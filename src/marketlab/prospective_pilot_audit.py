from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .prospective_sequence_states import discover_snapshot_directories, verify_snapshot


OUTCOMES = ("home", "draw", "away")
DRAW_LABELS = {"draw", "tie", "x"}


@dataclass(frozen=True, slots=True)
class PilotAuditPolicy:
    required_market: str = "h2h"
    maximum_regions: int = 1
    maximum_named_bookmakers: int = 10
    maximum_nonempty_request_cost: int = 1
    minimum_complete_books_per_event: int = 4
    minimum_fraction_events_with_book_coverage: float = 0.80
    minimum_effective_update_timestamp_fraction: float = 0.80
    minimum_precommence_event_fraction: float = 0.95


def _truthy(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "yes"}


def _csv_values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(
        item.strip()
        for item in str(value).split(",")
        if item and item.strip()
    )


def _parse_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _canonical_outcome(name: Any, home_team: Any, away_team: Any) -> str | None:
    value = str(name).strip().casefold()
    home = str(home_team).strip().casefold()
    away = str(away_team).strip().casefold()
    if value and value == home:
        return "home"
    if value and value == away:
        return "away"
    if value in DRAW_LABELS:
        return "draw"
    return None


def _scan_secret(directory: Path, secret_value: str | None) -> dict[str, Any]:
    suspicious_files: list[str] = []
    exact_secret_files: list[str] = []
    secret_bytes = secret_value.encode("utf-8") if secret_value else None
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        data = path.read_bytes()
        lowered = data.lower()
        if b"apikey=" in lowered or b'"apikey"' in lowered or b"api_key" in lowered:
            suspicious_files.append(path.name)
        if secret_bytes and secret_bytes in data:
            exact_secret_files.append(path.name)
    return {
        "api_key_parameter_markers": suspicious_files,
        "exact_secret_matches": exact_secret_files,
        "passed": not suspicious_files and not exact_secret_files,
    }


