from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from marketlab.availability import AvailabilityClass, classify_football_data_column


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile Football-Data market-field coverage by season/division.")
    parser.add_argument("--input", required=True, help="Full archive bronze CSV.gz")
    parser.add_argument("--output-root", default="artifacts/market-field-coverage")
    args = parser.parse_args()

    output = Path(args.output_root)
    output.mkdir(parents=True, exist_ok=True)

    rows_by_group: Counter[tuple[str, str]] = Counter()
    nonempty_by_group_column: Counter[tuple[str, str, str]] = Counter()
    nonempty_global: Counter[str] = Counter()
    columns_seen: set[str] = set()
    total_rows = 0

    with gzip.open(args.input, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise SystemExit("input has no header")
        columns_seen.update(reader.fieldnames)
        for row in reader:
            total_rows += 1
            season = (row.get("_season") or "").strip()
            division = (row.get("_division") or row.get("Div") or "").strip()
            if not season or not division:
                raise SystemExit(f"row {total_rows + 1} missing season/division provenance")
            rows_by_group[(season, division)] += 1
            for column, value in row.items():
                if column is None or value in (None, ""):
                    continue
                nonempty_global[column] += 1
                nonempty_by_group_column[(season, division, column)] += 1

    classifications = {column: classify_football_data_column(column) for column in sorted(columns_seen)}
    market_classes = {
        AvailabilityClass.MARKET_FIRST_SET_UNKNOWN_TIME,
        AvailabilityClass.MARKET_CLOSING,
    }
    market_columns = sorted(column for column, decision in classifications.items() if decision.availability in market_classes)
    unknown_columns = sorted(column for column, decision in classifications.items() if decision.availability == AvailabilityClass.UNKNOWN)

    global_rows = []
    for column in market_columns:
        decision = classifications[column]
        nonempty = nonempty_global[column]
        global_rows.append(
            {
                "column": column,
                "availability_class": decision.availability.value,
                "nonempty_rows": nonempty,
                "total_rows": total_rows,
                "coverage_fraction": nonempty / total_rows if total_rows else 0.0,
            }
        )
    global_rows.sort(key=lambda item: (-int(item["nonempty_rows"]), str(item["column"])))

    group_rows = []
    for (season, division), group_total in sorted(rows_by_group.items()):
        for column in market_columns:
            nonempty = nonempty_by_group_column[(season, division, column)]
            if nonempty == 0:
                continue
            decision = classifications[column]
            group_rows.append(
                {
                    "season": season,
                    "division": division,
                    "column": column,
                    "availability_class": decision.availability.value,
                    "nonempty_rows": nonempty,
                    "group_rows": group_total,
                    "coverage_fraction": nonempty / group_total,
                }
            )

    class_counts = Counter(decision.availability.value for decision in classifications.values())
    active_seasons_by_column: dict[str, set[str]] = defaultdict(set)
    active_divisions_by_column: dict[str, set[str]] = defaultdict(set)
    for item in group_rows:
        active_seasons_by_column[str(item["column"])].add(str(item["season"]))
        active_divisions_by_column[str(item["column"])].add(str(item["division"]))

    summary = {
        "total_rows": total_rows,
        "season_division_groups": len(rows_by_group),
        "columns_seen": len(columns_seen),
        "availability_class_counts": dict(sorted(class_counts.items())),
        "market_columns": len(market_columns),
        "unknown_columns": unknown_columns,
        "unknown_column_count": len(unknown_columns),
        "market_column_summary": [
            {
                **item,
                "active_seasons": len(active_seasons_by_column[str(item["column"])]),
                "active_divisions": len(active_divisions_by_column[str(item["column"])]),
            }
            for item in global_rows
        ],
    }

    (output / "coverage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    with (output / "market_columns_global.csv").open("w", encoding="utf-8", newline="") as fh:
        fields = ["column", "availability_class", "nonempty_rows", "total_rows", "coverage_fraction"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(global_rows)

    with gzip.open(output / "market_columns_by_season_division.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        fields = ["season", "division", "column", "availability_class", "nonempty_rows", "group_rows", "coverage_fraction"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(group_rows)

    print(
        json.dumps(
            {
                "total_rows": total_rows,
                "season_division_groups": len(rows_by_group),
                "columns_seen": len(columns_seen),
                "market_columns": len(market_columns),
                "unknown_columns": len(unknown_columns),
                "top_market_columns": [item["column"] for item in global_rows[:20]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
