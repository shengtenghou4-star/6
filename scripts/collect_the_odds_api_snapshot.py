from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

from marketlab.prospective_odds import (
    SnapshotRequest,
    archive_current_odds_snapshot,
    parse_csv_tuple,
    utc_now_iso,
)


API_HOST = "https://api.the-odds-api.com"
API_KEY_ENV = "THE_ODDS_API_KEY"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect one immutable current-odds snapshot from The Odds API v4."
    )
    parser.add_argument("--sport", required=True)
    parser.add_argument("--markets", default="h2h")
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--regions")
    location.add_argument("--bookmakers")
    parser.add_argument("--commence-time-from")
    parser.add_argument("--commence-time-to")
    parser.add_argument("--output-root", default="artifacts/prospective-odds")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()

    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise SystemExit(
            f"missing required environment secret {API_KEY_ENV}; no request was sent and no credits were used"
        )

    request = SnapshotRequest(
        sport=args.sport,
        markets=parse_csv_tuple(args.markets),
        regions=parse_csv_tuple(args.regions),
        bookmakers=parse_csv_tuple(args.bookmakers),
        commence_time_from=args.commence_time_from,
        commence_time_to=args.commence_time_to,
    )
    endpoint = f"{API_HOST}/v4/sports/{request.sport}/odds"
    public_parameters = request.public_parameters()
    public_url = f"{endpoint}?{urlencode(public_parameters)}"
    ingested_at_utc = utc_now_iso()

    try:
        response = requests.get(
            endpoint,
            params=request.secure_parameters(api_key),
            timeout=args.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        output_root = Path(args.output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "provider": "the_odds_api_v4",
            "ingested_at_utc": ingested_at_utc,
            "endpoint": f"/v4/sports/{request.sport}/odds",
            "request_parameters_without_api_key": public_parameters,
            "error_type": type(exc).__name__,
            "error": str(exc).replace(api_key, "[REDACTED]"),
            "request_sent": True,
        }
        failure_path = output_root / "last-request-failure.json"
        failure_path.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(str(failure_path), file=sys.stderr)
        raise SystemExit(1) from exc

    directory = archive_current_odds_snapshot(
        output_root=Path(args.output_root),
        request=request,
        raw_response_bytes=response.content,
        response_headers=response.headers,
        ingested_at_utc=ingested_at_utc,
        http_status=response.status_code,
        response_url_without_api_key=public_url,
    )
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "snapshot_directory": str(directory),
                "normalized_rows": manifest["normalized"]["rows"],
                "unique_events": manifest["normalized"]["unique_events"],
                "unique_bookmakers": manifest["normalized"]["unique_bookmakers"],
                "quota": manifest["response_headers"]["quota"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
