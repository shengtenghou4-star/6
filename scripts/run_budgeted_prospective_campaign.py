from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from marketlab.prospective_campaign import (
    CampaignPolicy,
    select_near_event_sports,
    utc_iso,
)
from marketlab.prospective_odds import (
    SnapshotRequest,
    archive_current_odds_snapshot,
    parse_csv_tuple,
    utc_now_iso,
)
from marketlab.prospective_pilot_audit import audit_snapshot_directory

API_HOST = "https://api.the-odds-api.com"
API_KEY_ENV = "THE_ODDS_API_KEY"


def _redact(value: str, api_key: str) -> str:
    return value.replace(api_key, "[REDACTED]")


def _safe_json_request(
    session: requests.Session,
    *,
    endpoint: str,
    params: dict[str, str],
    api_key: str,
    timeout_seconds: float,
) -> tuple[requests.Response, Any]:
    try:
        response = session.get(
            endpoint,
            params={**params, "apiKey": api_key},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        return response, response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(_redact(str(exc), api_key)) from exc


def _quota_headers(response: requests.Response) -> dict[str, str | None]:
    lowered = {key.casefold(): value for key, value in response.headers.items()}
    return {
        "x-requests-remaining": lowered.get("x-requests-remaining"),
        "x-requests-used": lowered.get("x-requests-used"),
        "x-requests-last": lowered.get("x-requests-last"),
    }


def _parse_credit(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select near-event soccer competitions with quota-free scouting and collect a bounded h2h snapshot campaign run."
    )
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--sports", default="")
    parser.add_argument("--max-sports", type=int, default=4)
    parser.add_argument("--horizon-hours", type=float, default=60.0)
    parser.add_argument("--region", default="uk")
    parser.add_argument("--max-run-credits", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()

    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise SystemExit(
            f"missing required environment secret {API_KEY_ENV}; no request was sent"
        )

    policy_kwargs: dict[str, Any] = {
        "maximum_paid_sports_per_run": args.max_sports,
        "horizon_hours": args.horizon_hours,
        "region": args.region,
        "maximum_paid_credits_per_run": args.max_run_credits,
    }
    requested_sports = parse_csv_tuple(args.sports)
    if requested_sports:
        policy_kwargs["sports"] = requested_sports
    policy = CampaignPolicy(**policy_kwargs)

    output_root = Path(args.output_root)
    scouting_root = output_root / "event-scouting"
    snapshot_root = output_root / "snapshots"
    audit_root = output_root / "audits"
    for path in (output_root, scouting_root, snapshot_root, audit_root):
        path.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    horizon_end = now + timedelta(hours=policy.horizon_hours)
    commence_from = utc_iso(now)
    commence_to = utc_iso(horizon_end)
    session = requests.Session()

    try:
        sports_response, sports_payload = _safe_json_request(
            session,
            endpoint=f"{API_HOST}/v4/sports",
            params={},
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        if not isinstance(sports_payload, list):
            raise RuntimeError("active sports response root was not a list")
        active_records = [
            item
            for item in sports_payload
            if isinstance(item, dict)
            and bool(item.get("active", True))
            and not bool(item.get("has_outrights", False))
        ]
        active_keys = {
            str(item.get("key", "")).strip()
            for item in active_records
            if str(item.get("key", "")).strip()
        }
        active_evidence = {
            "endpoint": "/v4/sports",
            "observed_at_utc": utc_now_iso(),
            "quota": _quota_headers(sports_response),
            "active_sports": active_records,
        }
        (scouting_root / "active-sports.json").write_text(
            json.dumps(active_evidence, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        events_by_sport: dict[str, Any] = {}
        event_scouting: dict[str, Any] = {}
        for sport in policy.sports:
            if sport not in active_keys:
                event_scouting[sport] = {
                    "active": False,
                    "eligible_events": 0,
                }
                continue
            event_endpoint = f"{API_HOST}/v4/sports/{sport}/events"
            event_params = {
                "dateFormat": "iso",
                "commenceTimeFrom": commence_from,
                "commenceTimeTo": commence_to,
            }
            event_response, event_payload = _safe_json_request(
                session,
                endpoint=event_endpoint,
                params=event_params,
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            events_by_sport[sport] = event_payload
            raw_event_path = scouting_root / f"{sport}.json"
            raw_event_path.write_bytes(event_response.content)
            event_scouting[sport] = {
                "active": True,
                "endpoint": f"/v4/sports/{sport}/events",
                "request_parameters_without_api_key": event_params,
                "raw_path": raw_event_path.name,
                "raw_bytes": len(event_response.content),
                "events_returned": len(event_payload)
                if isinstance(event_payload, list)
                else None,
                "quota": _quota_headers(event_response),
            }

        selections = select_near_event_sports(
            active_sport_keys=sorted(active_keys),
            events_by_sport=events_by_sport,
            now=now,
            policy=policy,
        )

        snapshots: list[dict[str, Any]] = []
        total_paid_credits = 0
        for selection in selections:
            request = SnapshotRequest(
                sport=selection.sport_key,
                markets=(policy.market,),
                regions=(policy.region,),
                commence_time_from=commence_from,
                commence_time_to=commence_to,
            )
            endpoint = f"{API_HOST}/v4/sports/{selection.sport_key}/odds"
            public_parameters = request.public_parameters()
            response, _ = _safe_json_request(
                session,
                endpoint=endpoint,
                params=public_parameters,
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            ingested_at = utc_now_iso()
            public_url = f"{endpoint}?{urlencode(public_parameters)}"
            directory = archive_current_odds_snapshot(
                output_root=snapshot_root,
                request=request,
                raw_response_bytes=response.content,
                response_headers=response.headers,
                ingested_at_utc=ingested_at,
                http_status=response.status_code,
                response_url_without_api_key=public_url,
            )
            audit = audit_snapshot_directory(
                directory,
                secret_value=api_key,
            )
            audit_path = audit_root / f"{directory.name}.json"
            audit_path.write_text(
                json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            cost = _parse_credit(audit.get("quota", {}).get("last"))
            total_paid_credits += cost
            snapshots.append(
                {
                    "sport_key": selection.sport_key,
                    "snapshot_id": directory.name,
                    "raw_sha256": audit["snapshot"]["raw_sha256"],
                    "events": audit["coverage"]["events"],
                    "complete_h2h_quote_states": audit["coverage"][
                        "complete_h2h_quote_states"
                    ],
                    "minimum_books_per_event": audit["coverage"][
                        "complete_books_per_event_min"
                    ],
                    "request_cost": cost,
                    "quota_remaining": audit["quota"]["remaining"],
                    "authenticated_source_connected": audit["decisions"][
                        "authenticated_source_connected"
                    ],
                    "admitted_to_repeated_pilot": audit["decisions"][
                        "suitable_for_repeated_snapshot_pilot"
                    ],
                    "audit_path": str(audit_path.relative_to(output_root)),
                }
            )

        if total_paid_credits > policy.maximum_paid_credits_per_run:
            raise RuntimeError(
                "campaign paid-credit ceiling exceeded: "
                f"{total_paid_credits} > {policy.maximum_paid_credits_per_run}"
            )

        manifest = {
            "schema_version": 1,
            "status": "completed",
            "started_at_utc": utc_iso(now),
            "completed_at_utc": utc_now_iso(),
            "policy": {
                "sports": list(policy.sports),
                "maximum_paid_sports_per_run": policy.maximum_paid_sports_per_run,
                "horizon_hours": policy.horizon_hours,
                "region": policy.region,
                "market": policy.market,
                "maximum_paid_credits_per_run": policy.maximum_paid_credits_per_run,
            },
            "scouting_window": {
                "commence_time_from": commence_from,
                "commence_time_to": commence_to,
            },
            "event_scouting": event_scouting,
            "selected_sports": [selection.as_dict() for selection in selections],
            "snapshots": snapshots,
            "paid_requests": len(selections),
            "paid_credits": total_paid_credits,
            "research_only": True,
            "no_execution": True,
            "match_outcomes_used": False,
        }
        manifest_text = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        )
        if api_key in manifest_text or "apikey=" in manifest_text.casefold():
            raise RuntimeError("campaign manifest contains API key material")
        (output_root / "manifest.json").write_text(
            manifest_text, encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "selected_sports": [
                        selection.sport_key for selection in selections
                    ],
                    "snapshots": len(snapshots),
                    "paid_credits": total_paid_credits,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    except Exception as exc:
        failure = {
            "status": "failed",
            "failed_at_utc": utc_now_iso(),
            "error_type": type(exc).__name__,
            "error": _redact(str(exc), api_key),
            "research_only": True,
            "no_execution": True,
        }
        (output_root / "failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
