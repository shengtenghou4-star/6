from __future__ import annotations

import pandas as pd
import pytest

from marketlab.support_repaired_shadow import (
    SupportRepairPolicy,
    prepare_support_repaired_records,
)


def fixture() -> pd.DataFrame:
    rows = []
    for index, (ingested, hours, active) in enumerate(
        [
            ("2026-07-19T11:59:00Z", 47.0, 3),
            ("2026-07-19T12:01:00Z", 47.0, 3),
            ("2026-07-19T12:01:00Z", 47.5, 2),
            ("2026-07-19T12:01:00Z", 44.0, 3),
        ]
    ):
        rows.append(
            {
                "event_id": "event-1",
                "bookmaker_key": f"book-{index}",
                "market_key": "h2h",
                "context_snapshot_id": "context-1",
                "realized_snapshot_id": f"realized-{index}",
                "realized_snapshot_ingested_at": ingested,
                "supported_closing_cutoff_hours": 48,
                "hours_to_commence_scaled_71": hours / 71.0,
                "active_other_books_scaled_31": active / 31.0,
                "raw_candidate_score": 0.01 + index / 1000,
                "action_rank_score_for_raw_candidate": 0.02 + index / 1000,
            }
        )
    return pd.DataFrame(rows)


def policy() -> SupportRepairPolicy:
    return SupportRepairPolicy("2026-07-19T12:00:00Z")


def test_filters_activation_and_timing_then_normalizes_panel_coverage() -> None:
    repaired, diagnostics = prepare_support_repaired_records(fixture(), policy())
    assert diagnostics["pre_activation_rows_excluded"] == 1
    assert diagnostics["post_activation_rows"] == 3
    assert diagnostics["timing_supported_rows"] == 2
    assert diagnostics["timing_excluded_rows"] == 1
    assert diagnostics["panel_peer_capacity"] == {
        "minimum": 3,
        "median": 3.0,
        "maximum": 3,
    }
    assert repaired["active_peer_book_count"].tolist() == [3, 2]
    assert repaired["active_other_books_scaled_31"].tolist() == pytest.approx(
        [1.0, 2.0 / 3.0]
    )
    assert repaired["original_active_other_books_scaled_31"].tolist() == pytest.approx(
        [3.0 / 31.0, 2.0 / 31.0]
    )
    assert repaired["support_repair_research_only"].all()
    assert repaired["support_repair_no_execution"].all()


def test_no_post_activation_rows_is_recorded() -> None:
    repaired, diagnostics = prepare_support_repaired_records(
        fixture(), SupportRepairPolicy("2026-07-20T00:00:00Z")
    )
    assert repaired.empty
    assert diagnostics["status"] == "no_post_activation_rows"


def test_forbids_result_fields() -> None:
    frame = fixture().assign(won=False)
    with pytest.raises(ValueError, match="result or settlement"):
        prepare_support_repaired_records(frame, policy())


def test_rejects_noninteger_active_peer_reconstruction() -> None:
    frame = fixture()
    frame.loc[1, "active_other_books_scaled_31"] = 2.5 / 31.0
    with pytest.raises(ValueError, match="does not reconcile"):
        prepare_support_repaired_records(frame, policy())


def test_invalid_policy_fails() -> None:
    with pytest.raises(ValueError, match="activation_utc"):
        prepare_support_repaired_records(fixture(), SupportRepairPolicy("invalid"))
    with pytest.raises(ValueError, match="cutoff_tolerance"):
        prepare_support_repaired_records(
            fixture(),
            SupportRepairPolicy("2026-07-19T12:00:00Z", cutoff_tolerance_hours=0),
        )
