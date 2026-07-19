from __future__ import annotations

from copy import deepcopy

from marketlab.prospective_campaign_liveness import audit_campaign_liveness


def sequence() -> dict:
    return {
        "status": "materialized",
        "snapshot_directories": [
            "20260719T110022_555695Z__soccer_korea_kleague1__abc",
            "20260719T140100_000000Z__soccer_sweden_allsvenskan__def",
        ],
        "outputs": {
            "quote_ledger": {"sha256": "q" * 64},
            "transitions": {"sha256": "t" * 64},
        },
    }


def shadow() -> dict:
    return {
        "status": "scored",
        "inputs": {
            "quote_ledger": {"sha256": "q" * 64},
            "transitions": {"sha256": "t" * 64},
        },
        "outputs": {"per_book_scores": {"sha256": "s" * 64}},
        "policy": {"match_outcomes_used": False},
    }


def adapter() -> dict:
    return {
        "status": "scored",
        "source": {"per_book_scores": {"sha256": "s" * 64}},
        "diagnostics": {
            "match_outcomes_used": False,
            "closing_targets_used": False,
        },
        "outputs": {"event_candidates": {"rows": 7}},
    }


def test_healthy_fresh_aligned_state() -> None:
    result = audit_campaign_liveness(
        sequence(),
        shadow(),
        now_utc="2026-07-19T15:00:00Z",
        campaign_start_utc="2026-07-19T06:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        stale_after_hours=4.5,
        support_repaired=adapter(),
        canonical_timing=adapter(),
    )
    assert result["status"] == "healthy"
    assert result["freshness"]["latest_snapshot_age_hours"] == 0.9833333333333333
    assert result["alignment"]["quote_hash_aligned"] is True
    assert result["alignment"]["adapters"]["canonical_timing"][
        "aligned_to_original_shadow"
    ] is True


def test_stale_active_campaign_fails() -> None:
    result = audit_campaign_liveness(
        sequence(),
        shadow(),
        now_utc="2026-07-19T19:00:00Z",
        campaign_start_utc="2026-07-19T06:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        stale_after_hours=4.5,
    )
    assert result["status"] == "unhealthy"
    assert "latest_snapshot_is_stale" in result["failures"]


def test_hash_mismatch_fails() -> None:
    changed = deepcopy(shadow())
    changed["inputs"]["quote_ledger"]["sha256"] = "x" * 64
    result = audit_campaign_liveness(
        sequence(),
        changed,
        now_utc="2026-07-19T15:00:00Z",
        campaign_start_utc="2026-07-19T06:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        stale_after_hours=4.5,
    )
    assert "sequence_shadow_quote_hash_mismatch" in result["failures"]


def test_adapter_source_mismatch_fails() -> None:
    changed = adapter()
    changed["source"]["per_book_scores"]["sha256"] = "z" * 64
    result = audit_campaign_liveness(
        sequence(),
        shadow(),
        now_utc="2026-07-19T15:00:00Z",
        campaign_start_utc="2026-07-19T06:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        stale_after_hours=4.5,
        support_repaired=changed,
    )
    assert "support_repaired_source_hash_mismatch" in result["failures"]


def test_outcome_use_claim_fails() -> None:
    changed = adapter()
    changed["diagnostics"]["match_outcomes_used"] = True
    result = audit_campaign_liveness(
        sequence(),
        shadow(),
        now_utc="2026-07-19T15:00:00Z",
        campaign_start_utc="2026-07-19T06:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        stale_after_hours=4.5,
        canonical_timing=changed,
    )
    assert "outcome_or_closing_use_claimed_during_scoring" in result["failures"]
