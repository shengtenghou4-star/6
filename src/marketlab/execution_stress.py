from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ExecutionScenario:
    name: str
    latency_hours: int
    slippage_bps: int
    base_fill_rate: float
    adverse_fill_sensitivity: float = 20.0
    seed: int = 20260719

    def __post_init__(self) -> None:
        if self.latency_hours < 0:
            raise ValueError("latency_hours must be nonnegative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be nonnegative")
        if not 0.0 <= self.base_fill_rate <= 1.0:
            raise ValueError("base_fill_rate must be in [0, 1]")
        if self.adverse_fill_sensitivity < 0.0:
            raise ValueError("adverse_fill_sensitivity must be nonnegative")


REQUIRED_COLUMNS = {
    "match_id",
    "hours_before_kickoff",
    "book_slot",
    "selected_outcome",
    "traded",
    "won",
    "observation_decimal_odds",
}


def deterministic_uniform(keys: Iterable[str], *, seed: int) -> np.ndarray:
    values: list[float] = []
    for key in keys:
        digest = hashlib.sha256(f"{seed}|{key}".encode("utf-8")).digest()
        integer = int.from_bytes(digest[:8], "big", signed=False)
        values.append((integer + 0.5) / 2**64)
    return np.asarray(values, dtype=float)


def _execution_column(latency_hours: int) -> str:
    return f"execution_decimal_odds_delay_{latency_hours}h"


def apply_execution_scenario(
    settled: pd.DataFrame,
    scenario: ExecutionScenario,
) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(settled.columns))
    if missing:
        raise ValueError(f"settled strategy missing columns: {missing}")
    execution_column = _execution_column(scenario.latency_hours)
    if execution_column not in settled.columns:
        raise ValueError(f"settled strategy missing execution column: {execution_column}")
    frame = settled.copy()
    observation = pd.to_numeric(frame["observation_decimal_odds"], errors="coerce").to_numpy(float)
    execution = pd.to_numeric(frame[execution_column], errors="coerce").to_numpy(float)
    valid_execution = np.isfinite(execution) & (execution > 1.0)
    if not np.isfinite(observation).all() or np.any(observation <= 1.0):
        raise ValueError("invalid observation odds")

    adverse_log_move = np.zeros(len(frame), dtype=float)
    adverse_log_move[valid_execution] = np.maximum(
        0.0,
        np.log(observation[valid_execution] / execution[valid_execution]),
    )
    fill_probability = (
        scenario.base_fill_rate
        * np.exp(-scenario.adverse_fill_sensitivity * adverse_log_move)
    )
    fill_probability = np.clip(fill_probability, 0.0, 1.0)
    identity = (
        frame["match_id"].astype(str)
        + "|"
        + frame["hours_before_kickoff"].astype(str)
        + "|"
        + frame["book_slot"].astype(str)
        + "|"
        + frame["selected_outcome"].astype(str)
        + "|"
        + scenario.name
    )
    draw = deterministic_uniform(identity.tolist(), seed=scenario.seed)
    attempted = frame["traded"].astype(bool).to_numpy()
    filled = attempted & valid_execution & (draw < fill_probability)
    haircut = math.exp(-scenario.slippage_bps / 10_000.0)
    executed_odds = np.where(valid_execution, np.maximum(1.000001, execution * haircut), np.nan)
    won = frame["won"].astype(bool).to_numpy()
    net_return = np.where(filled, np.where(won, executed_odds - 1.0, -1.0), 0.0)

    frame["scenario_name"] = scenario.name
    frame["latency_hours"] = scenario.latency_hours
    frame["slippage_bps"] = scenario.slippage_bps
    frame["base_fill_rate"] = scenario.base_fill_rate
    frame["adverse_fill_sensitivity"] = scenario.adverse_fill_sensitivity
    frame["execution_price_available"] = valid_execution
    frame["adverse_log_move"] = adverse_log_move
    frame["fill_probability"] = fill_probability
    frame["fill_uniform"] = draw
    frame["attempted"] = attempted
    frame["filled"] = filled
    frame["executed_decimal_odds"] = executed_odds
    frame["net_return_after_friction"] = net_return
    return frame


def maximum_drawdown(ledger: pd.DataFrame) -> float:
    if "observation_time_proxy" in ledger.columns:
        ordered = ledger.sort_values(
            ["observation_time_proxy", "match_id", "hours_before_kickoff"],
            kind="mergesort",
        )
    else:
        ordered = ledger.sort_values(
            ["match_id", "hours_before_kickoff"], kind="mergesort"
        )
    cumulative = ordered["net_return_after_friction"].to_numpy(float).cumsum()
    if cumulative.size == 0:
        return 0.0
    running_peak = np.maximum.accumulate(np.concatenate([[0.0], cumulative]))[1:]
    return float(np.max(running_peak - cumulative, initial=0.0))


