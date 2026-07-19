from __future__ import annotations

from typing import Any

import pandas as pd

from marketlab.prospective_matched_budget_evaluation import CohortEvaluationPolicy

EXPECTED_OUTCOME = "home"
ACTIVATION_UTC = "2026-07-19T15:00:00Z"


def filter_home_candidates(candidates: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "raw_candidate_outcome" not in candidates.columns:
        raise ValueError("prospective candidates missing raw_candidate_outcome")
    unexpected = sorted(
        set(candidates["raw_candidate_outcome"].astype(str).unique())
        - {"home", "draw", "away"}
    )
    if unexpected:
        raise ValueError(f"unexpected candidate outcomes: {unexpected}")
    home = candidates.loc[
        candidates["raw_candidate_outcome"].astype(str) == EXPECTED_OUTCOME
    ].copy()
    if home.empty:
        raise RuntimeError("no home candidate opportunities")
    home["home_only_challenger"] = True
    home["home_only_activation_utc"] = ACTIVATION_UTC
    home["home_only_source_experiment"] = "experiment_024_post_hoc_diagnostic"
    home.reset_index(drop=True, inplace=True)
    return home, {
        "input_rows": int(len(candidates)),
        "home_rows_before_campaign_rules": int(len(home)),
        "input_events": int(candidates["event_id"].nunique()),
        "home_events_before_campaign_rules": int(home["event_id"].nunique()),
        "expected_outcome": EXPECTED_OUTCOME,
        "activation_utc": ACTIVATION_UTC,
        "filter_applied_before_policy_ranking": True,
    }


def home_only_policy() -> CohortEvaluationPolicy:
    return CohortEvaluationPolicy(
        activation_utc=ACTIVATION_UTC,
        campaign_end_utc="2026-07-26T06:30:00Z",
        minimum_collection_lead_hours=3.25,
        fraction=0.05,
        raw_policy_id="raw_positive_top_5pct_home_only_cohort_v1",
        residual_policy_id="residual_positive_top_5pct_home_only_cohort_v1",
        minimum_candidates=300,
        minimum_unique_events=75,
        minimum_selected_per_policy=15,
        minimum_candidates_per_cutoff=40,
        minimum_supported_cutoffs=3,
        maximum_positive_book_contribution_share=0.50,
        bootstrap_replicates=4000,
        bootstrap_seed=20260727,
    )
