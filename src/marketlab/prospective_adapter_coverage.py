from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

KEYS = ["event_id", "realized_snapshot_id"]
REQUIRED = {
    "event_id",
    "realized_snapshot_id",
    "realized_snapshot_ingested_at",
    "supported_closing_cutoff_hours",
    "bookmaker_key",
    "raw_candidate_outcome",
    "raw_candidate_score",
    "action_rank_score_for_raw_candidate",
}
FORBIDDEN = {
    "winning_outcome",
    "won",
    "net_return",
    "settled_return",
    "match_result",
    "closing_decimal_odds",
    "log_odds_clv",
    "fair_probability_clv",
}


def prepare(frame: pd.DataFrame, name: str, activation: pd.Timestamp) -> pd.DataFrame:
    missing = sorted(REQUIRED - set(frame.columns))
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
    forbidden = sorted(FORBIDDEN & set(frame.columns))
    if forbidden:
        raise ValueError(f"{name} contains forbidden columns: {forbidden}")
    output = frame.copy()
    output["realized_snapshot_ingested_at"] = pd.to_datetime(
        output["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    if output["realized_snapshot_ingested_at"].isna().any():
        raise ValueError(f"{name} contains invalid timestamps")
    if output.duplicated(KEYS).any():
        raise ValueError(f"{name} contains duplicate identities")
    return output.loc[output["realized_snapshot_ingested_at"] >= activation].copy()


def correlation(left: pd.Series, right: pd.Series, method: str) -> float | None:
    if len(left) < 2 or left.nunique() < 2 or right.nunique() < 2:
        return None
    value = left.corr(right, method=method)
    return float(value) if np.isfinite(value) else None


def profile(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(frame)),
        "events": int(frame["event_id"].nunique()) if len(frame) else 0,
        "snapshots": int(frame["realized_snapshot_id"].nunique()) if len(frame) else 0,
        "rows_by_cutoff": {
            str(int(key)): int(value)
            for key, value in frame["supported_closing_cutoff_hours"]
            .value_counts()
            .sort_index()
            .items()
        },
    }


def compare(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    left_ids = set(map(tuple, left[KEYS].astype(str).to_numpy()))
    right_ids = set(map(tuple, right[KEYS].astype(str).to_numpy()))
    joined = left.merge(
        right,
        on=KEYS,
        how="inner",
        validate="one_to_one",
        suffixes=("_left", "_right"),
    )
    output: dict[str, Any] = {
        "intersection": int(len(left_ids & right_ids)),
        "left_only": int(len(left_ids - right_ids)),
        "right_only": int(len(right_ids - left_ids)),
        "union": int(len(left_ids | right_ids)),
    }
    output["jaccard"] = (
        output["intersection"] / output["union"] if output["union"] else 0.0
    )
    if joined.empty:
        output.update(
            same_bookmaker_share=None,
            same_outcome_share=None,
            raw_spearman=None,
            action_spearman=None,
        )
        return output
    output.update(
        same_bookmaker_share=float(
            (joined["bookmaker_key_left"] == joined["bookmaker_key_right"]).mean()
        ),
        same_outcome_share=float(
            (
                joined["raw_candidate_outcome_left"]
                == joined["raw_candidate_outcome_right"]
            ).mean()
        ),
        raw_spearman=correlation(
            joined["raw_candidate_score_left"],
            joined["raw_candidate_score_right"],
            "spearman",
        ),
        action_spearman=correlation(
            joined["action_rank_score_for_raw_candidate_left"],
            joined["action_rank_score_for_raw_candidate_right"],
            "spearman",
        ),
    )
    return output


def audit_adapter_coverage(
    original: pd.DataFrame,
    support: pd.DataFrame,
    canonical: pd.DataFrame,
    common_activation_utc: str,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    activation = pd.to_datetime(common_activation_utc, utc=True, errors="coerce")
    if pd.isna(activation):
        raise ValueError("invalid common activation")
    streams = {
        "original": prepare(original, "original", activation),
        "support_repaired": prepare(support, "support_repaired", activation),
        "canonical_timing": prepare(canonical, "canonical_timing", activation),
    }
    original_rows = len(streams["original"])
    result = {
        "common_activation_utc": activation.isoformat(),
        "outcome_blind": True,
        "streams": {name: profile(frame) for name, frame in streams.items()},
        "pairs": {
            "original_vs_support": compare(streams["original"], streams["support_repaired"]),
            "original_vs_canonical": compare(streams["original"], streams["canonical_timing"]),
            "support_vs_canonical": compare(streams["support_repaired"], streams["canonical_timing"]),
        },
    }
    result["coverage"] = {
        "support_share_of_original": len(streams["support_repaired"]) / original_rows
        if original_rows
        else None,
        "canonical_share_of_original": len(streams["canonical_timing"]) / original_rows
        if original_rows
        else None,
        "canonical_minus_support_rows": int(
            len(streams["canonical_timing"]) - len(streams["support_repaired"])
        ),
    }
    return result, streams
