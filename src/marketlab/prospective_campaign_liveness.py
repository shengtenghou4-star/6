from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def snapshot_time(directory_name: str) -> datetime:
    prefix = directory_name.split("__", 1)[0]
    try:
        return datetime.strptime(prefix, "%Y%m%dT%H%M%S_%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"invalid snapshot directory timestamp: {directory_name}") from exc


def nested(manifest: dict[str, Any], *keys: str) -> Any:
    value: Any = manifest
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"manifest missing path: {'/'.join(keys)}")
        value = value[key]
    return value


def false_claim(manifest: dict[str, Any], *paths: tuple[str, ...]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        value: Any = manifest
        found = True
        for key in path:
            if not isinstance(value, dict) or key not in value:
                found = False
                break
            value = value[key]
        if found and bool(value):
            failures.append("/".join(path))
    return failures


def audit_campaign_liveness(
    sequence: dict[str, Any],
    shadow: dict[str, Any],
    *,
    now_utc: str,
    campaign_start_utc: str,
    campaign_end_utc: str,
    stale_after_hours: float,
    support_repaired: dict[str, Any] | None = None,
    canonical_timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = parse_utc(now_utc)
    start = parse_utc(campaign_start_utc)
    end = parse_utc(campaign_end_utc)
    if start >= end:
        raise ValueError("campaign start must precede campaign end")
    if stale_after_hours <= 0:
        raise ValueError("stale threshold must be positive")

    active = start <= now < end
    directories = list(sequence.get("snapshot_directories", []))
    failures: list[str] = []
    warnings: list[str] = []
    latest: datetime | None = None
    age_hours: float | None = None

    if not directories:
        failures.append("no_snapshot_directories")
    else:
        times = [snapshot_time(str(name)) for name in directories]
        latest = max(times)
        age_hours = (now - latest).total_seconds() / 3600.0
        if age_hours < -0.05:
            failures.append("latest_snapshot_is_in_future")
        if active and age_hours > stale_after_hours:
            failures.append("latest_snapshot_is_stale")

    if sequence.get("status") != "materialized":
        failures.append("sequence_not_materialized")
    if shadow.get("status") != "scored":
        failures.append("shadow_not_scored")

    sequence_quote_sha = nested(sequence, "outputs", "quote_ledger", "sha256")
    shadow_quote_sha = nested(shadow, "inputs", "quote_ledger", "sha256")
    sequence_transition_sha = nested(sequence, "outputs", "transitions", "sha256")
    shadow_transition_sha = nested(shadow, "inputs", "transitions", "sha256")
    shadow_score_sha = nested(shadow, "outputs", "per_book_scores", "sha256")
    if sequence_quote_sha != shadow_quote_sha:
        failures.append("sequence_shadow_quote_hash_mismatch")
    if sequence_transition_sha != shadow_transition_sha:
        failures.append("sequence_shadow_transition_hash_mismatch")

    adapters: dict[str, Any] = {}
    for name, manifest in (
        ("support_repaired", support_repaired),
        ("canonical_timing", canonical_timing),
    ):
        if manifest is None:
            adapters[name] = {"available": False}
            continue
        source_sha = nested(manifest, "source", "per_book_scores", "sha256")
        aligned = source_sha == shadow_score_sha
        if not aligned:
            failures.append(f"{name}_source_hash_mismatch")
        adapters[name] = {
            "available": True,
            "status": manifest.get("status"),
            "source_score_sha256": source_sha,
            "aligned_to_original_shadow": aligned,
            "output_candidate_rows": manifest.get("outputs", {})
            .get("event_candidates", {})
            .get("rows"),
        }

    forbidden_true: list[str] = []
    forbidden_true.extend(
        false_claim(
            shadow,
            ("policy", "match_outcomes_used"),
            ("policy", "closing_targets_used"),
        )
    )
    for name, manifest in (
        ("support_repaired", support_repaired),
        ("canonical_timing", canonical_timing),
    ):
        if manifest is None:
            continue
        claims = false_claim(
            manifest,
            ("diagnostics", "match_outcomes_used"),
            ("diagnostics", "closing_targets_used"),
            ("policy", "match_outcomes_used"),
            ("policy", "closing_targets_used"),
        )
        forbidden_true.extend(f"{name}:{claim}" for claim in claims)
    if forbidden_true:
        failures.append("outcome_or_closing_use_claimed_during_scoring")

    if not active:
        warnings.append("campaign_window_inactive")
    healthy = not failures
    return {
        "schema_version": 1,
        "status": "healthy" if healthy else "unhealthy",
        "checked_at_utc": now.isoformat(),
        "campaign": {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "active": active,
            "stale_after_hours": float(stale_after_hours),
        },
        "freshness": {
            "snapshot_directories": int(len(directories)),
            "latest_snapshot_utc": latest.isoformat() if latest else None,
            "latest_snapshot_age_hours": age_hours,
            "fresh_within_threshold": bool(
                latest is not None
                and age_hours is not None
                and age_hours <= stale_after_hours
                and age_hours >= -0.05
            ),
        },
        "alignment": {
            "sequence_quote_sha256": sequence_quote_sha,
            "shadow_quote_sha256": shadow_quote_sha,
            "sequence_transition_sha256": sequence_transition_sha,
            "shadow_transition_sha256": shadow_transition_sha,
            "shadow_per_book_score_sha256": shadow_score_sha,
            "quote_hash_aligned": sequence_quote_sha == shadow_quote_sha,
            "transition_hash_aligned": sequence_transition_sha == shadow_transition_sha,
            "adapters": adapters,
        },
        "outcome_blind": True,
        "forbidden_true_claims": forbidden_true,
        "failures": failures,
        "warnings": warnings,
    }
