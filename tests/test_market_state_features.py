from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from marketlab.features.market_state import (
    BookmakerMarketState,
    SelectionQuote,
    consensus_median,
    deviation_from_consensus,
    latest_quotes_at_or_before,
    movement_primitives,
    proportional_devig,
)


T0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def q(book: str, selection: str, price: float, at: datetime = T0) -> SelectionQuote:
    return SelectionQuote(book, selection, price, at)


def test_proportional_devig_requires_complete_unique_market() -> None:
    state = proportional_devig(
        [q("b1", "home", 2.0), q("b1", "draw", 4.0), q("b1", "away", 4.0)],
        expected_selections={"home", "draw", "away"},
    )
    assert state.bookmaker_id == "b1"
    assert state.overround == pytest.approx(0.0)
    assert state.probabilities == pytest.approx({"home": 0.5, "draw": 0.25, "away": 0.25})

    with pytest.raises(ValueError, match="incomplete"):
        proportional_devig(
            [q("b1", "home", 2.0), q("b1", "away", 4.0)],
            expected_selections={"home", "draw", "away"},
        )


def test_consensus_median_is_normalized_and_robust() -> None:
    selections = {"home", "draw", "away"}
    states = [
        proportional_devig([q("b1", "home", 2.0), q("b1", "draw", 4.0), q("b1", "away", 4.0)], expected_selections=selections),
        proportional_devig([q("b2", "home", 2.1), q("b2", "draw", 3.8), q("b2", "away", 4.1)], expected_selections=selections),
        proportional_devig([q("outlier", "home", 10.0), q("outlier", "draw", 2.0), q("outlier", "away", 2.0)], expected_selections=selections),
    ]
    consensus = consensus_median(states, expected_selections=selections)
    assert sum(consensus.probabilities.values()) == pytest.approx(1.0)
    assert consensus.contributing_bookmakers == {"home": 3, "draw": 3, "away": 3}
    assert consensus.probabilities["home"] > 0.4


def test_deviation_and_movement_do_not_infer_intent() -> None:
    selections = {"home", "draw", "away"}
    b1_t0 = proportional_devig([q("b1", "home", 2.0), q("b1", "draw", 4.0), q("b1", "away", 4.0)], expected_selections=selections)
    b2_t0 = proportional_devig([q("b2", "home", 2.1), q("b2", "draw", 3.8), q("b2", "away", 4.1)], expected_selections=selections)
    c0 = consensus_median([b1_t0, b2_t0], expected_selections=selections)

    later = T0 + timedelta(minutes=10)
    b1_t1 = proportional_devig(
        [q("b1", "home", 1.8, later), q("b1", "draw", 4.3, later), q("b1", "away", 4.6, later)],
        expected_selections=selections,
    )
    b2_t1 = proportional_devig(
        [q("b2", "home", 2.05, later), q("b2", "draw", 3.85, later), q("b2", "away", 4.15, later)],
        expected_selections=selections,
    )
    c1 = consensus_median([b1_t1, b2_t1], expected_selections=selections)

    deviation = deviation_from_consensus(b1_t0, c0)
    assert set(deviation) == selections

    movements = {item.selection_id: item for item in movement_primitives(b1_t0, b1_t1, previous_consensus=c0, current_consensus=c1)}
    assert movements["home"].elapsed_seconds == 600
    assert movements["home"].probability_delta > 0
    assert movements["home"].consensus_delta is not None
    assert movements["home"].deviation_delta is not None


def test_movement_rejects_time_reversal() -> None:
    previous = BookmakerMarketState("b1", T0, {"home": 0.5, "away": 0.5}, 0.0)
    current = BookmakerMarketState("b1", T0 - timedelta(seconds=1), {"home": 0.51, "away": 0.49}, 0.0)
    with pytest.raises(ValueError, match="strictly later"):
        movement_primitives(previous, current)


def test_latest_quotes_at_or_before_never_uses_future() -> None:
    quotes = [
        q("b1", "home", 2.2, T0 - timedelta(minutes=10)),
        q("b1", "home", 2.1, T0 - timedelta(minutes=1)),
        q("b1", "home", 1.8, T0 + timedelta(seconds=1)),
        q("b1", "away", 3.2, T0 - timedelta(minutes=2)),
    ]
    latest = latest_quotes_at_or_before(quotes, T0)
    assert latest[("b1", "home")].decimal_price == 2.1
    assert latest[("b1", "away")].decimal_price == 3.2
