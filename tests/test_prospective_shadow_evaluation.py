from __future__ import annotations

import pandas as pd
import pytest

from marketlab.prospective_shadow_evaluation import (
    ProspectiveEvaluationPolicy,
    attach_closing_clv,
    evaluate_prospective_shadow,
    freeze_snapshot_strategies,
)


def fixture(
    n_events: int = 40,
    snapshots: tuple[str, ...] = ("s1", "s2"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = []
    closing = []
    for snapshot in snapshots:
        for index in range(n_events):
            outcome = ("home", "draw", "away")[index % 3]
            raw_score = float(index) / n_events
            action_score = raw_score + (0.5 if index % 5 == 0 else -0.05)
            candidates.append(
                {
                    "event_id": f"e{index}",
                    "bookmaker_key": "b1",
                    "market_key": "h2h",
                    "realized_snapshot_id": snapshot,
                    "realized_snapshot_ingested_at": "2025-12-31T12:00:00Z",
                    "raw_candidate_outcome": outcome,
                    "raw_candidate_score": raw_score,
                    "action_rank_score_for_raw_candidate": action_score,
                    "supported_closing_cutoff_hours": 12,
                    "research_only": True,
                    "no_execution": True,
                    "unvalidated_prospective_transfer": True,
                    "bundle_id": "bundle",
                    "bundle_manifest_sha256": "a" * 64,
                }
            )
            log_clv = {"home": -0.01, "draw": -0.01, "away": -0.01}
            log_clv[outcome] = 0.04 if index % 5 == 0 else 0.001
            fair_clv = {key: value / 3.0 for key, value in log_clv.items()}
            closing.append(
                {
                    "event_id": f"e{index}",
                    "bookmaker_key": "b1",
                    "market_key": "h2h",
                    "snapshot_id": snapshot,
                    "closing_snapshot_id": f"close-{snapshot}",
                    "closing_snapshot_ingested_at": "2026-01-01T00:00:00Z",
                    "commence_time": "2026-01-01T01:00:00Z",
                    **{
                        f"closing_log_odds_clv_{key}": value
                        for key, value in log_clv.items()
                    },
                    **{
                        f"closing_delta_{key}_p": value
                        for key, value in fair_clv.items()
                    },
                }
            )
    return pd.DataFrame(candidates), pd.DataFrame(closing)


def test_exact_join_and_deterministic_rank_only_strategy() -> None:
    candidates, closing = fixture()
    policy = ProspectiveEvaluationPolicy(
        minimum_candidates_per_snapshot_cutoff=20,
        minimum_unique_events=1,
        minimum_eligible_snapshot_cutoff_groups=1,
        minimum_unique_events_per_cutoff=0,
        bootstrap_replicates=200,
    )
    rows, report = evaluate_prospective_shadow(candidates, closing, policy)
    assert len(rows) == 80
    assert rows["action_traded"].sum() == 16
    assert rows["baseline_traded"].sum() == 16
    assert report["incremental_action_minus_baseline"]["mean"] > 0.0
    assert (
        report["action_rank_strategy"]["mean_trade_log_clv"]
        > report["baseline_strategy"]["mean_trade_log_clv"]
    )


def test_rejects_mixed_bundle_false_policy_and_outcome_fields() -> None:
    candidates, closing = fixture()
    candidates.loc[0, "bundle_id"] = "other"
    with pytest.raises(ValueError, match="one frozen bundle"):
        attach_closing_clv(candidates, closing)

    candidates.loc[0, "bundle_id"] = "bundle"
    candidates.loc[0, "research_only"] = False
    with pytest.raises(ValueError, match="policy flags"):
        attach_closing_clv(candidates, closing)

    candidates.loc[0, "research_only"] = True
    closing["winner"] = "home"
    with pytest.raises(ValueError, match="outcome fields are forbidden"):
        attach_closing_clv(candidates, closing)


def test_rejects_invalid_observation_close_commence_chronology() -> None:
    candidates, closing = fixture()
    closing.loc[0, "closing_snapshot_ingested_at"] = "2025-12-31T11:00:00Z"
    with pytest.raises(ValueError, match="chronology is invalid"):
        attach_closing_clv(candidates, closing)


def test_missing_exact_closing_target_is_rejected() -> None:
    candidates, closing = fixture()
    closing = closing.iloc[1:].copy()
    with pytest.raises(ValueError, match="missing exact closing targets"):
        attach_closing_clv(candidates, closing)


def test_undersized_snapshot_cutoff_groups_are_preserved_but_not_traded() -> None:
    candidates, closing = fixture(n_events=5, snapshots=("s1",))
    attached = attach_closing_clv(candidates, closing)
    rows = freeze_snapshot_strategies(
        attached,
        ProspectiveEvaluationPolicy(
            minimum_candidates_per_snapshot_cutoff=20,
        ),
    )
    assert len(rows) == 5
    assert not rows["eligible_snapshot_cutoff_group"].any()
    assert not rows["action_traded"].any()
    assert not rows["baseline_traded"].any()
