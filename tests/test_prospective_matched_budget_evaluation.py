from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketlab.prospective_matched_budget_evaluation import (
    CUTOFFS,
    CohortEvaluationPolicy,
    evaluate_frozen_campaign_policies,
    freeze_campaign_cohort_policies,
)


def policy(**overrides: object) -> CohortEvaluationPolicy:
    values = {
        "activation_utc": "2026-07-19T11:00:00Z",
        "campaign_end_utc": "2026-07-26T06:30:00Z",
        "minimum_collection_lead_hours": 3.25,
        "fraction": 0.05,
        "minimum_candidates": 80,
        "minimum_unique_events": 80,
        "minimum_selected_per_policy": 4,
        "minimum_candidates_per_cutoff": 20,
        "minimum_supported_cutoffs": 4,
        "bootstrap_replicates": 500,
        "bootstrap_seed": 17,
    }
    values.update(overrides)
    return CohortEvaluationPolicy(**values)


def candidate_fixture(rows_per_cutoff: int = 20) -> pd.DataFrame:
    rows = []
    index = 0
    for cutoff_index, cutoff in enumerate(CUTOFFS):
        for local in range(rows_per_cutoff):
            rows.append(
                {
                    "event_id": f"event-{index:04d}",
                    "realized_snapshot_id": f"snapshot-{index:04d}",
                    "realized_snapshot_ingested_at": "2026-07-20T00:00:00Z",
                    "commence_time": "2026-07-21T00:00:00Z",
                    "supported_closing_cutoff_hours": cutoff,
                    "bookmaker_key": f"book-{(local + cutoff_index) % 4}",
                    "market_key": "h2h",
                    "raw_candidate_outcome": ("home", "draw", "away")[local % 3],
                    "raw_candidate_score": float(local + 1),
                    "action_rank_score_for_raw_candidate": float(rows_per_cutoff - local),
                    "bundle_id": "bundle-v1",
                    "bundle_manifest_sha256": "a" * 64,
                    "research_only": True,
                    "no_execution": True,
                    "unvalidated_prospective_transfer": True,
                }
            )
            index += 1
    return pd.DataFrame(rows)


