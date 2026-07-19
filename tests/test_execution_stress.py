from __future__ import annotations

import numpy as np
import pandas as pd

from marketlab.execution_stress import (
    ExecutionScenario,
    apply_execution_scenario,
    compare_scenario_ledgers,
    deterministic_uniform,
    scenario_metrics,
)


def fixture() -> pd.DataFrame:
    rows = []
    for index in range(100):
        won = index % 3 == 0
        rows.append(
            {
                "match_id": f"m{index}",
                "hours_before_kickoff": (48, 24, 12, 6)[index % 4],
                "book_slot": f"b{index % 3}",
                "selected_outcome": ("home", "draw", "away")[index % 3],
                "traded": index < 40,
                "won": won,
                "observation_decimal_odds": 3.2 if won else 2.1,
                "execution_decimal_odds_delay_0h": 3.2 if won else 2.1,
                "execution_decimal_odds_delay_1h": (3.0 if won else 2.0),
                "execution_decimal_odds_delay_2h": (2.8 if won else 1.9),
                "execution_decimal_odds_delay_3h": (2.6 if won else 1.8),
                "observation_time_proxy": pd.Timestamp("2026-01-01", tz="UTC")
                + pd.Timedelta(hours=index),
            }
        )
    return pd.DataFrame(rows)


def test_deterministic_fill_draws() -> None:
    first = deterministic_uniform(["a", "b", "c"], seed=7)
    second = deterministic_uniform(["a", "b", "c"], seed=7)
    different = deterministic_uniform(["a", "b", "c"], seed=8)
    assert np.array_equal(first, second)
    assert not np.array_equal(first, different)
    assert ((first > 0.0) & (first < 1.0)).all()


def test_zero_friction_reproduces_flat_stake_settlement() -> None:
    frame = fixture()
    scenario = ExecutionScenario(
        name="zero",
        latency_hours=0,
        slippage_bps=0,
        base_fill_rate=1.0,
    )
    ledger = apply_execution_scenario(frame, scenario)
    attempted = ledger[ledger["traded"]]
    assert attempted["filled"].all()
    expected = np.where(
        attempted["won"], attempted["observation_decimal_odds"] - 1.0, -1.0
    )
    assert np.allclose(attempted["net_return_after_friction"], expected)
    assert (ledger.loc[~ledger["traded"], "net_return_after_friction"] == 0.0).all()


def test_latency_and_slippage_never_improve_executed_price() -> None:
    frame = fixture()
    clean = apply_execution_scenario(
        frame,
        ExecutionScenario("clean", 0, 0, 1.0),
    )
    stressed = apply_execution_scenario(
        frame,
        ExecutionScenario("stressed", 2, 100, 1.0),
    )
    mask = clean["traded"] & stressed["execution_price_available"]
    assert (
        stressed.loc[mask, "executed_decimal_odds"]
        <= clean.loc[mask, "executed_decimal_odds"]
    ).all()


def test_adverse_moves_reduce_fill_probability() -> None:
    frame = fixture()
    frame.loc[:19, "execution_decimal_odds_delay_1h"] = (
        frame.loc[:19, "observation_decimal_odds"] * 0.8
    )
    ledger = apply_execution_scenario(
        frame,
        ExecutionScenario("fills", 1, 0, 0.9, adverse_fill_sensitivity=20.0),
    )
    adverse = ledger.loc[:19, "fill_probability"].mean()
    stable = ledger.loc[20:39, "fill_probability"].mean()
    assert adverse < stable


def test_metrics_and_comparison_share_opportunity_universe() -> None:
    frame = fixture()
    baseline = apply_execution_scenario(
        frame,
        ExecutionScenario("same", 1, 25, 0.75),
    )
    overlay_frame = frame.copy()
    overlay_frame["traded"] = overlay_frame.index.between(10, 49)
    overlay = apply_execution_scenario(
        overlay_frame,
        ExecutionScenario("same", 1, 25, 0.75),
    )
    metrics = scenario_metrics(baseline)
    comparison = compare_scenario_ledgers(baseline, overlay)
    assert metrics["opportunities"] == 100
    assert metrics["attempts"] == 40
    assert 0 <= metrics["fills"] <= 40
    assert comparison["opportunities"] == 100
