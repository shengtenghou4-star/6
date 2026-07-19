from __future__ import annotations

import pandas as pd
import pytest

from marketlab.clv_return_bridge import bridge_by_outcome, paired_bridge_frame


def ledger(*, residual: bool) -> pd.DataFrame:
    outcomes = ["home", "draw", "away"]
    if residual:
        execution = [2.2, 4.0, 3.3]
        returns = [1.2, -1.0, -1.0]
    else:
        execution = [2.0, 4.0, 3.0]
        returns = [-1.0, 3.0, -1.0]
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "hours_before_kickoff": [24, 24, 24],
            "filled": [True, True, True],
            "executed_decimal_odds": execution,
            "closing_decimal_odds": [2.0, 4.0, 3.0],
            "net_return_after_friction": returns,
            "selected_outcome": outcomes,
        }
    )


def test_builds_closing_value_and_realization_gap() -> None:
    paired = paired_bridge_frame(ledger(residual=False), ledger(residual=True))
    home = paired[paired["selected_outcome"] == "home"].iloc[0]
    draw = paired[paired["selected_outcome"] == "draw"].iloc[0]
    away = paired[paired["selected_outcome"] == "away"].iloc[0]

    assert home["incremental_closing_value_contribution"] == pytest.approx(0.1)
    assert home["incremental_realized_contribution"] == pytest.approx(2.2)
    assert home["incremental_realization_gap"] == pytest.approx(2.1)
    assert draw["incremental_closing_value_contribution"] == pytest.approx(0.0)
    assert draw["incremental_realized_contribution"] == pytest.approx(-4.0)
    assert away["incremental_closing_value_contribution"] == pytest.approx(0.1)
    assert away["incremental_realized_contribution"] == pytest.approx(0.0)


def test_reports_each_outcome_with_bootstrap_intervals() -> None:
    table, summary = bridge_by_outcome(
        ledger(residual=False),
        ledger(residual=True),
        replicates=20,
        seed=3,
    )
    assert table["outcome"].tolist() == ["home", "draw", "away"]
    assert table["opportunities"].tolist() == [1, 1, 1]
    assert table["incremental_closing_value_contribution_ci95_low"].notna().all()
    assert summary["outcomes"]["home"]["incremental_closing_value_positive"] is True
    assert summary["outcomes"]["away"]["incremental_closing_value_positive"] is True


def test_rejects_changed_outcome_identity() -> None:
    residual = ledger(residual=True)
    residual.loc[0, "selected_outcome"] = "away"
    with pytest.raises(ValueError, match="selected outcomes differ"):
        paired_bridge_frame(ledger(residual=False), residual)


def test_rejects_invalid_filled_price() -> None:
    residual = ledger(residual=True)
    residual.loc[0, "closing_decimal_odds"] = float("nan")
    with pytest.raises(ValueError, match="invalid price"):
        paired_bridge_frame(ledger(residual=False), residual)
