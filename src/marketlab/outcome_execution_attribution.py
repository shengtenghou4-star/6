from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketlab.execution_envelope_pairing import paired_frame

OUTCOMES = ("home", "draw", "away")


def event_cluster_bootstrap(
    frame: pd.DataFrame,
    value_column: str,
    *,
    replicates: int = 4000,
    seed: int = 20260719,
) -> dict[str, float | int | None]:
    if frame.empty:
        return {
            "replicates": int(replicates),
            "mean": None,
            "ci95_low": None,
            "ci95_high": None,
        }
    working = pd.DataFrame(
        {
            "match_id": frame["match_id"].astype(str),
            "value": pd.to_numeric(frame[value_column], errors="raise").astype(float),
        }
    )
    grouped = working.groupby("match_id", sort=True)["value"].agg(["sum", "count"])
    matrix = grouped[["sum", "count"]].to_numpy(float)
    rng = np.random.default_rng(seed)
    estimates = np.empty(replicates, dtype=float)
    for index in range(replicates):
        sampled = rng.integers(0, len(matrix), size=len(matrix))
        total, count = matrix[sampled].sum(axis=0)
        estimates[index] = total / count
    return {
        "replicates": int(replicates),
        "mean": float(working["value"].mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
    }


def _subset_row(
    paired: pd.DataFrame,
    mask: pd.Series,
    *,
    group_kind: str,
    group: str,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    selected = paired.loc[mask].copy()
    fills = int(selected["filled_residual"].sum())
    residual_profit = float(selected["net_return_after_friction_residual"].sum())
    incremental_profit = float(selected["incremental_return"].sum())
    bootstrap = event_cluster_bootstrap(
        selected,
        "incremental_return",
        replicates=replicates,
        seed=seed,
    )
    return {
        "group_kind": group_kind,
        "group": group,
        "opportunities": int(len(selected)),
        "matches": int(selected["match_id"].nunique()),
        "residual_fills": fills,
        "residual_profit_units": residual_profit,
        "residual_roi_per_fill": residual_profit / fills if fills else None,
        "incremental_profit_units": incremental_profit,
        "incremental_return_per_opportunity": (
            incremental_profit / len(selected) if len(selected) else None
        ),
        "incremental_ci95_low": bootstrap["ci95_low"],
        "incremental_ci95_high": bootstrap["ci95_high"],
    }


def attribute_outcome_execution(
    raw: pd.DataFrame,
    residual: pd.DataFrame,
    *,
    replicates: int = 4000,
    seed: int = 20260719,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    paired = paired_frame(raw, residual)
    if not (
        paired["selected_outcome_raw"].astype(str)
        == paired["selected_outcome_residual"].astype(str)
    ).all():
        raise ValueError("raw and residual selected outcomes differ")
    outcome = paired["selected_outcome_residual"].astype(str)
    unexpected = sorted(set(outcome.unique()) - set(OUTCOMES))
    if unexpected:
        raise ValueError(f"unexpected selected outcomes: {unexpected}")

    rows: list[dict[str, Any]] = []
    for index, selected_outcome in enumerate(OUTCOMES):
        rows.append(
            _subset_row(
                paired,
                outcome == selected_outcome,
                group_kind="outcome",
                group=selected_outcome,
                replicates=replicates,
                seed=seed + index,
            )
        )
    rows.append(
        _subset_row(
            paired,
            outcome != "home",
            group_kind="combined",
            group="non_home",
            replicates=replicates,
            seed=seed + 10,
        )
    )
    for index, excluded in enumerate(OUTCOMES):
        rows.append(
            _subset_row(
                paired,
                outcome != excluded,
                group_kind="leave_one_outcome_out",
                group=f"without_{excluded}",
                replicates=replicates,
                seed=seed + 20 + index,
            )
        )

    table = pd.DataFrame(rows)
    outcome_rows = table[table["group_kind"] == "outcome"].copy()
    positive = outcome_rows.loc[
        outcome_rows["incremental_profit_units"] > 0,
        "incremental_profit_units",
    ]
    summary = {
        "opportunities": int(len(paired)),
        "matches": int(paired["match_id"].nunique()),
        "positive_outcome_count": int((outcome_rows["incremental_profit_units"] > 0).sum()),
        "maximum_positive_outcome_contribution_share": (
            float(positive.max() / positive.sum()) if not positive.empty else None
        ),
        "non_home_incremental_positive": bool(
            table.loc[table["group"] == "non_home", "incremental_profit_units"].iloc[0]
            > 0
        ),
        "without_home_incremental_positive": bool(
            table.loc[
                table["group"] == "without_home", "incremental_profit_units"
            ].iloc[0]
            > 0
        ),
    }
    return table, summary
