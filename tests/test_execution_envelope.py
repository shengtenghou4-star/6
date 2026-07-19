from __future__ import annotations

import math

import numpy as np
import pandas as pd

from marketlab.execution_envelope import (
    EnvelopeSpec,
    apply_envelope,
    bootstrap_break_even_frontiers,
    incremental_residual_only_break_even_slippage_bps,
    signed_standalone_break_even_slippage_bps,
)


def sample_frame() -> pd.DataFrame:
    rows = []
    for index in range(8):
        rows.append(
            {
                "match_id": f"m{index}",
                "hours_before_kickoff": 24,
                "book_slot": "b1" if index < 4 else "b2",
                "bookmaker_name": "A" if index < 4 else "B",
                "selected_outcome": "home",
                "traded": True,
                "won": index in {0, 2, 4, 6},
                "observation_decimal_odds": 2.0,
                "execution_decimal_odds_delay_0h": 2.0 - 0.02 * index,
                "baseline_score": float(index + 1),
                "rank_score": float(index + 1),
            }
        )
    return pd.DataFrame(rows)


def test_common_random_hits_exact_monotone_target() -> None:
    frame = sample_frame()
    low = apply_envelope(
        frame,
        EnvelopeSpec("low", 0, 0.5, "common_random"),
        score_column="baseline_score",
    )
    high = apply_envelope(
        frame,
        EnvelopeSpec("high", 0, 0.75, "common_random"),
        score_column="baseline_score",
    )
    assert int(low["filled"].sum()) == 4
    assert int(high["filled"].sum()) == 6
    assert (low["filled"] <= high["filled"]).all()


def test_edge_rejection_rejects_highest_frozen_scores() -> None:
    frame = sample_frame()
    ledger = apply_envelope(
        frame,
        EnvelopeSpec("edge", 0, 0.5, "edge_rejection"),
        score_column="baseline_score",
    )
    assert ledger.loc[ledger["filled"], "baseline_score"].tolist() == [
        1.0,
        2.0,
        3.0,
        4.0,
    ]


def test_book_clustered_outage_hits_exact_target() -> None:
    frame = sample_frame()
    ledger = apply_envelope(
        frame,
        EnvelopeSpec("cluster", 0, 0.75, "book_clustered_outage"),
        score_column="baseline_score",
    )
    assert int(ledger["filled"].sum()) == 6
    by_book = ledger.groupby("book_slot")["filled"].sum().sort_values().tolist()
    assert by_book == [2, 4]


def test_signed_standalone_break_even_matches_closed_form() -> None:
    frame = sample_frame().iloc[:2].copy()
    frame["won"] = [True, False]
    frame["execution_decimal_odds_delay_0h"] = [2.2, 2.0]
    ledger = apply_envelope(
        frame,
        EnvelopeSpec("all", 0, 1.0, "common_random"),
        score_column="baseline_score",
    )
    expected = 10_000.0 * math.log(2.2 / 2.0)
    assert math.isclose(
        signed_standalone_break_even_slippage_bps(ledger), expected, rel_tol=1e-12
    )


def test_incremental_break_even_is_positive_when_residual_leads() -> None:
    raw = sample_frame().iloc[:2].copy()
    residual = raw.copy()
    raw["won"] = [True, False]
    residual["won"] = [True, False]
    raw["execution_decimal_odds_delay_0h"] = [2.0, 2.0]
    residual["execution_decimal_odds_delay_0h"] = [2.2, 2.0]
    raw_ledger = apply_envelope(
        raw,
        EnvelopeSpec("same", 0, 1.0, "common_random"),
        score_column="baseline_score",
    )
    residual_ledger = apply_envelope(
        residual,
        EnvelopeSpec("same", 0, 1.0, "common_random"),
        score_column="rank_score",
    )
    result = incremental_residual_only_break_even_slippage_bps(
        raw_ledger, residual_ledger
    )
    assert result["status"] == "finite_crossing"
    assert result["value_bps"] > 0


def test_frontier_bootstrap_is_deterministic_and_finite() -> None:
    raw = sample_frame()
    residual = sample_frame()
    residual.loc[residual["won"], "execution_decimal_odds_delay_0h"] += 0.1
    raw_ledger = apply_envelope(
        raw,
        EnvelopeSpec("same", 0, 1.0, "common_random"),
        score_column="baseline_score",
    )
    residual_ledger = apply_envelope(
        residual,
        EnvelopeSpec("same", 0, 1.0, "common_random"),
        score_column="rank_score",
    )
    first = bootstrap_break_even_frontiers(
        raw_ledger, residual_ledger, replicates=100, seed=7
    )
    second = bootstrap_break_even_frontiers(
        raw_ledger, residual_ledger, replicates=100, seed=7
    )
    assert first == second
    assert first["standalone_residual"]["finite_replicates"] == 100
    assert np.isfinite(first["standalone_residual"]["median"])
