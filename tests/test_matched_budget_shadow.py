from __future__ import annotations

import pandas as pd
import pytest

from marketlab.matched_budget_shadow import (
    MatchedBudgetPolicy,
    build_matched_budget_shadow,
)


def fixture(rows: int = 40) -> pd.DataFrame:
    output = []
    for index in range(rows):
        output.append(
            {
                "event_id": f"event-{index:03d}",
                "realized_snapshot_id": "snapshot-new",
                "realized_snapshot_ingested_at": "2026-07-19T09:47:00Z",
                "supported_closing_cutoff_hours": 24,
                "bookmaker_key": f"book-{index % 5}",
                "raw_candidate_outcome": ("home", "draw", "away")[index % 3],
                "raw_candidate_score": float(index + 1),
                "action_rank_score_for_raw_candidate": float(rows - index),
            }
        )
    output.append(
        {
            "event_id": "old-event",
            "realized_snapshot_id": "snapshot-old",
            "realized_snapshot_ingested_at": "2026-07-19T06:59:59Z",
            "supported_closing_cutoff_hours": 24,
            "bookmaker_key": "old-book",
            "raw_candidate_outcome": "home",
            "raw_candidate_score": 999.0,
            "action_rank_score_for_raw_candidate": 999.0,
        }
    )
    return pd.DataFrame(output)


def test_builds_matched_five_percent_policies_after_activation() -> None:
    ledger, diagnostics = build_matched_budget_shadow(
        fixture(),
        MatchedBudgetPolicy("2026-07-19T07:00:00Z", fraction=0.05),
    )
    assert len(ledger) == 40
    assert diagnostics["pre_activation_rows_excluded"] == 1
    assert diagnostics["raw_selected_rows"] == 2
    assert diagnostics["residual_selected_rows"] == 2
    raw_events = set(ledger.loc[ledger["raw_matched_selected"], "event_id"])
    residual_events = set(
        ledger.loc[ledger["residual_challenger_selected"], "event_id"]
    )
    assert raw_events == {"event-038", "event-039"}
    assert residual_events == {"event-000", "event-001"}
    assert diagnostics["same_candidate_identity_by_construction"] is True
    assert ledger["research_only"].all()
    assert ledger["no_execution"].all()


def test_selection_is_independent_within_snapshot_and_cutoff() -> None:
    frame = pd.concat(
        [
            fixture(20).iloc[:-1],
            fixture(20).iloc[:-1].assign(
                event_id=lambda x: "second-" + x["event_id"],
                realized_snapshot_id="snapshot-second",
                supported_closing_cutoff_hours=12,
            ),
        ],
        ignore_index=True,
    )
    ledger, diagnostics = build_matched_budget_shadow(
        frame,
        MatchedBudgetPolicy("2026-07-19T07:00:00Z", fraction=0.05),
    )
    assert diagnostics["snapshot_cutoff_groups"] == 2
    assert diagnostics["raw_selected_rows"] == 2
    assert diagnostics["residual_selected_rows"] == 2


def test_nonpositive_scores_are_not_selected() -> None:
    frame = fixture(20).iloc[:-1].copy()
    frame["raw_candidate_score"] = -1.0
    frame["action_rank_score_for_raw_candidate"] = -2.0
    ledger, diagnostics = build_matched_budget_shadow(
        frame,
        MatchedBudgetPolicy("2026-07-19T07:00:00Z", fraction=0.05),
    )
    assert not ledger["raw_matched_selected"].any()
    assert not ledger["residual_challenger_selected"].any()
    assert diagnostics["selection_jaccard"] == 1.0


def test_invalid_activation_and_missing_columns_fail() -> None:
    with pytest.raises(ValueError, match="activation_utc"):
        build_matched_budget_shadow(fixture(), MatchedBudgetPolicy("not-a-date"))
    with pytest.raises(ValueError, match="missing columns"):
        build_matched_budget_shadow(
            fixture().drop(columns=["raw_candidate_score"]),
            MatchedBudgetPolicy("2026-07-19T07:00:00Z"),
        )
