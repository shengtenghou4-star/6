from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, TextIO

import requests


DATASET_SLUG = "eladsil/football-games-odds"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"


def download(url: str, path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256()
    total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        if response.status_code in {401, 403}:
            raise PermissionError(f"Kaggle download is account/auth gated: HTTP {response.status_code}")
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
                fh.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "final_url": str(response.url)}


def profile_csv_stream(fh: TextIO, sample_rows: int = 5) -> dict[str, Any]:
    reader = csv.DictReader(fh)
    columns = list(reader.fieldnames or [])
    rows = 0
    samples: list[dict[str, str]] = []
    nonempty = Counter()
    candidates: dict[str, set[str]] = {
        col: set()
        for col in columns
        if any(token in col.casefold() for token in ("book", "match", "game", "league", "market", "time", "date", "odd", "home", "away"))
    }
    minmax: dict[str, list[str | None]] = {
        col: [None, None]
        for col in columns
        if any(token in col.casefold() for token in ("time", "date"))
    }
    for row in reader:
        rows += 1
        if len(samples) < sample_rows:
            samples.append({str(k): str(v)[:300] if v is not None else "" for k, v in row.items() if k is not None})
        for key, value in row.items():
            if key is None or value in (None, "", "nan", "NaN", "NULL", "null"):
                continue
            text = str(value)
            nonempty[key] += 1
            bucket = candidates.get(key)
            if bucket is not None and len(bucket) < 100_000:
                bucket.add(text)
            bounds = minmax.get(key)
            if bounds is not None:
                if bounds[0] is None or text < bounds[0]:
                    bounds[0] = text
                if bounds[1] is None or text > bounds[1]:
                    bounds[1] = text
    return {
        "type": "csv",
        "rows": rows,
        "columns": columns,
        "column_count": len(columns),
        "sample_rows": samples,
        "nonempty_by_column": dict(sorted(nonempty.items())),
        "distinct_candidate_counts": {k: len(v) for k, v in sorted(candidates.items())},
        "distinct_candidate_samples": {k: sorted(v)[:100] for k, v in sorted(candidates.items())},
        "lexical_time_date_minmax": {k: {"min": v[0], "max": v[1]} for k, v in sorted(minmax.items())},
    }


def profile_sqlite(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        output: dict[str, Any] = {"type": "sqlite", "tables": {}}
        for table in tables:
            safe = table.replace('"', '""')
            columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{safe}")')]
            count = int(conn.execute(f'SELECT COUNT(*) FROM "{safe}"').fetchone()[0])
            sample = conn.execute(f'SELECT * FROM "{safe}" LIMIT 5').fetchall()
            output["tables"][table] = {
                "rows": count,
                "columns": columns,
                "column_count": len(columns),
                "sample_rows": [dict(zip(columns, row, strict=False)) for row in sample],
            }
        return output
    finally:
        conn.close()


def profile_file(path: Path) -> dict[str, Any]:
    lower = path.name.casefold()
    suffix = path.suffix.casefold()
    if lower.endswith(".csv.gz"):
        with gzip.open(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as fh:
            result = profile_csv_stream(fh)
        result["type"] = "csv.gz"
        return result
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            return profile_csv_stream(fh)
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return profile_sqlite(path)
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return {"type": "json", "root_type": type(payload).__name__, "records": len(payload) if isinstance(payload, (list, dict)) else None}
    if suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"type": suffix.lstrip("."), "characters": len(text), "text": text[:50_000]}
    return {"type": suffix.lstrip(".") or "other", "profile_supported": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire and profile an independent public football odds-change dataset.")
    parser.add_argument("--output-root", default="artifacts/football-games-odds")
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    failure_path = root / "failure.json"

    try:
        archive_meta = download(DOWNLOAD_URL, archive)
        if not zipfile.is_zipfile(archive):
            raise ValueError("Kaggle response is not a ZIP archive")
        if extracted.exists():
            shutil.rmtree(extracted)
        extracted.mkdir(parents=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extracted)
            members = [
                {"name": i.filename, "compressed_bytes": i.compress_size, "uncompressed_bytes": i.file_size}
                for i in zf.infolist() if not i.is_dir()
            ]

        files: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for path in sorted(p for p in extracted.rglob("*") if p.is_file()):
            item: dict[str, Any] = {"path": str(path.relative_to(extracted)), "bytes": path.stat().st_size}
            try:
                item["profile"] = profile_file(path)
            except Exception as exc:
                failures.append({"path": item["path"], "error_type": type(exc).__name__, "error": str(exc)})
            files.append(item)

        manifest = {
            "dataset_slug": DATASET_SLUG,
            "download_url": DOWNLOAD_URL,
            "archive": {"path": str(archive), **archive_meta},
            "zip_members": members,
            "files": files,
            "profile_failures": failures,
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
        print(json.dumps({"archive_bytes": archive_meta["bytes"], "files": len(files), "profile_failures": len(failures)}, indent=2))
        if failures:
            raise RuntimeError(f"profile failures detected: {len(failures)}")
        failure_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
