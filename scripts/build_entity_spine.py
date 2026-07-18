from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%Y-%m-%d")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def stable_id(prefix: str, *parts: str, length: int = 20) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:length]}"


def parse_date(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic Football-Data source-level entity spine.")
    parser.add_argument("--input", required=True, help="Full archive bronze CSV.gz")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    output = Path(args.output_root)
    teams: dict[str, dict[str, Any]] = {}
    aliases: dict[str, set[str]] = defaultdict(set)
    team_occurrences: dict[str, set[tuple[str, str]]] = defaultdict(set)
    match_rows: list[dict[str, str]] = []
    normalized_to_raw: dict[str, set[str]] = defaultdict(set)
    parse_failures: list[dict[str, str]] = []
    seen_match_ids: set[str] = set()
    duplicate_match_ids: list[dict[str, str]] = []
    rows_seen = 0

    with gzip.open(args.input, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row_number, row in enumerate(reader, start=2):
            rows_seen += 1
            home_raw = (row.get("HomeTeam") or "").strip()
            away_raw = (row.get("AwayTeam") or "").strip()
            division = (row.get("_division") or row.get("Div") or "").strip()
            season = (row.get("_season") or "").strip()
            raw_date = (row.get("Date") or "").strip()
            raw_time = (row.get("Time") or "").strip()

            if not home_raw or not away_raw or not division or not season or not raw_date:
                parse_failures.append(
                    {
                        "row": str(row_number),
                        "reason": "missing_identity_field",
                        "season": season,
                        "division": division,
                        "date": raw_date,
                        "home": home_raw,
                        "away": away_raw,
                    }
                )
                continue

            home_norm = normalize_name(home_raw)
            away_norm = normalize_name(away_raw)
            if not home_norm or not away_norm:
                parse_failures.append(
                    {
                        "row": str(row_number),
                        "reason": "empty_normalized_team",
                        "season": season,
                        "division": division,
                        "date": raw_date,
                        "home": home_raw,
                        "away": away_raw,
                    }
                )
                continue

            home_id = stable_id("fdteam", home_norm)
            away_id = stable_id("fdteam", away_norm)
            for team_id, norm, raw in ((home_id, home_norm, home_raw), (away_id, away_norm, away_raw)):
                teams.setdefault(team_id, {"team_id": team_id, "normalized_name": norm})
                aliases[team_id].add(raw)
                team_occurrences[team_id].add((season, division))
                normalized_to_raw[norm].add(raw)

            parsed_date = parse_date(raw_date)
            if parsed_date is None:
                parse_failures.append(
                    {
                        "row": str(row_number),
                        "reason": "unparsed_date",
                        "season": season,
                        "division": division,
                        "date": raw_date,
                        "home": home_raw,
                        "away": away_raw,
                    }
                )
                parsed_date = raw_date

            match_id = stable_id(
                "fdmatch",
                "football_data",
                division,
                season,
                parsed_date,
                raw_time,
                home_id,
                away_id,
            )
            if match_id in seen_match_ids:
                duplicate_match_ids.append(
                    {
                        "match_id": match_id,
                        "row": str(row_number),
                        "season": season,
                        "division": division,
                        "date": raw_date,
                        "home": home_raw,
                        "away": away_raw,
                    }
                )
            seen_match_ids.add(match_id)
            match_rows.append(
                {
                    "match_id": match_id,
                    "source": "football_data",
                    "season": season,
                    "division": division,
                    "raw_date": raw_date,
                    "parsed_date": parsed_date,
                    "raw_time": raw_time,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "home_team_raw": home_raw,
                    "away_team_raw": away_raw,
                }
            )

    output.mkdir(parents=True, exist_ok=True)

    with gzip.open(output / "teams.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        fields = ["team_id", "normalized_name", "raw_aliases", "occurrences"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for team_id in sorted(teams):
            writer.writerow(
                {
                    "team_id": team_id,
                    "normalized_name": teams[team_id]["normalized_name"],
                    "raw_aliases": json.dumps(sorted(aliases[team_id]), ensure_ascii=False),
                    "occurrences": json.dumps(sorted([list(item) for item in team_occurrences[team_id]]), ensure_ascii=False),
                }
            )

    with gzip.open(output / "matches.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        fields = list(match_rows[0].keys()) if match_rows else []
        writer = csv.DictWriter(fh, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(match_rows)

    alias_groups = [
        {"normalized_name": norm, "raw_aliases": sorted(raws), "count": len(raws)}
        for norm, raws in sorted(normalized_to_raw.items())
        if len(raws) > 1
    ]
    report = {
        "rows_seen": rows_seen,
        "matches_written": len(match_rows),
        "teams": len(teams),
        "multi_alias_normalized_groups": len(alias_groups),
        "alias_groups": alias_groups,
        "parse_or_identity_failures": parse_failures,
        "duplicate_match_ids": duplicate_match_ids,
    }
    (output / "entity_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "rows_seen": rows_seen,
                "matches_written": len(match_rows),
                "teams": len(teams),
                "multi_alias_normalized_groups": len(alias_groups),
                "parse_or_identity_failures": len(parse_failures),
                "duplicate_match_ids": len(duplicate_match_ids),
            },
            indent=2,
        )
    )

    if len(match_rows) != rows_seen:
        raise SystemExit(f"silent-row-loss gate failed: {len(match_rows)} matches from {rows_seen} rows")
    if duplicate_match_ids:
        raise SystemExit(f"duplicate deterministic match IDs: {len(duplicate_match_ids)}")


if __name__ == "__main__":
    main()
