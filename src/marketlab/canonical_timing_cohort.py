from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketlab.prospective_matched_budget_evaluation import CohortEvaluationPolicy

EXPECTED_ADAPTER_ID = "canonical_cutoff_coverage_normalized_v1"
EXPECTED_ACTIVATION = pd.Timestamp("2026-07-19T15:00:00Z")
ADAPTER_FLAGS = (
    "canonical_timing_unvalidated_transfer",
    "canonical_timing_research_only",
    "canonical_timing_no_execution",
)


def truthy(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "yes"}


def validate_canonical_candidates(candidates: pd.DataFrame) -> dict[str, Any]:
    required = [
        "canonical_timing_adapter_id",
        "canonical_timing_activation_utc",
        *ADAPTER_FLAGS,
    ]
    missing = sorted(set(required) - set(candidates.columns))
    if missing:
        raise ValueError(f"canonical-timing candidates missing columns: {missing}")
    if candidates.empty:
        raise RuntimeError("canonical-timing candidate file is empty")
    if candidates["canonical_timing_adapter_id"].nunique(dropna=False) != 1:
        raise ValueError("canonical-timing cohort contains multiple adapter IDs")
    adapter_id = str(candidates["canonical_timing_adapter_id"].iloc[0])
    if adapter_id != EXPECTED_ADAPTER_ID:
        raise ValueError(f"unexpected canonical-timing adapter ID: {adapter_id}")
    flags = candidates[list(ADAPTER_FLAGS)].apply(lambda column: column.map(truthy))
    if not flags.all().all():
        raise ValueError("canonical-timing evidence flags are not all true")
    activation = pd.to_datetime(
        candidates["canonical_timing_activation_utc"], utc=True, errors="coerce"
    )
    if activation.isna().any() or activation.nunique() != 1:
        raise ValueError("canonical-timing activation boundary is invalid or mixed")
    if activation.iloc[0] != EXPECTED_ACTIVATION:
        raise ValueError(
            f"unexpected canonical-timing activation: {activation.iloc[0].isoformat()}"
        )
    return {
        "adapter_id": adapter_id,
        "activation_utc": activation.iloc[0].isoformat(),
        "rows": int(len(candidates)),
        "events": int(candidates["event_id"].nunique()),
        "snapshots": int(candidates["realized_snapshot_id"].nunique()),
        "adapter_flags_verified": True,
    }


def canonical_policy() -> CohortEvaluationPolicy:
    return CohortEvaluationPolicy(
        activation_utc="2026-07-19T15:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        minimum_collection_lead_hours=3.25,
        fraction=0.05,
        raw_policy_id="raw_positive_top_5pct_canonical_timing_cohort_v1",
        residual_policy_id="residual_positive_top_5pct_canonical_timing_cohort_v1",
        minimum_candidates=300,
        minimum_unique_events=75,
        minimum_selected_per_policy=15,
        minimum_candidates_per_cutoff=40,
        minimum_supported_cutoffs=3,
        maximum_positive_book_contribution_share=0.50,
        bootstrap_replicates=4000,
        bootstrap_seed=20260727,
    )
