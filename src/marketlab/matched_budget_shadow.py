from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "event_id",
    "realized_snapshot_id",
    "realized_snapshot_ingested_at",
    "supported_closing_cutoff_hours",
    "bookmaker_key",
    "raw_candidate_outcome",
    "raw_candidate_score",
    "action_rank_score_for_raw_candidate",
)


@dataclass(frozen=True, slots=True)
class MatchedBudgetPolicy:
    activation_utc: str
    fraction: float = 0.05
    raw_policy_id: str = "raw_positive_top_5pct_v1"
    residual_policy_id: str = "residual_positive_top_5pct_v1"

    def validate(self) -> None:
        activation = pd.to_datetime(self.activation_utc, utc=True, errors="coerce")
        if pd.isna(activation):
            raise ValueError("activation_utc is invalid")
        if not 0.0 < self.fraction <= 1.0:
            raise ValueError("fraction must be in (0, 1]")


def _require_columns(frame: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"event candidates missing columns: {missing}")


def _rank_percentile(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame.groupby(
        ["realized_snapshot_id", "supported_closing_cutoff_hours"],
        sort=False,
    )[column].rank(method="average", pct=True)


def _select_group(
    group: pd.DataFrame,
    *,
    score_column: str,
    output_column: str,
    fraction: float,
) -> pd.DataFrame:
    group = group.copy()
    group[output_column] = False
    count = max(1, int(np.floor(len(group) * fraction)))
    eligible = group[group[score_column] > 0].sort_values(
        [score_column, "event_id", "bookmaker_key", "raw_candidate_outcome"],
        ascending=[False, True, True, True],
        kind="mergesort",
    )
    group.loc[eligible.index[:count], output_column] = True
    return group


def build_matched_budget_shadow(
    candidates: pd.DataFrame,
    policy: MatchedBudgetPolicy,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    policy.validate()
    _require_columns(candidates)
    frame = candidates.copy()
    frame["realized_snapshot_ingested_at"] = pd.to_datetime(
        frame["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    invalid_time = frame["realized_snapshot_ingested_at"].isna()
    if invalid_time.any():
        raise ValueError(
            f"event candidates contain {int(invalid_time.sum())} invalid ingestion timestamps"
        )
    if frame.duplicated(["event_id", "realized_snapshot_id"]).any():
        raise ValueError("event candidates contain duplicate event/snapshot rows")

    activation = pd.to_datetime(policy.activation_utc, utc=True)
    pre_activation = frame["realized_snapshot_ingested_at"] < activation
    frame = frame.loc[~pre_activation].copy()
    frame["raw_rank_percentile_within_snapshot_cutoff"] = _rank_percentile(
        frame, "raw_candidate_score"
    )
    frame["residual_rank_percentile_within_snapshot_cutoff"] = _rank_percentile(
        frame, "action_rank_score_for_raw_candidate"
    )

    if frame.empty:
        frame["raw_matched_selected"] = pd.Series(dtype=bool)
        frame["residual_challenger_selected"] = pd.Series(dtype=bool)
    else:
        groups: list[pd.DataFrame] = []
        for _, group in frame.groupby(
            ["realized_snapshot_id", "supported_closing_cutoff_hours"],
            sort=False,
        ):
            selected = _select_group(
                group,
                score_column="raw_candidate_score",
                output_column="raw_matched_selected",
                fraction=policy.fraction,
            )
            selected = _select_group(
                selected,
                score_column="action_rank_score_for_raw_candidate",
                output_column="residual_challenger_selected",
                fraction=policy.fraction,
            )
            groups.append(selected)
        frame = pd.concat(groups, ignore_index=True)

    frame["raw_policy_id"] = policy.raw_policy_id
    frame["residual_policy_id"] = policy.residual_policy_id
    frame["matched_budget_fraction"] = policy.fraction
    frame["policy_activation_utc"] = activation.isoformat()
    frame["research_only"] = True
    frame["no_execution"] = True

    raw_selected = frame["raw_matched_selected"].to_numpy(bool) if len(frame) else np.array([], dtype=bool)
    residual_selected = (
        frame["residual_challenger_selected"].to_numpy(bool)
        if len(frame)
        else np.array([], dtype=bool)
    )
    either = raw_selected | residual_selected
    both = raw_selected & residual_selected
    diagnostics = {
        "policy": asdict(policy),
        "input_rows": int(len(candidates)),
        "pre_activation_rows_excluded": int(pre_activation.sum()),
        "eligible_rows_after_activation": int(len(frame)),
        "snapshots": int(frame["realized_snapshot_id"].nunique()) if len(frame) else 0,
        "snapshot_cutoff_groups": int(
            frame.groupby(
                ["realized_snapshot_id", "supported_closing_cutoff_hours"]
            ).ngroups
        )
        if len(frame)
        else 0,
        "raw_selected_rows": int(raw_selected.sum()),
        "residual_selected_rows": int(residual_selected.sum()),
        "selected_by_both": int(both.sum()),
        "selection_jaccard": float(both.sum() / either.sum()) if either.any() else 1.0,
        "same_candidate_identity_by_construction": True,
        "match_outcomes_used": False,
        "no_execution": True,
    }
    frame.sort_values(
        [
            "realized_snapshot_ingested_at",
            "realized_snapshot_id",
            "supported_closing_cutoff_hours",
            "event_id",
        ],
        kind="mergesort",
        inplace=True,
    )
    frame.reset_index(drop=True, inplace=True)
    return frame, diagnostics
