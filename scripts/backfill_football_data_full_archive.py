from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/data.zip"
DEFAULT_SEASONS = tuple(f"{year % 100:02d}{(year + 1) % 100:02d}" for year in range(1993, 2026))


def download_zip(url: str, *, timeout: float = 90.0, attempts: int = 3) -> bytes:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            content = response.content
            if len(content) < 100 or not zipfile.is_zipfile(io.BytesIO(content)):
                raise ValueError(f"response is not a valid ZIP: {url}")
            return content
        except (requests.RequestException, ValueError) as exc:
            error = exc
            if attempt < attempts:
                time.sleep(attempt)
    raise RuntimeError(f"failed to download {url}") from error


def preserve_zip(root: Path, season: str, content: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(content).hexdigest()
    path = root / "raw" / "football_data_archives" / season / f"data_{digest[:16]}.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return {"archive_path": str(path), "archive_sha256": digest, "archive_bytes": len(content)}


def parse_csv_bytes(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if not raw_row or not any(value not in (None, "") for value in raw_row.values()):
            continue
        # Some legacy files contain overflow cells that csv.DictReader stores under a None key.
        # Preserve named source fields and drop only the structurally unaddressable overflow key.
        row = {str(key): value for key, value in raw_row.items() if key is not None}
        rows.append(row)
    return rows


def extract_valid_csvs(season: str, archive: bytes) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]]:
    combined: list[dict[str, str]] = []
    profiles: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for info in sorted(zf.infolist(), key=lambda item: item.filename):
            if info.is_dir() or not info.filename.lower().endswith(".csv"):
                continue
            filename = Path(info.filename).name
            division = Path(filename).stem
            try:
                content = zf.read(info)
                parsed_rows = parse_csv_bytes(content)
                if not parsed_rows:
                    raise ValueError("zero parsed rows")
                sample_keys = set().union(*(row.keys() for row in parsed_rows[: min(10, len(parsed_rows))]))
                if not {"HomeTeam", "AwayTeam"}.issubset(sample_keys):
                    raise ValueError("missing HomeTeam/AwayTeam columns")

                rows: list[dict[str, str]] = []
                rejected_non_match_rows = 0
                for row in parsed_rows:
                    home = (row.get("HomeTeam") or "").strip()
                    away = (row.get("AwayTeam") or "").strip()
                    date = (row.get("Date") or "").strip()
                    # Legacy source files occasionally contain footer/annotation rows with values in
                    # unrelated columns. They are not matches and must not enter the bronze match table.
                    if not home or not away or not date:
                        rejected_non_match_rows += 1
                        continue
                    rows.append(row)

                if not rows:
                    raise ValueError("zero valid match rows after identity filtering")

                nonempty = Counter()
                for row in rows:
                    row["_season"] = season
                    row["_division"] = division
                    row["_source_archive"] = BASE_URL.format(season=season)
                    row["_source_file"] = info.filename
                    for key, value in row.items():
                        if value not in (None, ""):
                            nonempty[key] += 1
                combined.extend(rows)
                profiles.append(
                    {
                        "season": season,
                        "division": division,
                        "source_file": info.filename,
                        "rows": len(rows),
                        "parsed_rows_before_identity_filter": len(parsed_rows),
                        "rejected_non_match_rows": rejected_non_match_rows,
                        "columns": len({key for row in rows for key in row}),
                        "nonempty_columns": dict(sorted(nonempty.items())),
                        "csv_sha256": hashlib.sha256(content).hexdigest(),
                        "csv_bytes": len(content),
                    }
                )
            except Exception as exc:
                failures.append(
                    {
                        "season": season,
                        "source_file": info.filename,
                        "error": repr(exc),
                    }
                )
    return combined, profiles, failures


def write_bronze(rows: list[dict[str, str]], path: Path) -> None:
    fields: set[str] = set()
    for row in rows:
        fields.update(row)
    provenance = ["_season", "_division", "_source_archive", "_source_file"]
    ordered = provenance + sorted(fields - set(provenance))
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ordered, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def duplicate_report(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str, str]] = Counter()
    for row in rows:
        key = (
            row.get("_division", ""),
            row.get("Date", ""),
            row.get("HomeTeam", ""),
            row.get("AwayTeam", ""),
        )
        if all(key):
            counts[key] += 1
    return [
        {"division": key[0], "date": key[1], "home": key[2], "away": key[3], "count": count}
        for key, count in counts.items()
        if count > 1
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill all official Football-Data seasonal CSV archives.")
    parser.add_argument("--output-root", default="artifacts/football-data-full-archive")
    parser.add_argument("--seasons", nargs="*", default=list(DEFAULT_SEASONS))
    parser.add_argument("--min-rows", type=int, default=100000)
    args = parser.parse_args()

    root = Path(args.output_root)
    all_rows: list[dict[str, str]] = []
    archives: list[dict[str, Any]] = []
    csv_profiles: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for season in args.seasons:
        url = BASE_URL.format(season=season)
        try:
            archive = download_zip(url)
            archive_meta = preserve_zip(root, season, archive)
            rows, profiles, csv_failures = extract_valid_csvs(season, archive)
            if not rows:
                raise ValueError("season archive contained no valid match CSV rows")
            all_rows.extend(rows)
            csv_profiles.extend(profiles)
            failures.extend(csv_failures)
            archives.append(
                {
                    "season": season,
                    "url": url,
                    "valid_csv_files": len(profiles),
                    "rows": len(rows),
                    **archive_meta,
                }
            )
        except Exception as exc:
            failures.append({"season": season, "source_file": url, "error": repr(exc)})

    bronze_path = root / "bronze" / "football_data_full_archive.csv.gz"
    write_bronze(all_rows, bronze_path)
    duplicates = duplicate_report(all_rows)
    divisions = sorted({row.get("_division", "") for row in all_rows if row.get("_division")})
    columns = sorted({key for row in all_rows for key in row})
    rejected_non_match_rows = sum(int(profile.get("rejected_non_match_rows", 0)) for profile in csv_profiles)

    report = {
        "requested_seasons": list(args.seasons),
        "successful_archives": len(archives),
        "failed_or_skipped_items": len(failures),
        "valid_csv_files": len(csv_profiles),
        "rows": len(all_rows),
        "rejected_non_match_rows": rejected_non_match_rows,
        "divisions": divisions,
        "division_count": len(divisions),
        "unique_columns": len(columns),
        "columns": columns,
        "duplicate_match_keys": duplicates,
        "archives": archives,
        "csv_profiles": csv_profiles,
        "failures": failures,
        "bronze_path": str(bronze_path),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "successful_archives": len(archives),
                "valid_csv_files": len(csv_profiles),
                "rows": len(all_rows),
                "rejected_non_match_rows": rejected_non_match_rows,
                "division_count": len(divisions),
                "unique_columns": len(columns),
                "duplicate_match_keys": len(duplicates),
                "failures": len(failures),
            },
            indent=2,
        )
    )

    if len(all_rows) < args.min_rows:
        raise SystemExit(f"archive too small: {len(all_rows)} rows < required {args.min_rows}")


if __name__ == "__main__":
    main()
