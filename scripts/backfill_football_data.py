from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"
DEFAULT_DIVISIONS = ("E0", "D1", "I1", "SP1", "F1")
DEFAULT_SEASONS = tuple(f"{year % 100:02d}{(year + 1) % 100:02d}" for year in range(2015, 2026))


def fetch_csv(url: str, *, timeout: float = 30.0, attempts: int = 3) -> bytes:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            if not response.content.strip():
                raise ValueError(f"empty response from {url}")
            return response.content
        except (requests.RequestException, ValueError) as exc:
            error = exc
            if attempt < attempts:
                time.sleep(attempt)
    raise RuntimeError(f"failed to fetch {url}") from error


def parse_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader if row and any(value not in (None, "") for value in row.values())]


def write_raw(root: Path, *, season: str, division: str, content: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(content).hexdigest()
    path = root / "raw" / "football_data" / season / f"{division}_{digest[:16]}.csv.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with gzip.open(path, "wb") as fh:
            fh.write(content)
    return {"path": str(path), "sha256": digest, "bytes": len(content)}


def write_bronze(rows: list[dict[str, str]], path: Path) -> None:
    fields: set[str] = set()
    for row in rows:
        fields.update(row)
    ordered = ["_season", "_division", "_source_url"] + sorted(fields - {"_season", "_division", "_source_url"})
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ordered, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill a coarse multi-league Football-Data baseline.")
    parser.add_argument("--data-root", default="artifacts/football-data-baseline")
    parser.add_argument("--seasons", nargs="*", default=list(DEFAULT_SEASONS))
    parser.add_argument("--divisions", nargs="*", default=list(DEFAULT_DIVISIONS))
    parser.add_argument("--min-rows", type=int, default=15000)
    args = parser.parse_args()

    root = Path(args.data_root)
    all_rows: list[dict[str, str]] = []
    files: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    duplicate_keys: Counter[tuple[str, str, str, str]] = Counter()

    for season in args.seasons:
        for division in args.divisions:
            url = BASE_URL.format(season=season, division=division)
            try:
                content = fetch_csv(url)
                rows = parse_csv(content)
                if not rows:
                    raise ValueError("parsed zero data rows")
                raw = write_raw(root, season=season, division=division, content=content)
                nonempty_columns = Counter()
                for row in rows:
                    row["_season"] = season
                    row["_division"] = division
                    row["_source_url"] = url
                    for key, value in row.items():
                        if value not in (None, ""):
                            nonempty_columns[key] += 1
                    match_key = (division, row.get("Date", ""), row.get("HomeTeam", ""), row.get("AwayTeam", ""))
                    duplicate_keys[match_key] += 1
                all_rows.extend(rows)
                files.append(
                    {
                        "season": season,
                        "division": division,
                        "source_url": url,
                        "rows": len(rows),
                        "columns": len({key for row in rows for key in row}),
                        "nonempty_columns": dict(sorted(nonempty_columns.items())),
                        **raw,
                    }
                )
            except Exception as exc:  # report failures rather than silently skipping them
                failures.append({"season": season, "division": division, "source_url": url, "error": repr(exc)})

    duplicate_match_keys = [
        {"division": key[0], "date": key[1], "home": key[2], "away": key[3], "count": count}
        for key, count in duplicate_keys.items()
        if count > 1 and all(key)
    ]

    bronze_path = root / "bronze" / "football_data_matches.csv.gz"
    write_bronze(all_rows, bronze_path)

    unique_columns = sorted({key for row in all_rows for key in row})
    report = {
        "requested_seasons": args.seasons,
        "requested_divisions": args.divisions,
        "successful_files": len(files),
        "failed_files": len(failures),
        "rows": len(all_rows),
        "unique_columns": len(unique_columns),
        "columns": unique_columns,
        "duplicate_match_keys": duplicate_match_keys,
        "files": files,
        "failures": failures,
        "bronze_path": str(bronze_path),
    }
    report_path = root / "coverage_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("successful_files", "failed_files", "rows", "unique_columns")}, indent=2))
    if len(all_rows) < args.min_rows:
        raise SystemExit(f"baseline too small: {len(all_rows)} rows < required {args.min_rows}")
    if duplicate_match_keys:
        raise SystemExit(f"found {len(duplicate_match_keys)} duplicate match keys; inspect coverage_report.json")


if __name__ == "__main__":
    main()
