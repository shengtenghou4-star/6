from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketlab.execution_envelope_pairing import (
    paired_frame,
    signed_standalone_break_even_slippage_bps,
)


def ledger_metrics(ledger: pd.DataFrame) -> dict[str, Any]:
    attempts = ledger[ledger["attempted"]]
    filled = ledger[ledger["filled"]]
    eligible = int(ledger["eligible_for_fill"].sum())
    return {
        "opportunities": int(len(ledger)),
        "attempts": int(len(attempts)),
        "eligible_execution_prices": eligible,
        "fills": int(len(filled)),
        "fill_rate_among_execution_eligible_attempts": (
            float(len(filled) / eligible) if eligible else 0.0
        ),
        "profit_units": float(ledger["net_return_after_friction"].sum()),
        "roi_per_fill": (
            float(filled["net_return_after_friction"].mean())
            if len(filled)
            else None
        ),
        "return_per_opportunity": float(
            ledger["net_return_after_friction"].mean()
        ),
        "signed_additional_break_even_slippage_bps": (
            signed_standalone_break_even_slippage_bps(ledger)
        ),
    }


def cluster_bootstrap_mean(
    frame: pd.DataFrame,
    value_column: str,
    *,
    replicates: int,
    seed: int,
) -> dict[str, float | int]:
    grouped = frame.groupby(frame["match_id"].astype(str), sort=True)[value_column].agg(
        ["sum", "count"]
    )
    sums = grouped["sum"].to_numpy(float)
    counts = grouped["count"].to_numpy(float)
    rng = np.random.default_rng(seed)
    estimates = np.empty(replicates, dtype=float)
    for index in range(replicates):
        sampled = rng.integers(0, len(sums), size=len(sums))
        estimates[index] = sums[sampled].sum() / counts[sampled].sum()
    values = frame[value_column].to_numpy(float)
    return {
        "mean": float(values.mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
        "replicates": int(replicates),
    }


def paired_metrics(
    raw: pd.DataFrame,
    residual: pd.DataFrame,
    *,
    replicates: int | None = None,
    seed: int = 20260719,
) -> dict[str, Any]:
    joined = paired_frame(raw, residual)
    result: dict[str, Any] = {
        "opportunities": int(len(joined)),
        "incremental_profit_units": float(joined["incremental_return"].sum()),
        "incremental_return_per_opportunity": float(
            joined["incremental_return"].mean()
        ),
        "raw_fills": int(joined["filled_raw"].sum()),
        "residual_fills": int(joined["filled_residual"].sum()),
    }
    if replicates:
        result["paired_event_cluster_bootstrap"] = cluster_bootstrap_mean(
            joined,
            "incremental_return",
            replicates=replicates,
            seed=seed,
        )
    return result
