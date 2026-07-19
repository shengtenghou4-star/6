from __future__ import annotations

import math
from typing import Any

import pandas as pd


def paired_frame(raw: pd.DataFrame, residual: pd.DataFrame) -> pd.DataFrame:
    keys = ["match_id", "hours_before_kickoff"]
    columns = keys + [
        "filled",
        "won",
        "executed_decimal_odds",
        "net_return_after_friction",
        "book_slot",
        "bookmaker_name",
        "selected_outcome",
    ]
    joined = raw[columns].merge(
        residual[columns],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_raw", "_residual"),
    )
    if len(joined) != len(raw) or len(joined) != len(residual):
        raise RuntimeError("strategy opportunity universes differ")
    joined["incremental_return"] = (
        joined["net_return_after_friction_residual"]
        - joined["net_return_after_friction_raw"]
    )
    return joined


def signed_standalone_break_even_slippage_bps(
    ledger: pd.DataFrame,
) -> float | None:
    filled = ledger[ledger["filled"]]
    if filled.empty:
        return None
    winner_odds = float(
        filled.loc[filled["won"], "executed_decimal_odds"].sum()
    )
    if winner_odds <= 0.0:
        return None
    return float(10_000.0 * math.log(winner_odds / len(filled)))


def incremental_residual_only_break_even_slippage_bps(
    raw: pd.DataFrame,
    residual: pd.DataFrame,
) -> dict[str, Any]:
    raw_filled = raw[raw["filled"]]
    residual_filled = residual[residual["filled"]]
    raw_profit = float(raw["net_return_after_friction"].sum())
    residual_winner_odds = float(
        residual_filled.loc[
            residual_filled["won"], "executed_decimal_odds"
        ].sum()
    )
    denominator = float(len(residual_filled) + raw_profit)
    if residual_winner_odds <= 0.0:
        return {
            "value_bps": None,
            "status": "no_residual_winner_odds",
            "raw_profit_units": raw_profit,
        }
    if denominator <= 0.0:
        return {
            "value_bps": None,
            "status": "no_finite_crossing",
            "raw_profit_units": raw_profit,
        }
    value = 10_000.0 * math.log(residual_winner_odds / denominator)
    return {
        "value_bps": float(value),
        "status": "finite_crossing",
        "raw_profit_units": raw_profit,
        "raw_fills": int(len(raw_filled)),
        "residual_fills": int(len(residual_filled)),
    }
