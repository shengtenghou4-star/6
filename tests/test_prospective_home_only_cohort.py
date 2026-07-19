from __future__ import annotations

import pandas as pd
import pytest

from marketlab.prospective_home_only_cohort import (
    ACTIVATION_UTC,
    filter_home_candidates,
    home_only_policy,
)


def candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": ["e1", "e2", "e3", "e4"],
            "raw_candidate_outcome": ["home", "draw", "away", "home"],
        }
    )


def test_filters_home_before_policy_ranking() -> None:
    filtered, diagnostics = filter_home_candidates(candidates())
    assert filtered["event_id"].tolist() == ["e1", "e4"]
    assert filtered["raw_candidate_outcome"].eq("home").all()
    assert filtered["home_only_challenger"].all()
    assert filtered["home_only_activation_utc"].eq(ACTIVATION_UTC).all()
    assert diagnostics["input_rows"] == 4
    assert diagnostics["home_rows_before_campaign_rules"] == 2
    assert diagnostics["filter_applied_before_policy_ranking"] is True


def test_rejects_unknown_outcome_and_empty_home_set() -> None:
    unknown = candidates().copy()
    unknown.loc[0, "raw_candidate_outcome"] = "other"
    with pytest.raises(ValueError, match="unexpected candidate outcomes"):
        filter_home_candidates(unknown)
    no_home = candidates().query("raw_candidate_outcome != 'home'")
    with pytest.raises(RuntimeError, match="no home"):
        filter_home_candidates(no_home)


def test_home_policy_preserves_strict_volume_gates() -> None:
    policy = home_only_policy()
    assert policy.activation_utc == "2026-07-19T15:00:00Z"
    assert policy.fraction == 0.05
    assert policy.minimum_candidates == 300
    assert policy.minimum_unique_events == 75
    assert policy.minimum_selected_per_policy == 15
    assert policy.minimum_candidates_per_cutoff == 40
    assert policy.minimum_supported_cutoffs == 3
    assert policy.maximum_positive_book_contribution_share == 0.50
    assert policy.bootstrap_replicates == 4000
    assert policy.bootstrap_seed == 20260727
