from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

CANONICAL_CUTOFFS = (48, 24, 12, 6)
REQUIRED_COLUMNS = (
    "event_id",
    "bookmaker_key",
    "market_key",
    "context_snapshot_id",
    "realized_snapshot_id",
    "realized_snapshot_ingested_at",
    "supported_closing_cutoff_hours",
    "hours_to_commence_scaled_71",
    "active_other_books_scaled_31",
    "raw_candidate_score",
    "action_rank_score_for_raw_candidate",
)
FORBIDDEN_RESULT_COLUMNS = {
    "score_home",
    "score_away",
    "winning_outcome",
    "won",
    "net_return",
    "settled_return",
    "match_result",
}
UNIQUE_KEYS = ("event_id", "bookmaker_key", "market_key", "realized_snapshot_id")
PANEL_KEYS = ("event_id", "context_snapshot_id", "market_key")


@dataclass(frozen=True, slots=True)
class CanonicalTimingPolicy:
    activation_utc: str
    minimum_historical_hours: float = 6.0
    maximum_historical_hours: float = 48.0
    adapter_id: str = "canonical_cutoff_coverage_normalized_v1"

    def validate(self) -> None:
        activation = pd.to_datetime(self.activation_utc, utc=True, errors="coerce")
        if pd.isna(activation):
            raise ValueError("activation_utc is invalid")
        if not self.minimum_historical_hours < self.maximum_historical_hours:
            raise ValueError("invalid historical hours range")
        if not self.adapter_id.strip():
            raise ValueError("adapter_id must be nonempty")


def _require_columns(frame: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"per-book shadow scores missing columns: {missing}")
    forbidden = sorted(FORBIDDEN_RESULT_COLUMNS & set(frame.columns))
    if forbidden:
        raise ValueError(f"result or settlement columns are forbidden: {forbidden}")


def _empty_diagnostics(
    scores: pd.DataFrame,
    policy: CanonicalTimingPolicy,
    *,
    pre_activation_rows: int,
    post_activation_rows: int,
    status: str,
) -> dict[str, Any]:
    return {
        "policy": asdict(policy),
        "input_rows": int(len(scores)),
        "pre_activation_rows_excluded": int(pre_activation_rows),
        "post_activation_rows": int(post_activation_rows),
        "globally_supported_rows": 0,
        "globally_excluded_rows": int(post_activation_rows),
        "status": status,
        "match_outcomes_used": False,
        "closing_targets_used": False,
    }


