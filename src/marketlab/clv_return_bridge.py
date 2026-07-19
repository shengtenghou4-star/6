from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

OUTCOMES = ("home", "draw", "away")
KEYS = ("match_id", "hours_before_kickoff")
LEDGER_COLUMNS = (
    "filled",
    "executed_decimal_odds",
    "closing_decimal_odds",
    "net_return_after_friction",
    "selected_outcome",
)
VALUE_COLUMNS = (
    "residual_realized_contribution",
    "residual_closing_value_contribution",
    "incremental_realized_contribution",
    "incremental_closing_value_contribution",
    "incremental_realization_gap",
)


def paired_bridge_frame(raw: pd.DataFrame, residual: pd.DataFrame) -> pd.DataFrame:
    required = set(KEYS) | set(LEDGER_COLUMNS)
    for label, frame in (("raw", raw), ("residual", residual)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} ledger missing columns: {missing}")
        if frame.duplicated(list(KEYS)).any():
            raise ValueError(f"{label} ledger contains duplicate opportunities")

    joined = raw[[*KEYS, *LEDGER_COLUMNS]].merge(
        residual[[*KEYS, *LEDGER_COLUMNS]],
        on=list(KEYS),
        how="inner",
        validate="one_to_one",
        suffixes=("_raw", "_residual"),
    )
    if len(joined) != len(raw) or len(joined) != len(residual):
        raise RuntimeError("raw and residual opportunity universes differ")
    if not (
        joined["selected_outcome_raw"].astype(str)
        == joined["selected_outcome_residual"].astype(str)
    ).all():
        raise ValueError("raw and residual selected outcomes differ")
    outcome = joined["selected_outcome_residual"].astype(str)
    unexpected = sorted(set(outcome.unique()) - set(OUTCOMES))
    if unexpected:
        raise ValueError(f"unexpected selected outcomes: {unexpected}")

    for side in ("raw", "residual"):
        filled = joined[f"filled_{side}"].astype(bool).to_numpy()
        execution = pd.to_numeric(
            joined[f"executed_decimal_odds_{side}"], errors="coerce"
        ).to_numpy(float)
        closing = pd.to_numeric(
            joined[f"closing_decimal_odds_{side}"], errors="coerce"
        ).to_numpy(float)
        valid = (~filled) | (
            np.isfinite(execution)
            & np.isfinite(closing)
            & (execution > 1.0)
            & (closing > 1.0)
        )
        if not valid.all():
            raise ValueError(f"{side} filled rows contain invalid price data")
        joined[f"closing_value_contribution_{side}"] = np.where(
            filled, execution / closing - 1.0, 0.0
        )

    joined["selected_outcome"] = outcome
    joined["residual_realized_contribution"] = joined[
        "net_return_after_friction_residual"
    ].astype(float)
    joined["residual_closing_value_contribution"] = joined[
        "closing_value_contribution_residual"
    ].astype(float)
    joined["incremental_realized_contribution"] = (
        joined["net_return_after_friction_residual"].astype(float)
        - joined["net_return_after_friction_raw"].astype(float)
    )
    joined["incremental_closing_value_contribution"] = (
        joined["closing_value_contribution_residual"].astype(float)
        - joined["closing_value_contribution_raw"].astype(float)
    )
    joined["incremental_realization_gap"] = (
        joined["incremental_realized_contribution"]
        - joined["incremental_closing_value_contribution"]
    )
    return joined


def cluster_bootstrap_means(
    frame: pd.DataFrame,
    *,
    replicates: int,
    seed: int,
) -> dict[str, dict[str, float | int]]:
    if frame.empty:
        raise ValueError("cannot bootstrap an empty outcome group")
    grouped = frame.groupby(frame["match_id"].astype(str), sort=True)[
        list(VALUE_COLUMNS)
    ].sum()
    counts = frame.groupby(frame["match_id"].astype(str), sort=True).size()
    if not grouped.index.equals(counts.index):
        raise RuntimeError("cluster sums and counts are misaligned")
    sums = grouped.to_numpy(float)
    count_values = counts.to_numpy(float)
    rng = np.random.default_rng(seed)
    estimates = np.empty((replicates, len(VALUE_COLUMNS)), dtype=float)
    for index in range(replicates):
        sampled = rng.integers(0, len(grouped), size=len(grouped))
        denominator = count_values[sampled].sum()
        estimates[index] = sums[sampled].sum(axis=0) / denominator
    output: dict[str, dict[str, float | int]] = {}
    for column_index, column in enumerate(VALUE_COLUMNS):
        values = frame[column].to_numpy(float)
        output[column] = {
            "replicates": int(replicates),
            "clusters": int(len(grouped)),
            "mean": float(values.mean()),
            "ci95_low": float(np.quantile(estimates[:, column_index], 0.025)),
            "ci95_high": float(np.quantile(estimates[:, column_index], 0.975)),
        }
    return output


def bridge_by_outcome(
    raw: pd.DataFrame,
    residual: pd.DataFrame,
    *,
    replicates: int = 1000,
    seed: int = 20260719,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    paired = paired_bridge_frame(raw, residual)
    rows: list[dict[str, Any]] = []
    outcome_summary: dict[str, Any] = {}
    for outcome_index, outcome in enumerate(OUTCOMES):
        group = paired[paired["selected_outcome"] == outcome].copy()
        bootstrap = cluster_bootstrap_means(
            group,
            replicates=replicates,
            seed=seed + outcome_index,
        )
        row: dict[str, Any] = {
            "outcome": outcome,
            "opportunities": int(len(group)),
            "matches": int(group["match_id"].nunique()),
            "residual_fills": int(group["filled_residual"].sum()),
            "raw_fills": int(group["filled_raw"].sum()),
            "residual_mean_executed_odds": float(
                group.loc[group["filled_residual"], "executed_decimal_odds_residual"].mean()
            ),
        }
        for column in VALUE_COLUMNS:
            values = group[column].to_numpy(float)
            row[f"{column}_units"] = float(values.sum())
            row[f"{column}_per_opportunity"] = float(values.mean())
            row[f"{column}_ci95_low"] = bootstrap[column]["ci95_low"]
            row[f"{column}_ci95_high"] = bootstrap[column]["ci95_high"]
        rows.append(row)
        outcome_summary[outcome] = {
            "incremental_realized_positive": bool(
                row["incremental_realized_contribution_units"] > 0
            ),
            "incremental_closing_value_positive": bool(
                row["incremental_closing_value_contribution_units"] > 0
            ),
            "residual_closing_value_positive": bool(
                row["residual_closing_value_contribution_units"] > 0
            ),
            "realized_vs_closing_sign_divergence": bool(
                np.sign(row["incremental_realized_contribution_units"])
                != np.sign(row["incremental_closing_value_contribution_units"])
            ),
        }
    return pd.DataFrame(rows), {
        "opportunities": int(len(paired)),
        "matches": int(paired["match_id"].nunique()),
        "outcomes": outcome_summary,
    }
