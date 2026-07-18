from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

import requests


DATASET_SLUG = "eladsil/football-games-odds"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
DATE_FORMAT = "%m/%d/%Y %H:%M"


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


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value.strip(), DATE_FORMAT)


def percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def audit_matches_odds(path: Path) -> dict[str, Any]:
    updates_per_match: Counter[str] = Counter()
    distinct_competitions: set[str] = set()
    first_created: datetime | None = None
    last_created: datetime | None = None
    first_start: datetime | None = None
    last_start: datetime | None = None
    rows_after_start = 0
    invalid_odds = Counter()
    duplicate_exact_rows = 0
    previous_fingerprint: tuple[str, ...] | None = None
    rows = 0

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        expected = {
            "match_id", "date_start", "competition_name", "date_created",
            "home_team_name", "away_team_name", "home_team_odd", "away_team_odd", "tie_odd",
        }
        if set(reader.fieldnames or []) != expected:
            raise ValueError(f"unexpected Matches_Odds schema: {reader.fieldnames}")
        for row in reader:
            rows += 1
            match_id = row["match_id"].strip()
            created = parse_dt(row["date_created"])
            start = parse_dt(row["date_start"])
            updates_per_match[match_id] += 1
            distinct_competitions.add(row["competition_name"].strip())
            first_created = created if first_created is None or created < first_created else first_created
            last_created = created if last_created is None or created > last_created else last_created
            first_start = start if first_start is None or start < first_start else first_start
            last_start = start if last_start is None or start > last_start else last_start
            if created > start:
                rows_after_start += 1
            for field in ("home_team_odd", "away_team_odd", "tie_odd"):
                try:
                    value = float(row[field])
                    if value <= 1.0:
                        invalid_odds[field] += 1
                except ValueError:
                    invalid_odds[field] += 1
            fingerprint = tuple(row.get(field, "") for field in reader.fieldnames or [])
            if fingerprint == previous_fingerprint:
                duplicate_exact_rows += 1
            previous_fingerprint = fingerprint

    counts = list(updates_per_match.values())
    return {
        "rows": rows,
        "unique_matches": len(updates_per_match),
        "unique_competitions": len(distinct_competitions),
        "date_created_min": first_created.isoformat() if first_created else None,
        "date_created_max": last_created.isoformat() if last_created else None,
        "match_start_min": first_start.isoformat() if first_start else None,
        "match_start_max": last_start.isoformat() if last_start else None,
        "rows_after_match_start": rows_after_start,
        "rows_after_match_start_fraction": rows_after_start / rows if rows else None,
        "invalid_or_nondecimal_odds_counts": dict(invalid_odds),
        "consecutive_exact_duplicate_rows": duplicate_exact_rows,
        "updates_per_match": {
            "min": min(counts) if counts else None,
            "median": statistics.median(counts) if counts else None,
            "mean": statistics.mean(counts) if counts else None,
            "p90": percentile(counts, 0.90),
            "p99": percentile(counts, 0.99),
            "max": max(counts) if counts else None,
        },
    }


def audit_results(path: Path) -> dict[str, Any]:
    rows = 0
    matches: set[str] = set()
    first_start: datetime | None = None
    last_start: datetime | None = None
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows += 1
            matches.add(row["match_id"].strip())
            start = parse_dt(row["date_start"])
            first_start = start if first_start is None or start < first_start else first_start
            last_start = start if last_start is None or start > last_start else last_start
    return {
        "rows": rows,
        "unique_matches": len(matches),
        "match_start_min": first_start.isoformat() if first_start else None,
        "match_start_max": last_start.isoformat() if last_start else None,
    }


def profile_csv_stream(fh: TextIO, sample_rows: int = 5) -> dict[str, Any]:
    reader = csv.DictReader(fh)
    columns = list(reader.fieldnames or [])
    rows = 0
    samples: list[dict[str, str]] = []
    nonempty = Counter()
    candidates: dict[str, set[str]] = {
        col: set() for col in columns
        if any(token in col.casefold() for token in ("book", "match", "game", "league", "market", "time", "date", "odd", "home", "away"))
    }
    for row in reader:
        rows += 1
        if len(samples) < sample_rows:
            samples.append({str(k): str(v)[:300] if v is not None else "" for k, v in row.items() if k is not None})
        for key, value in row.items():
            if key is None or value in (None, "", "nan", "NaN", "NULL", "null"):
                continue
            nonempty[key] += 1
            bucket = candidates.get(key)
            if bucket is not None and len(bucket) < 100_000:
                bucket.add(str(value))
    return {
        "type": "csv", "rows": rows, "columns": columns, "column_count": len(columns), "sample_rows": samples,
        "nonempty_by_column": dict(sorted(nonempty.items())),
        "distinct_candidate_counts": {k: len(v) for k, v in sorted(candidates.items())},
        "distinct_candidate_samples": {k: sorted(v)[:100] for k, v in sorted(candidates.items())},
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
            output["tables"][table] = {"rows": count, "columns": columns, "column_count": len(columns)}
        return output
    finally:
        conn.close()


def profile_file(path: Path) -> dict[str, Any]:
    lower, suffix = path.name.casefold(), path.suffix.casefold()
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
            members = [{"name": i.filename, "compressed_bytes": i.compress_size, "uncompressed_bytes": i.file_size} for i in zf.infolist() if not i.is_dir()]
        files: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for path in sorted(p for p in extracted.rglob("*") if p.is_file()):
            item: dict[str, Any] = {"path": str(path.relative_to(extracted)), "bytes": path.stat().st_size}
            try:
                item["profile"] = profile_file(path)
            except Exception as exc:
                failures.append({"path": item["path"], "error_type": type(exc).__name__, "error": str(exc)})
            files.append(item)
        odds_path = extracted / "Matches_Odds.csv"
        results_path = extracted / "Matches_Results.csv"
        if not odds_path.exists() or not results_path.exists():
            raise ValueError("expected Matches_Odds.csv and Matches_Results.csv are required")
        odds_audit = audit_matches_odds(odds_path)
        results_audit = audit_results(results_path)
        manifest = {
            "dataset_slug": DATASET_SLUG, "download_url": DOWNLOAD_URL,
            "archive": {"path": str(archive), **archive_meta}, "zip_members": members,
            "files": files, "profile_failures": failures,
            "source_semantics": {
                "bookmaker_identity": "No bookmaker column exists in Matches_Odds.csv; treat as one source/global feed, not multi-bookmaker history.",
                "quote_timestamp": "date_created is an explicit quote-state timestamp; rows after scheduled date_start are separately counted and must be excluded for pre-match research.",
            },
            "odds_change_audit": odds_audit,
            "results_audit": results_audit,
            "result_matches_missing_from_odds": max(0, results_audit["unique_matches"] - odds_audit["unique_matches"]),
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
        print(json.dumps({"archive_bytes": archive_meta["bytes"], "odds_rows": odds_audit["rows"], "odds_matches": odds_audit["unique_matches"], "updates_per_match": odds_audit["updates_per_match"], "rows_after_start": odds_audit["rows_after_match_start"], "profile_failures": len(failures)}, indent=2))
        if failures:
            raise RuntimeError(f"profile failures detected: {len(failures)}")
        failure_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
