from __future__ import annotations

import pandas as pd
import pytest

from marketlab.outcome_execution_attribution import attribute_outcome_execution


def ledger(*, residual: bool) -> pd.DataFrame:
    outcomes = ["home", "home", "draw", "draw", "away", "away"]
    returns = (
        [1.2, -1.0, -1.0, -1.0, -1.0, -1.0]
        if residual
        else [-1.0, -1.0, 1.5, -1.0, -1.0, -1.0]
    )
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4", "m5", "m6"],
            "hours_before_kickoff": [24] * 6,
            "filled": [True] * 6,
            "won": [value > 0 for value in returns],
            "executed_decimal_odds": [
                value + 1 if value > 0 else 2.0 for value in returns
            ],
            "net_return_after_friction": returns,
            "book_slot": ["b1", "b1", "b2", "b2", "b3", "b3"],
            "bookmaker_name": ["A", "A", "B", "B", "C", "C"],
            "selected_outcome": outcomes,
        }
    )


def test_attributes_point_return_by_outcome_and_without_home() -> None:
    table, summary = attribute_outcome_execution(
        ledger(residual=False),
        ledger(residual=True),
        replicates=100,
        seed=7,
    )
    home = table[
        (table["group_kind"] == "outcome") & (table["group"] == "home")
    ].iloc[0]
    draw = table[
        (table["group_kind"] == "outcome") & (table["group"] == "draw")
    ].iloc[0]
    non_home = table[table["group"] == "non_home"].iloc[0]
    without_home = table[table["group"] == "without_home"].iloc[0]

    assert home["incremental_profit_units"] == pytest.approx(2.2)
    assert draw["incremental_profit_units"] == pytest.approx(-2.5)
    assert non_home["incremental_profit_units"] == pytest.approx(-2.5)
    assert without_home["incremental_profit_units"] == pytest.approx(-2.5)
    assert summary["non_home_incremental_positive"] is False
    assert summary["without_home_incremental_positive"] is False
    assert summary["maximum_positive_outcome_contribution_share"] == pytest.approx(1.0)


def test_preserves_complete_partition_counts() -> None:
    table, summary = attribute_outcome_execution(
        ledger(residual=False),
        ledger(residual=True),
        replicates=50,
        seed=11,
    )
    outcome_rows = table[table["group_kind"] == "outcome"]
    assert outcome_rows["opportunities"].sum() == 6
    assert summary["opportunities"] == 6
    assert summary["matches"] == 6
    assert summary["positive_outcome_count"] == 1


def test_rejects_policy_outcome_identity_change() -> None:
    residual = ledger(residual=True)
    residual.loc[0, "selected_outcome"] = "away"
    with pytest.raises(ValueError, match="selected outcomes differ"):
        attribute_outcome_execution(
            ledger(residual=False),
            residual,
            replicates=20,
        )


def test_rejects_unexpected_outcome() -> None:
    raw = ledger(residual=False)
    residual = ledger(residual=True)
    raw.loc[0, "selected_outcome"] = "other"
    residual.loc[0, "selected_outcome"] = "other"
    with pytest.raises(ValueError, match="unexpected selected outcomes"):
        attribute_outcome_execution(raw, residual, replicates=20)
