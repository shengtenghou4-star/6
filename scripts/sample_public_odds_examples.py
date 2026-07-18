from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.sources.the_odds_api import PUBLIC_SAMPLE_URLS, fetch_public_sample
from marketlab.storage import write_raw_json_gz


def profile(payload: dict[str, Any]) -> dict[str, Any]:
    bookmakers = Counter()
    markets = Counter()
    outcomes = 0
    events = payload.get("data") or []
    if not isinstance(events, list):
        raise ValueError("payload data must be a list")
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
                rows = market.get("outcomes")
                if isinstance(rows, list):
                    outcomes += len(rows)
    return {
        "timestamp": payload.get("timestamp"),
        "events": len(events),
        "bookmaker_count": len(bookmakers),
        "bookmakers": dict(sorted(bookmakers.items())),
        "market_count": len(markets),
        "markets": dict(sorted(markets.items())),
        "outcome_rows": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and profile official credential-free The Odds API historical samples.")
    parser.add_argument("--output-root", default="artifacts/public-odds-samples")
    args = parser.parse_args()

    root = Path(args.output_root)
    report: dict[str, Any] = {"samples": {}}
    for sample_key, source_url in PUBLIC_SAMPLE_URLS.items():
        payload = fetch_public_sample(sample_key)
        raw_path = write_raw_json_gz(root, source="the_odds_api_public", dataset=sample_key, payload=payload)
        report["samples"][sample_key] = {
            "source_url": source_url,
            "raw_path": str(raw_path),
            "profile": profile(payload),
        }

    root.mkdir(parents=True, exist_ok=True)
    (root / "sample_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
