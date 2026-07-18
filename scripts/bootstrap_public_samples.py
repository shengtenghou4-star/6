from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.sources.football_data import fetch_season_division, summarize_columns
from marketlab.sources.statsbomb_open import fetch_competitions
from marketlab.sources.the_odds_api import fetch_public_epl_sample
from marketlab.storage import write_raw_json_gz


def _odds_sample_summary(payload: dict) -> dict:
    events = payload.get("data", [])
    bookmaker_keys: set[str] = set()
    market_keys: set[str] = set()
    quote_rows = 0
    for event in events:
        for bookmaker in event.get("bookmakers", []) or []:
            key = bookmaker.get("key")
            if key:
                bookmaker_keys.add(str(key))
            for market in bookmaker.get("markets", []) or []:
                market_key = market.get("key")
                if market_key:
                    market_keys.add(str(market_key))
                quote_rows += len(market.get("outcomes", []) or [])
    return {
        "snapshot_timestamp": payload.get("timestamp"),
        "events": len(events),
        "bookmakers": len(bookmaker_keys),
        "bookmaker_keys": sorted(bookmaker_keys),
        "market_keys": sorted(market_keys),
        "outcome_quotes": quote_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch small public samples before any large ingestion.")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--season", default="2526", help="Football-Data season code, e.g. 2526")
    parser.add_argument("--division", default="E0", help="Football-Data division code, e.g. E0")
    args = parser.parse_args()

    root = Path(args.data_root)

    odds = fetch_public_epl_sample()
    odds_path = write_raw_json_gz(root, source="the_odds_api", dataset="official_historical_epl_sample", payload=odds)

    fd = fetch_season_division(args.season, args.division)
    fd_payload = {
        "season": fd.season,
        "division": fd.division,
        "source_url": fd.source_url,
        "rows": fd.rows,
    }
    fd_path = write_raw_json_gz(root, source="football_data", dataset=f"{args.season}_{args.division}", payload=fd_payload)

    competitions = fetch_competitions()
    sb_path = write_raw_json_gz(root, source="statsbomb_open", dataset="competitions", payload=competitions)

    report = {
        "the_odds_api": {
            **_odds_sample_summary(odds),
            "raw_path": str(odds_path),
        },
        "football_data": {
            "rows": len(fd.rows),
            "nonempty_by_column": summarize_columns(fd.rows),
            "raw_path": str(fd_path),
        },
        "statsbomb_open": {
            "competition_rows": len(competitions),
            "raw_path": str(sb_path),
        },
    }
    report_path = root / "sample_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