def closing_fixture(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in candidates.iterrows():
        local = int(str(row["event_id"]).split("-")[-1]) % 20
        # Residual selects local=0, raw selects local=19. Make residual positive
        # and raw negative while all non-selected rows are neutral.
        if local == 0:
            chosen_log = 0.08
            chosen_fair = 0.02
        elif local == 19:
            chosen_log = -0.04
            chosen_fair = -0.01
        else:
            chosen_log = 0.0
            chosen_fair = 0.0
        logs = {outcome: 0.0 for outcome in ("home", "draw", "away")}
        fairs = {outcome: 0.0 for outcome in ("home", "draw", "away")}
        logs[str(row["raw_candidate_outcome"])] = chosen_log
        fairs[str(row["raw_candidate_outcome"])] = chosen_fair
        rows.append(
            {
                "event_id": row["event_id"],
                "bookmaker_key": row["bookmaker_key"],
                "market_key": row["market_key"],
                "snapshot_id": row["realized_snapshot_id"],
                "closing_snapshot_id": f"close-{row['realized_snapshot_id']}",
                "closing_snapshot_ingested_at": "2026-07-20T03:00:00Z",
                "commence_time": row["commence_time"],
                **{f"closing_log_odds_clv_{key}": value for key, value in logs.items()},
                **{f"closing_delta_{key}_p": value for key, value in fairs.items()},
            }
        )
    return pd.DataFrame(rows)


def test_freezes_exact_full_cohort_quota_before_closing() -> None:
    candidates = candidate_fixture()
    raw, residual, diagnostics = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    assert len(raw) == 80
    assert int(raw["selected"].sum()) == 4
    assert int(residual["selected"].sum()) == 4
    assert not raw["closing_data_read_before_selection"].any()
    assert not residual["closing_data_read_before_selection"].any()
    assert diagnostics["closing_data_used_for_selection"] is False
    for cutoff in CUTOFFS:
        assert diagnostics["raw_policy"]["cutoffs"][f"T-{cutoff}h"]["quota"] == 1
        assert diagnostics["residual_policy"]["cutoffs"][f"T-{cutoff}h"]["quota"] == 1


def test_frozen_cohort_excludes_pre_activation_late_and_unmatured_rows() -> None:
    candidates = candidate_fixture()
    extras = candidates.iloc[:3].copy()
    extras["event_id"] = ["pre", "late", "unmatured"]
    extras["realized_snapshot_id"] = ["pre-s", "late-s", "unmatured-s"]
    extras.loc[extras.index[0], "realized_snapshot_ingested_at"] = "2026-07-19T10:59:59Z"
    extras.loc[extras.index[1], "realized_snapshot_ingested_at"] = "2026-07-26T04:00:00Z"
    extras.loc[extras.index[1], "commence_time"] = "2026-07-26T05:00:00Z"
    extras.loc[extras.index[2], "commence_time"] = "2026-07-26T07:00:00Z"
    combined = pd.concat([candidates, extras], ignore_index=True)
    raw, _, diagnostics = freeze_campaign_cohort_policies(combined, policy())
    assert len(raw) == 80
    assert diagnostics["excluded"] == {
        "before_activation": 1,
        "after_latest_observation": 1,
        "commences_after_campaign": 1,
    }


def test_capacity_shortfall_is_frozen_not_backfilled_with_nonpositive_scores() -> None:
    candidates = candidate_fixture()
    candidates.loc[
        candidates["supported_closing_cutoff_hours"] == 48,
        "action_rank_score_for_raw_candidate",
    ] = -1.0
    _, residual, diagnostics = freeze_campaign_cohort_policies(candidates, policy())
    assert int(
        residual.loc[
            residual["supported_closing_cutoff_hours"] == 48, "selected"
        ].sum()
    ) == 0
    assert (
        diagnostics["residual_policy"]["cutoffs"]["T-48h"][
            "positive_score_capacity_complete"
        ]
        is False
    )


def test_evaluation_promotes_clean_synthetic_directional_signal() -> None:
    candidates = candidate_fixture()
    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    ledger, result = evaluate_frozen_campaign_policies(
        frozen_raw,
        frozen_residual,
        closing_fixture(candidates),
        policy(),
    )
    assert len(ledger) == 80
    assert result["raw_strategy"]["mean_selected_log_clv"] == pytest.approx(-0.04)
    assert result["residual_strategy"]["mean_selected_log_clv"] == pytest.approx(0.08)
    assert result["positive_cutoffs"] == 4
    assert result["incremental_residual_minus_raw"]["ci95_low"] > 0
    assert result["prospective_matched_budget_promoted"] is True
    assert result["profit_claim"] is False


def test_missing_exact_target_and_bad_chronology_fail_closed() -> None:
    candidates = candidate_fixture()
    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    closing = closing_fixture(candidates)
    with pytest.raises(ValueError, match="missing exact closing targets"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing.iloc[:-1].copy(),
            policy(),
        )
    closing.loc[0, "closing_snapshot_ingested_at"] = "2026-07-19T23:00:00Z"
    with pytest.raises(ValueError, match="closing chronology is invalid"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing,
            policy(),
        )


def test_outcome_fields_and_policy_tampering_fail_closed() -> None:
    candidates = candidate_fixture()
    with pytest.raises(ValueError, match="outcome fields are forbidden"):
        freeze_campaign_cohort_policies(candidates.assign(winner="home"), policy())
    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    frozen_raw["closing_data_read_before_selection"] = True
    with pytest.raises(ValueError, match="not frozen before closing"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing_fixture(candidates),
            policy(),
        )


def test_selection_and_identity_tampering_fail_closed() -> None:
    candidates = candidate_fixture()
    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    selected_index = frozen_raw.index[frozen_raw["selected"]][0]
    unselected_index = frozen_raw.index[~frozen_raw["selected"]][0]
    frozen_raw.loc[selected_index, "selected"] = False
    frozen_raw.loc[unselected_index, "selected"] = True
    with pytest.raises(ValueError, match="selection flags do not match"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing_fixture(candidates),
            policy(),
        )

    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    frozen_residual.loc[0, "bookmaker_key"] = "tampered-book"
    with pytest.raises(ValueError, match="candidate identities differ"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing_fixture(candidates),
            policy(),
        )


def test_closing_target_commence_mismatch_fails_closed() -> None:
    candidates = candidate_fixture()
    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    closing = closing_fixture(candidates)
    closing.loc[0, "commence_time"] = "2026-07-21T01:00:00Z"
    with pytest.raises(ValueError, match="commence times differ"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing,
            policy(),
        )


def test_policy_score_tampering_fails_closed() -> None:
    candidates = candidate_fixture()
    frozen_raw, frozen_residual, _ = freeze_campaign_cohort_policies(
        candidates, policy()
    )
    frozen_raw.loc[0, "policy_score"] += 1.0
    with pytest.raises(ValueError, match="policy scores do not match"):
        evaluate_frozen_campaign_policies(
            frozen_raw,
            frozen_residual,
            closing_fixture(candidates),
            policy(),
        )
