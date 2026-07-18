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


DATASET_SLUG = "austro/beat-the-bookie-worldwide-football-dataset"
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


def profile_csv_stream(fh: TextIO, *, sample_rows: int = 3) -> dict[str, Any]:
    reader = csv.DictReader(fh)
    header = list(reader.fieldnames or [])
    rows = 0
    samples: list[dict[str, str]] = []
    nonempty = Counter()
    distinct_candidates: dict[str, set[str]] = {
        key: set()
        for key in header
        if key.casefold() in {
            "match_id", "matchid", "fixture_id", "fixtureid", "league", "league_id", "leagueid",
            "bookmaker", "bookmaker_id", "bookmakerid", "provider", "provider_id", "providerid",
            "market", "market_id", "marketid", "selection", "outcome", "timestamp", "time", "date",
        }
    }
    minmax_candidates: dict[str, list[str | None]] = {
        key: [None, None]
        for key in header
        if any(token in key.casefold() for token in ("time", "date", "timestamp"))
    }

    for row in reader:
        rows += 1
        if len(samples) < sample_rows:
            samples.append({key: str(value)[:300] if value is not None else "" for key, value in row.items() if key is not None})
        for key, value in row.items():
            if key is None or value in (None, ""):
                continue
            text = str(value)
            nonempty[key] += 1
            bucket = distinct_candidates.get(key)
            if bucket is not None and len(bucket) < 200_000:
                bucket.add(text)
            minmax = minmax_candidates.get(key)
            if minmax is not None:
                if minmax[0] is None or text < minmax[0]:
                    minmax[0] = text
                if minmax[1] is None or text > minmax[1]:
                    minmax[1] = text

    return {
        "type": "csv",
        "rows": rows,
        "columns": header,
        "column_count": len(header),
        "sample_rows": samples,
        "nonempty_by_column": dict(sorted(nonempty.items())),
        "distinct_candidate_counts": {key: len(values) for key, values in sorted(distinct_candidates.items())},
        "lexical_minmax_time_like_columns": {
            key: {"min": values[0], "max": values[1]} for key, values in sorted(minmax_candidates.items())
        },
    }


def count_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        return profile_csv_stream(fh)


def count_csv_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as fh:
        profile = profile_csv_stream(fh)
    profile["type"] = "csv.gz"
    return profile


def profile_sqlite(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result: dict[str, Any] = {"type": "sqlite", "tables": {}}
        for table in tables:
            safe = table.replace('"', '""')
            cols = [row[1] for row in conn.execute(f'PRAGMA table_info("{safe}")')]
            rows = conn.execute(f'SELECT COUNT(*) FROM "{safe}"').fetchone()[0]
            result["tables"][table] = {"rows": int(rows), "columns": cols, "column_count": len(cols)}
        return result
    finally:
        conn.close()


def profile_extracted(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = str(path.relative_to(root))
        item: dict[str, Any] = {"path": rel, "bytes": path.stat().st_size}
        try:
            lower_name = path.name.casefold()
            suffix = path.suffix.casefold()
            if lower_name.endswith(".csv.gz"):
                item["profile"] = count_csv_gz(path)
            elif suffix == ".csv":
                item["profile"] = count_csv(path)
            elif suffix in {".sqlite", ".sqlite3", ".db"}:
                item["profile"] = profile_sqlite(path)
            elif suffix == ".json":
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                item["profile"] = {
                    "type": "json",
                    "root_type": type(payload).__name__,
                    "records": len(payload) if isinstance(payload, (list, dict)) else None,
                }
            else:
                item["profile"] = {"type": suffix.lstrip(".") or "other"}
        except Exception as exc:
            failures.append({"path": rel, "error_type": type(exc).__name__, "error": str(exc)})
        files.append(item)
    return {"files": files, "profile_failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire and profile the public Beat The Bookie Kaggle dataset.")
    parser.add_argument("--output-root", default="artifacts/beat-the-bookie")
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "beat-the-bookie-kaggle.zip"
    extracted = root / "extracted"
    failure_path = root / "failure.json"

    try:
        meta = download(DOWNLOAD_URL, archive)
        if not zipfile.is_zipfile(archive):
            raise ValueError("Kaggle response is not a ZIP archive")
        if extracted.exists():
            shutil.rmtree(extracted)
        extracted.mkdir(parents=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extracted)
            zip_members = [
                {"name": info.filename, "compressed_bytes": info.compress_size, "uncompressed_bytes": info.file_size}
                for info in zf.infolist() if not info.is_dir()
            ]

        profile = profile_extracted(extracted)
        manifest = {
            "dataset_slug": DATASET_SLUG,
            "download_url": DOWNLOAD_URL,
            "license_from_dataset_page": "CC BY-SA 4.0",
            "archive": {"path": str(archive), **meta},
            "zip_members": zip_members,
            **profile,
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"archive_bytes": meta["bytes"], "files": len(profile["files"]), "profile_failures": len(profile["profile_failures"])}, indent=2))
        if profile["profile_failures"]:
            raise RuntimeError(f"profile failures detected: {len(profile['profile_failures'])}")
        failure_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