def _group_quote_states(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    rows: list[dict[str, Any]] = []
    diagnostics = {
        "groups_seen": 0,
        "complete_h2h_groups": 0,
        "incomplete_groups": 0,
        "ambiguous_groups": 0,
        "invalid_price_groups": 0,
        "invalid_team_or_event_groups": 0,
    }
    keys = ["event_id", "bookmaker_key", "market_key"]
    for (event_id, bookmaker_key, market_key), group in frame.groupby(
        keys, sort=True, dropna=False
    ):
        diagnostics["groups_seen"] += 1
        event_text = str(event_id).strip()
        bookmaker_text = str(bookmaker_key).strip()
        home_values = group["home_team"].dropna().astype(str).unique().tolist()
        away_values = group["away_team"].dropna().astype(str).unique().tolist()
        commence_values = group["commence_time"].dropna().astype(str).unique().tolist()
        if (
            not event_text
            or not bookmaker_text
            or len(home_values) != 1
            or len(away_values) != 1
            or len(commence_values) != 1
        ):
            diagnostics["invalid_team_or_event_groups"] += 1
            continue
        canonical = [
            _canonical_outcome(value, home_values[0], away_values[0])
            for value in group["outcome_name"]
        ]
        if any(value is None for value in canonical) or len(set(canonical)) != len(canonical):
            diagnostics["ambiguous_groups"] += 1
            continue
        if len(canonical) != 3 or set(canonical) != set(OUTCOMES):
            diagnostics["incomplete_groups"] += 1
            continue
        prices = pd.to_numeric(group["price_decimal"], errors="coerce")
        valid_price_flags = group["price_valid_decimal"].map(_truthy)
        if (
            prices.isna().any()
            or not np.isfinite(prices.to_numpy(float)).all()
            or (prices <= 1.0).any()
            or not valid_price_flags.all()
        ):
            diagnostics["invalid_price_groups"] += 1
            continue
        bookmaker_updates = pd.to_datetime(
            group["bookmaker_last_update"], utc=True, errors="coerce"
        )
        market_updates = pd.to_datetime(
            group["market_last_update"], utc=True, errors="coerce"
        )
        effective_update = market_updates.dropna()
        if effective_update.empty:
            effective_update = bookmaker_updates.dropna()
        commence = pd.to_datetime(commence_values[0], utc=True, errors="coerce")
        rows.append(
            {
                "event_id": event_text,
                "bookmaker_key": bookmaker_text,
                "market_key": str(market_key),
                "commence_time": commence,
                "effective_update_time": effective_update.max()
                if not effective_update.empty
                else pd.NaT,
            }
        )
        diagnostics["complete_h2h_groups"] += 1
    return pd.DataFrame(rows), diagnostics


def audit_snapshot_directory(
    directory: Path,
    *,
    policy: PilotAuditPolicy = PilotAuditPolicy(),
    secret_value: str | None = None,
) -> dict[str, Any]:
    evidence = verify_snapshot(directory)
    manifest = evidence.manifest
    normalized_path = directory / str(manifest["normalized"]["path"])
    frame = pd.read_csv(normalized_path, low_memory=False)
    required_columns = {
        "event_id",
        "sport_key",
        "commence_time",
        "commence_time_valid",
        "home_team",
        "away_team",
        "bookmaker_key",
        "bookmaker_title",
        "bookmaker_last_update",
        "bookmaker_last_update_valid",
        "market_key",
        "market_last_update",
        "market_last_update_valid",
        "outcome_name",
        "price_decimal",
        "price_valid_decimal",
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"normalized snapshot missing columns: {missing}")

    request_parameters = manifest.get("request", {}).get("parameters", {})
    markets = _csv_values(request_parameters.get("markets"))
    regions = _csv_values(request_parameters.get("regions"))
    bookmakers = _csv_values(request_parameters.get("bookmakers"))
    scope_checks = {
        "h2h_only": markets == (policy.required_market,),
        "exactly_one_location_selector": bool(regions) != bool(bookmakers),
        "one_region_maximum": bool(bookmakers) or len(regions) <= policy.maximum_regions,
        "named_bookmaker_maximum": bool(regions)
        or (1 <= len(bookmakers) <= policy.maximum_named_bookmakers),
    }

    quota = manifest.get("response_headers", {}).get("quota", {})
    quota_parsed = {
        "remaining": _parse_int(quota.get("x-requests-remaining")),
        "used": _parse_int(quota.get("x-requests-used")),
        "last": _parse_int(quota.get("x-requests-last")),
    }
    quota_checks = {
        "headers_present_and_integer": all(
            value is not None for value in quota_parsed.values()
        ),
        "nonnegative": all(
            value is not None and value >= 0 for value in quota_parsed.values()
        ),
        "pilot_cost_at_most_one": bool(
            quota_parsed["last"] is not None
            and quota_parsed["last"] <= policy.maximum_nonempty_request_cost
        ),
    }

    secret_scan = _scan_secret(directory, secret_value)
    request_url = str(manifest.get("response_url_without_api_key", ""))
    secret_checks = {
        "evidence_scan_passed": secret_scan["passed"],
        "response_url_has_no_api_key_parameter": "apikey" not in request_url.casefold(),
    }

    market_frame = frame[frame["market_key"].astype(str) == policy.required_market].copy()
    quote_states, quote_diagnostics = _group_quote_states(market_frame)
    ingestion = pd.to_datetime(evidence.ingested_at, utc=True)
    total_events = int(market_frame["event_id"].astype(str).nunique())
    complete_events = int(quote_states["event_id"].nunique()) if not quote_states.empty else 0
    if quote_states.empty:
        coverage_by_event = pd.Series(dtype=float)
        effective_update_fraction = 0.0
        precommence_fraction = 0.0
        update_age_seconds = pd.Series(dtype=float)
    else:
        coverage_by_event = quote_states.groupby("event_id")["bookmaker_key"].nunique()
        effective_update_fraction = float(
            quote_states["effective_update_time"].notna().mean()
        )
        precommence_fraction = float(
            (quote_states["commence_time"] > ingestion).mean()
        )
        update_age_seconds = (
            ingestion - quote_states["effective_update_time"]
        ).dt.total_seconds().dropna()
    covered_events = int(
        (coverage_by_event >= policy.minimum_complete_books_per_event).sum()
    ) if not coverage_by_event.empty else 0
    event_coverage_fraction = (
        float(covered_events / total_events) if total_events else 0.0
    )
    normalized_manifest = manifest.get("normalized", {})
    reconciliation_checks = {
        "row_count_matches": int(normalized_manifest.get("rows", -1)) == len(frame),
        "unique_event_count_matches": int(
            normalized_manifest.get("unique_events", -1)
        )
        == frame["event_id"].astype(str).nunique(),
        "unique_bookmaker_count_matches": int(
            normalized_manifest.get("unique_bookmakers", -1)
        )
        == frame["bookmaker_key"].astype(str).nunique(),
        "unique_market_count_matches": int(
            normalized_manifest.get("unique_markets", -1)
        )
        == frame["market_key"].astype(str).nunique(),
    }
    diagnostics = manifest.get("diagnostics", {})
    invalid_diagnostics_total = sum(
        int(diagnostics.get(key, 0) or 0)
        for key in (
            "malformed_events",
            "malformed_bookmakers",
            "malformed_markets",
            "malformed_outcomes",
            "invalid_commence_times",
            "invalid_bookmaker_update_times",
            "invalid_market_update_times",
            "invalid_decimal_prices",
        )
    )
    coverage_checks = {
        "nonempty_events": total_events > 0,
        "at_least_one_complete_quote_state": not quote_states.empty,
        "event_book_coverage_fraction": event_coverage_fraction
        >= policy.minimum_fraction_events_with_book_coverage,
        "effective_update_timestamp_fraction": effective_update_fraction
        >= policy.minimum_effective_update_timestamp_fraction,
        "precommence_event_fraction": precommence_fraction
        >= policy.minimum_precommence_event_fraction,
        "normalization_invalid_diagnostics_zero": invalid_diagnostics_total == 0,
    }
    integrity_checks = {
        "provider_matches": manifest.get("provider") == "the_odds_api_v4",
        "http_status_200": int(manifest.get("http_status", 0)) == 200,
        "raw_sha_verified": True,
        "normalized_reconciliation": all(reconciliation_checks.values()),
    }

    connected = bool(
        all(integrity_checks.values())
        and all(secret_checks.values())
        and quota_checks["headers_present_and_integer"]
        and quota_checks["nonnegative"]
        and len(frame) > 0
    )
    suitable_for_repeated_pilot = bool(
        connected
        and all(scope_checks.values())
        and all(quota_checks.values())
        and all(coverage_checks.values())
    )
    blocking_reasons: list[str] = []
    for section, checks in (
        ("integrity", integrity_checks),
        ("scope", scope_checks),
        ("quota", quota_checks),
        ("secret", secret_checks),
        ("coverage", coverage_checks),
    ):
        blocking_reasons.extend(
            f"{section}.{name}" for name, passed in checks.items() if not passed
        )

    return {
        "status": "completed",
        "snapshot": {
            "directory": str(directory),
            "snapshot_id": evidence.snapshot_id,
            "ingested_at_utc": evidence.ingested_at.isoformat(),
            "sport": manifest.get("request", {}).get("sport"),
            "raw_sha256": evidence.raw_sha256,
            "normalized_rows": int(len(frame)),
        },
        "policy": asdict(policy),
        "request_scope": {
            "markets": list(markets),
            "regions": list(regions),
            "bookmakers": list(bookmakers),
            "checks": scope_checks,
        },
        "quota": {**quota_parsed, "checks": quota_checks},
        "secret_safety": {**secret_scan, "checks": secret_checks},
        "integrity": {
            "checks": integrity_checks,
            "reconciliation_checks": reconciliation_checks,
        },
        "coverage": {
            "events": total_events,
            "events_with_any_complete_h2h_state": complete_events,
            "events_with_minimum_book_coverage": covered_events,
            "fraction_events_with_minimum_book_coverage": event_coverage_fraction,
            "complete_h2h_quote_states": int(len(quote_states)),
            "complete_books_per_event_min": int(coverage_by_event.min())
            if not coverage_by_event.empty
            else 0,
            "complete_books_per_event_median": float(coverage_by_event.median())
            if not coverage_by_event.empty
            else 0.0,
            "complete_books_per_event_max": int(coverage_by_event.max())
            if not coverage_by_event.empty
            else 0,
            "effective_update_timestamp_fraction": effective_update_fraction,
            "precommence_quote_state_fraction": precommence_fraction,
            "effective_update_age_seconds_median": float(update_age_seconds.median())
            if not update_age_seconds.empty
            else None,
            "effective_update_age_seconds_max": float(update_age_seconds.max())
            if not update_age_seconds.empty
            else None,
            "quote_group_diagnostics": quote_diagnostics,
            "normalization_invalid_diagnostics_total": invalid_diagnostics_total,
            "checks": coverage_checks,
        },
        "decisions": {
            "authenticated_source_connected": connected,
            "suitable_for_repeated_snapshot_pilot": suitable_for_repeated_pilot,
            "suitable_for_untouched_repricing_clv_now": False,
            "untouched_repricing_clv_reason": (
                "one authenticated snapshot can verify connectivity, coverage and timestamps but cannot form prospective transitions or elapsed closing targets"
            ),
        },
        "blocking_reasons": blocking_reasons,
    }


def audit_snapshot_root(
    root: Path,
    *,
    policy: PilotAuditPolicy = PilotAuditPolicy(),
    secret_value: str | None = None,
) -> dict[str, Any]:
    directories = discover_snapshot_directories(root)
    if len(directories) != 1:
        raise ValueError(
            f"first authenticated pilot must contain exactly one snapshot, found {len(directories)}"
        )
    return audit_snapshot_directory(
        directories[0], policy=policy, secret_value=secret_value
    )