def event_cluster_bootstrap(
    ledger: pd.DataFrame,
    values: np.ndarray,
    *,
    replicates: int = 1000,
    seed: int = 20260719,
) -> dict[str, float]:
    matches = ledger["match_id"].astype(str).to_numpy()
    unique, inverse = np.unique(matches, return_inverse=True)
    sums = np.bincount(inverse, weights=np.asarray(values, dtype=float), minlength=len(unique))
    counts = np.bincount(inverse, minlength=len(unique))
    rng = np.random.default_rng(seed)
    estimates = np.empty(replicates, dtype=float)
    for index in range(replicates):
        sampled = rng.integers(0, len(unique), size=len(unique))
        estimates[index] = sums[sampled].sum() / counts[sampled].sum()
    return {
        "mean": float(np.asarray(values, dtype=float).mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
    }


def scenario_metrics(ledger: pd.DataFrame) -> dict[str, Any]:
    attempted = ledger[ledger["attempted"]].copy()
    filled = ledger[ledger["filled"]].copy()
    net = ledger["net_return_after_friction"].to_numpy(float)
    fill_count = len(filled)
    win_odds_sum = float(
        filled.loc[filled["won"], "executed_decimal_odds"].sum()
    )
    if fill_count and win_odds_sum > fill_count:
        break_even_extra_log_haircut = math.log(win_odds_sum / fill_count)
        break_even_extra_slippage_bps = 10_000.0 * break_even_extra_log_haircut
    else:
        break_even_extra_slippage_bps = 0.0
    by_cutoff: dict[str, Any] = {}
    for cutoff, group in ledger.groupby("hours_before_kickoff", sort=True):
        group_filled = group[group["filled"]]
        by_cutoff[f"T-{int(cutoff)}h"] = {
            "attempts": int(group["attempted"].sum()),
            "fills": int(group["filled"].sum()),
            "profit_units": float(group["net_return_after_friction"].sum()),
            "roi_per_fill": float(group_filled["net_return_after_friction"].mean())
            if len(group_filled)
            else None,
            "return_per_opportunity": float(
                group["net_return_after_friction"].mean()
            ),
        }
    return {
        "scenario": {
            key: ledger[key].iloc[0]
            for key in (
                "scenario_name",
                "latency_hours",
                "slippage_bps",
                "base_fill_rate",
                "adverse_fill_sensitivity",
            )
        },
        "opportunities": int(len(ledger)),
        "attempts": int(len(attempted)),
        "fills": int(fill_count),
        "fill_rate_among_attempts": float(fill_count / len(attempted))
        if len(attempted)
        else 0.0,
        "total_profit_units": float(net.sum()),
        "roi_per_fill": float(filled["net_return_after_friction"].mean())
        if fill_count
        else None,
        "return_per_opportunity": float(net.mean()),
        "mean_adverse_log_move_attempted": float(
            attempted["adverse_log_move"].mean()
        )
        if len(attempted)
        else 0.0,
        "maximum_drawdown_units": maximum_drawdown(filled),
        "opportunity_return_match_bootstrap": event_cluster_bootstrap(
            ledger, net
        ),
        "break_even_additional_slippage_bps": float(
            max(0.0, break_even_extra_slippage_bps)
        ),
        "by_cutoff": by_cutoff,
    }


def compare_scenario_ledgers(
    baseline: pd.DataFrame,
    overlay: pd.DataFrame,
) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    columns = keys + ["net_return_after_friction", "filled"]
    joined = baseline[columns].merge(
        overlay[columns],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_overlay"),
    )
    if len(joined) != len(baseline) or len(joined) != len(overlay):
        raise RuntimeError("strategy opportunity universes differ")
    difference = (
        joined["net_return_after_friction_overlay"].to_numpy(float)
        - joined["net_return_after_friction_baseline"].to_numpy(float)
    )
    return {
        "opportunities": int(len(joined)),
        "incremental_profit_units": float(difference.sum()),
        "incremental_return_per_opportunity": float(difference.mean()),
        "paired_match_bootstrap": event_cluster_bootstrap(joined, difference),
        "baseline_fills": int(joined["filled_baseline"].sum()),
        "overlay_fills": int(joined["filled_overlay"].sum()),
    }


def default_scenarios() -> tuple[ExecutionScenario, ...]:
    scenarios: list[ExecutionScenario] = []
    for latency in (0, 1, 2, 3):
        for slippage in (0, 25, 50, 100):
            for fill_rate in (1.0, 0.9, 0.75, 0.5):
                scenarios.append(
                    ExecutionScenario(
                        name=(
                            f"delay_{latency}h__slip_{slippage}bps__fill_"
                            f"{int(fill_rate * 100)}pct"
                        ),
                        latency_hours=latency,
                        slippage_bps=slippage,
                        base_fill_rate=fill_rate,
                    )
                )
    return tuple(scenarios)


def scenario_to_dict(scenario: ExecutionScenario) -> dict[str, Any]:
    return asdict(scenario)
