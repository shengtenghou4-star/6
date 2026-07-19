from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from marketlab.execution_envelope_pairing import paired_frame


def _cluster_components(raw: pd.DataFrame, residual: pd.DataFrame) -> np.ndarray:
    paired = paired_frame(raw, residual)
    paired["raw_winner_odds"] = np.where(
        paired["filled_raw"] & paired["won_raw"],
        paired["executed_decimal_odds_raw"],
        0.0,
    )
    paired["residual_winner_odds"] = np.where(
        paired["filled_residual"] & paired["won_residual"],
        paired["executed_decimal_odds_residual"],
        0.0,
    )
    paired["raw_fill_count"] = paired["filled_raw"].astype(int)
    paired["residual_fill_count"] = paired["filled_residual"].astype(int)
    grouped = paired.groupby(paired["match_id"].astype(str), sort=True)[
        [
            "raw_winner_odds",
            "residual_winner_odds",
            "raw_fill_count",
            "residual_fill_count",
        ]
    ].sum()
    return grouped.to_numpy(float)


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "ci95_low": None,
            "ci95_high": None,
            "median": None,
            "finite_replicates": 0,
        }
    array = np.asarray(values, dtype=float)
    return {
        "ci95_low": float(np.quantile(array, 0.025)),
        "ci95_high": float(np.quantile(array, 0.975)),
        "median": float(np.median(array)),
        "finite_replicates": int(len(array)),
    }


def bootstrap_break_even_frontiers(
    raw: pd.DataFrame,
    residual: pd.DataFrame,
    *,
    replicates: int = 1000,
    seed: int = 20260719,
) -> dict[str, Any]:
    matrix = _cluster_components(raw, residual)
    rng = np.random.default_rng(seed)
    standalone: list[float] = []
    incremental: list[float] = []
    incremental_infinite = 0
    for _ in range(replicates):
        sampled = rng.integers(0, len(matrix), size=len(matrix))
        raw_w, residual_w, raw_n, residual_n = matrix[sampled].sum(axis=0)
        if residual_n > 0 and residual_w > 0:
            standalone.append(10_000.0 * math.log(residual_w / residual_n))
        denominator = residual_n + raw_w - raw_n
        if residual_w > 0 and denominator > 0:
            incremental.append(10_000.0 * math.log(residual_w / denominator))
        elif residual_w > 0 and denominator <= 0:
            incremental_infinite += 1
    return {
        "replicates": int(replicates),
        "standalone_residual": _summary(standalone),
        "incremental_residual_only": {
            **_summary(incremental),
            "infinite_replicates": int(incremental_infinite),
        },
    }
