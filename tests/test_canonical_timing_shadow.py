from __future__ import annotations

import pandas as pd
import pytest

from marketlab.canonical_timing_shadow import (
    CanonicalTimingPolicy,
    prepare_canonical_timing_records,
)


def rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": ["e1", "e1", "e2", "e2"],
            "bookmaker_key": ["a", "b", "a", "b"],
            "market_key": ["h2h"] * 4,
            "context_snapshot_id": ["c1", "c1", "c2", "c2"],
            "realized_snapshot_id": ["s1", "s1", "s2", "s2"],
            "realized_snapshot_ingested_at": [
                "2026-07-19T15:10:00Z",
                "2026-07-19T15:10:00Z",
                "2026-07-19T14:59:00Z",
                "2026-07-19T15:20:00Z",
            ],
            "supported_closing_cutoff_hours": [24, 24, 12, 12],
            "hours_to_commence_scaled_71": [20 / 71, 20 / 71, 10 / 71, 10 / 71],
            "active_other_books_scaled_31": [18 / 31, 20 / 31, 19 / 31, 20 / 31],
            "raw_candidate_score": [0.1, 0.2, 0.3, 0.4],
            "action_rank_score_for_raw_candidate": [0.2, 0.3, 0.4, 0.5],
        }
    )


def policy() -> CanonicalTimingPolicy:
    return CanonicalTimingPolicy(activation_utc="2026-07-19T15:00:00Z")


def test_canonicalizes_time_and_normalizes_panel_coverage() -> None:
    prepared, diagnostics = prepare_canonical_timing_records(rows(), policy())
    assert len(prepared) == 3
    assert diagnostics["pre_activation_rows_excluded"] == 1
    assert diagnostics["globally_supported_rows"] == 3
    assert set(prepared["hours_to_commence_scaled_71"].round(12)) == {
        round(24 / 71, 12),
        round(12 / 71, 12),
    }
    event_one = prepared[prepared["event_id"] == "e1"].sort_values("bookmaker_key")
    assert event_one["active_peer_book_count"].tolist() == [18, 20]
    assert event_one["inferred_panel_peer_capacity"].tolist() == [20, 20]
    assert event_one["active_other_books_scaled_31"].tolist() == [0.9, 1.0]
    assert event_one["cutoff_distance_hours"].tolist() == [4.0, 4.0]
    assert prepared["canonical_timing_adapter_id"].nunique() == 1
    assert prepared["canonical_timing_research_only"].all()


def test_excludes_rows_outside_global_historical_support() -> None:
    frame = rows().iloc[[0]].copy()
    frame["hours_to_commence_scaled_71"] = 55 / 71
    prepared, diagnostics = prepare_canonical_timing_records(frame, policy())
    assert prepared.empty
    assert diagnostics["status"] == "no_globally_supported_rows"
    assert diagnostics["globally_excluded_rows"] == 1


def test_rejects_noncanonical_cutoff() -> None:
    frame = rows().iloc[[0]].copy()
    frame["supported_closing_cutoff_hours"] = 18
    prepared, diagnostics = prepare_canonical_timing_records(frame, policy())
    assert prepared.empty
    assert diagnostics["globally_excluded_rows"] == 1


def test_rejects_result_columns() -> None:
    frame = rows()
    frame["won"] = False
    with pytest.raises(ValueError, match="forbidden"):
        prepare_canonical_timing_records(frame, policy())


def test_rejects_duplicate_identity() -> None:
    frame = pd.concat([rows(), rows().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        prepare_canonical_timing_records(frame, policy())


def test_requires_integer_peer_count_reconstruction() -> None:
    frame = rows()
    frame.loc[0, "active_other_books_scaled_31"] = 18.2 / 31
    with pytest.raises(ValueError, match="integer"):
        prepare_canonical_timing_records(frame, policy())
