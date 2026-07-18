from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from marketlab.sources.the_odds_api import HistoricalQuery, estimate_snapshot_credits, fetch_historical_snapshot
from marketlab.storage import write_raw_json_gz


def parse_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("snapshot timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    bookmakers = Counter()
    markets = Counter()
    outcome_rows = 0
    events = payload.get("data")
    if not isinstance(events, list):
        raise ValueError("historical payload data must be list")

    for event in events:
        if not isinstance(event, dict):
            continue
        for bookmaker in event.get("bookmakers") or []:
            if not isinstance(bookmaker, dict):
                continue
            key = bookmaker.get("key")
            if isinstance(key, str):
                bookmakers[key] += 1
            for market in bookmaker.get("markets") or []:
                if not isinstance(market, dict):
                    continue
                market_key = market.get("key")
                if isinstance(market_key, str):
                    markets[market_key] += 1
                outcomes = market.get("outcomes")
                if isinstance(outcomes, list):
                    outcome_rows += len(outcomes)

    return {
        "snapshot_timestamp": payload.get("timestamp"),
        "previous_timestamp": payload.get("previous_timestamp"),
        "next_timestamp": payload.get("next_timestamp"),
        "events": len(events),
        "bookmakers": dict(sorted(bookmakers.items())),
        "bookmaker_count": len(bookmakers),
        "markets": dict(sorted(markets.items())),
        "market_count": len(markets),
        "outcome_rows": outcome_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a narrow, credit-capped authenticated The Odds API historical sample.")
    parser.add_argument("--sport", required=True, help="The Odds API sport key")
    parser.add_argument("--snapshot", action="append", required=True, help="ISO-8601 timestamp; repeat for multiple snapshots")
    parser.add_argument("--regions", default="uk,eu", help="Comma-separated regions")
    parser.add_argument("--markets", default="h2h", help="Comma-separated markets")
    parser.add_argument("--max-estimated-credits", type=int, default=500, help="Hard preflight cap before any request")
    parser.add_argument("--output-root", default="artifacts/the-odds-api-auth-sample")
    parser.add_argument("--api-key-env", default="THE_ODDS_API_KEY")
    args = parser.parse_args()

    regions = tuple(item.strip() for item in args.regions.split(",") if item.strip())
    markets = tuple(item.strip() for item in args.markets.split(",") if item.strip())
    snapshots = [parse_utc(item) for item in args.snapshot]
    if not regions or not markets or not snapshots:
        raise SystemExit("regions, markets and snapshots must be non-empty")

    estimated = estimate_snapshot_credits(regions=len(regions), markets=len(markets), snapshots=len(snapshots))
    if estimated > args.max_estimated_credits:
        raise SystemExit(
            f"refusing to run: estimated {estimated} credits exceeds cap {args.max_estimated_credits}; "
            "narrow the sample or raise the cap explicitly"
        )

    api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        raise SystemExit(f"missing API key in environment variable {args.api_key_env}")

    root = Path(args.output_root)
    samples: list[dict[str, Any]] = []
    for snapshot in snapshots:
        query = HistoricalQuery(sport=args.sport, regions=regions, markets=markets, snapshot_at=snapshot)
        payload, headers = fetch_historical_snapshot(api_key, query)
        dataset = snapshot.strftime("%Y%m%dT%H%M%SZ")
        raw_path = write_raw_json_gz(root, source="the_odds_api", dataset=dataset, payload=payload)
        samples.append(
            {
                "requested_snapshot": snapshot.isoformat(),
                "estimated_credits": query.estimated_credits,
                "usage_headers": headers,
                "raw_path": str(raw_path),
                "profile": summarize_payload(payload),
            }
        )

    report = {
        "sport": args.sport,
        "regions": list(regions),
        "markets": list(markets),
        "snapshot_requests": len(snapshots),
        "estimated_total_credits": estimated,
        "samples": samples,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "sample_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
