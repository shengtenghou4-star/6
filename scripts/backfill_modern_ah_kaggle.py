from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, TextIO

import requests


DATASET_SLUG = "realsingwong/european-football-asian-handicap-odds-time-series"
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


def profile_csv_stream(fh: TextIO, *, sample_rows: int = 5) -> dict[str, Any]:
    reader = csv.DictReader(fh)
    columns = list(reader.fieldnames or [])
    rows = 0
    samples: list[dict[str, str]] = []
    nonempty = Counter()
    distinct: dict[str, set[str]] = {
        key: set()
        for key in columns
        if any(token in key.casefold() for token in ("book", "league", "season", "market", "match_id", "fixture", "time", "date"))
    }
    for row in reader:
        rows += 1
        if len(samples) < sample_rows:
            samples.append({str(key): str(value)[:300] if value is not None else "" for key, value in row.items() if key is not None})
        for key, value in row.items():
            if key is None or value in (None, "", "nan", "NaN", "NULL", "null"):
                continue
            nonempty[key] += 1
            bucket = distinct.get(key)
            if bucket is not None and len(bucket) < 100_000:
                bucket.add(str(value))
    return {
        "rows": rows,
        "columns": columns,
        "column_count": len(columns),
        "sample_rows": samples,
        "nonempty_by_column": dict(sorted(nonempty.items())),
        "distinct_candidate_counts": {key: len(values) for key, values in sorted(distinct.items())},
        "distinct_candidate_samples": {key: sorted(values)[:100] for key, values in sorted(distinct.items())},
    }


def profile_file(path: Path) -> dict[str, Any]:
    name = path.name.casefold()
    if name.endswith(".csv.gz"):
        with gzip.open(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as fh:
            return {"type": "csv.gz", **profile_csv_stream(fh)}
    if path.suffix.casefold() == ".csv":
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            return {"type": "csv", **profile_csv_stream(fh)}
    if path.suffix.casefold() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return {
            "type": "json",
            "root_type": type(payload).__name__,
            "records": len(payload) if isinstance(payload, (list, dict)) else None,
            "sample": payload[:3] if isinstance(payload, list) else None,
        }
    return {"type": path.suffix.casefold().lstrip(".") or "other", "profile_supported": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire and profile a public modern European Asian Handicap odds time-series dataset.")
    parser.add_argument("--output-root", default="artifacts/modern-ah-timeseries")
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
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
            "archive": {"path": str(archive), **meta},
            "zip_members": zip_members,
            "files": files,
            "profile_failures": failures,
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"archive_bytes": meta["bytes"], "files": len(files), "profile_failures": len(failures)}, indent=2))
        if failures:
            raise RuntimeError(f"profile failures detected: {len(failures)}")
        failure_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