def prepare_canonical_timing_records(
    scores: pd.DataFrame,
    policy: CanonicalTimingPolicy,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    policy.validate()
    _require_columns(scores)
    frame = scores.copy()
    frame["realized_snapshot_ingested_at"] = pd.to_datetime(
        frame["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    if frame["realized_snapshot_ingested_at"].isna().any():
        raise ValueError("invalid realized snapshot ingestion timestamps")
    if frame.duplicated(list(UNIQUE_KEYS)).any():
        raise ValueError("duplicate per-book shadow identity")

    activation = pd.to_datetime(policy.activation_utc, utc=True)
    pre_activation = frame["realized_snapshot_ingested_at"] < activation
    pre_activation_count = int(pre_activation.sum())
    frame = frame.loc[~pre_activation].copy().reset_index(drop=True)
    if frame.empty:
        return frame, _empty_diagnostics(
            scores,
            policy,
            pre_activation_rows=pre_activation_count,
            post_activation_rows=0,
            status="no_post_activation_rows",
        )

    frame["actual_hours_to_commence"] = pd.to_numeric(
        frame["hours_to_commence_scaled_71"], errors="coerce"
    ) * 71.0
    frame["supported_closing_cutoff_hours"] = pd.to_numeric(
        frame["supported_closing_cutoff_hours"], errors="coerce"
    ).astype("Int64")
    if frame[["actual_hours_to_commence", "supported_closing_cutoff_hours"]].isna().any().any():
        raise ValueError("invalid timing fields")

    actual = frame["actual_hours_to_commence"].to_numpy(dtype=float)
    cutoff = frame["supported_closing_cutoff_hours"].to_numpy(dtype=float)
    globally_supported = (
        (actual >= policy.minimum_historical_hours - 1e-12)
        & (actual <= policy.maximum_historical_hours + 1e-12)
        & frame["supported_closing_cutoff_hours"].isin(CANONICAL_CUTOFFS).to_numpy()
    )
    post_activation_rows = int(len(frame))
    excluded_rows = int((~globally_supported).sum())
    frame = frame.loc[globally_supported].copy().reset_index(drop=True)
    if frame.empty:
        return frame, _empty_diagnostics(
            scores,
            policy,
            pre_activation_rows=pre_activation_count,
            post_activation_rows=post_activation_rows,
            status="no_globally_supported_rows",
        )

    frame["cutoff_distance_hours"] = np.abs(
        frame["actual_hours_to_commence"].to_numpy(dtype=float)
        - frame["supported_closing_cutoff_hours"].to_numpy(dtype=float)
    )
    frame["original_hours_to_commence_scaled_71"] = frame[
        "hours_to_commence_scaled_71"
    ].astype(float)
    frame["hours_to_commence_scaled_71"] = (
        frame["supported_closing_cutoff_hours"].astype(float) / 71.0
    )

    raw_active = pd.to_numeric(
        frame["active_other_books_scaled_31"], errors="coerce"
    ).to_numpy(dtype=float) * 31.0
    rounded_active = np.rint(raw_active)
    if not np.isfinite(raw_active).all() or float(np.abs(raw_active - rounded_active).max()) > 1e-6:
        raise ValueError("active peer-book count does not reconcile to an integer")
    frame["active_peer_book_count"] = rounded_active.astype(np.int16)
    frame["inferred_panel_peer_capacity"] = frame.groupby(
        list(PANEL_KEYS), sort=False
    )["active_peer_book_count"].transform("max")
    if (frame["inferred_panel_peer_capacity"] < 3).any():
        raise ValueError("inferred panel peer capacity is below historical minimum")
    if (frame["active_peer_book_count"] > frame["inferred_panel_peer_capacity"]).any():
        raise RuntimeError("active peer count exceeds inferred panel capacity")

    frame["original_active_other_books_scaled_31"] = frame[
        "active_other_books_scaled_31"
    ].astype(float)
    frame["active_other_books_scaled_31"] = (
        frame["active_peer_book_count"].astype(float)
        / frame["inferred_panel_peer_capacity"].astype(float)
    )
    frame["original_raw_candidate_score"] = frame["raw_candidate_score"].astype(float)
    frame["original_action_rank_score_for_raw_candidate"] = frame[
        "action_rank_score_for_raw_candidate"
    ].astype(float)
    frame["canonical_timing_adapter_id"] = policy.adapter_id
    frame["canonical_timing_activation_utc"] = activation.isoformat()
    frame["canonical_timing_unvalidated_transfer"] = True
    frame["canonical_timing_research_only"] = True
    frame["canonical_timing_no_execution"] = True

    capacity = frame["inferred_panel_peer_capacity"].to_numpy(dtype=float)
    distance = frame["cutoff_distance_hours"].to_numpy(dtype=float)
    by_cutoff: dict[str, Any] = {}
    for hours, group in frame.groupby("supported_closing_cutoff_hours", sort=True):
        by_cutoff[str(int(hours))] = {
            "rows": int(len(group)),
            "events": int(group["event_id"].nunique()),
            "distance_median_hours": float(group["cutoff_distance_hours"].median()),
            "distance_p90_hours": float(group["cutoff_distance_hours"].quantile(0.90)),
        }
    diagnostics = {
        "policy": asdict(policy),
        "input_rows": int(len(scores)),
        "pre_activation_rows_excluded": pre_activation_count,
        "post_activation_rows": post_activation_rows,
        "globally_supported_rows": int(len(frame)),
        "globally_excluded_rows": excluded_rows,
        "events": int(frame["event_id"].nunique()),
        "snapshots": int(frame["realized_snapshot_id"].nunique()),
        "bookmakers": int(frame["bookmaker_key"].nunique()),
        "panel_groups": int(frame.groupby(list(PANEL_KEYS)).ngroups),
        "rows_by_cutoff": by_cutoff,
        "cutoff_distance_hours": {
            "median": float(np.median(distance)),
            "p90": float(np.quantile(distance, 0.90)),
            "maximum": float(np.max(distance)),
        },
        "panel_peer_capacity": {
            "minimum": int(capacity.min()),
            "median": float(np.median(capacity)),
            "maximum": int(capacity.max()),
        },
        "original_active_feature_median": float(
            frame["original_active_other_books_scaled_31"].median()
        ),
        "normalized_active_feature_median": float(
            frame["active_other_books_scaled_31"].median()
        ),
        "status": "prepared",
        "match_outcomes_used": False,
        "closing_targets_used": False,
    }
    frame.sort_values(
        ["realized_snapshot_ingested_at", "realized_snapshot_id", "event_id", "bookmaker_key"],
        kind="mergesort",
        inplace=True,
    )
    frame.reset_index(drop=True, inplace=True)
    return frame, diagnostics
