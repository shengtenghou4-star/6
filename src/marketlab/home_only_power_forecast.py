from __future__ import annotations

from typing import Any

import pandas as pd

HOME_ACTIVATION_UTC = "2026-07-19T15:00:00Z"


def filter_home_forecast_candidates(
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {
        "event_id",
        "realized_snapshot_id",
        "realized_snapshot_ingested_at",
        "raw_candidate_outcome",
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError(f"candidate ledger missing columns: {missing}")
    frame = candidates.copy()
    timestamps = pd.to_datetime(
        frame["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    if timestamps.isna().any():
        raise ValueError("candidate ledger has invalid ingestion timestamps")
    outcomes = frame["raw_candidate_outcome"].astype(str)
    unexpected = sorted(set(outcomes.unique()) - {"home", "draw", "away"})
    if unexpected:
        raise ValueError(f"unexpected candidate outcomes: {unexpected}")

    activation = pd.Timestamp(HOME_ACTIVATION_UTC)
    post_activation = timestamps >= activation
    home = outcomes == "home"
    filtered = frame.loc[home].copy().reset_index(drop=True)
    post_home = frame.loc[home & post_activation]
    return filtered, {
        "activation_utc": activation.isoformat(),
        "source_rows": int(len(frame)),
        "source_events": int(frame["event_id"].nunique()),
        "home_rows_all_times": int(home.sum()),
        "home_rows_post_activation": int(len(post_home)),
        "home_events_post_activation": int(post_home["event_id"].nunique()),
        "home_snapshots_post_activation": int(
            post_home["realized_snapshot_id"].nunique()
        ),
        "filter_applied_before_forecast": True,
        "performance_fields_used": False,
    }
