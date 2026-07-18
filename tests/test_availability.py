from __future__ import annotations

import pytest

from marketlab.availability import (
    AvailabilityClass,
    assert_default_prematch_safe,
    classify_football_data_column,
)


def test_identity_fields_are_safe_by_default() -> None:
    decision = classify_football_data_column("HomeTeam")
    assert decision.availability == AvailabilityClass.IDENTITY
    assert decision.default_prematch_safe is True


def test_results_and_match_stats_are_blocked() -> None:
    assert classify_football_data_column("FTR").availability == AvailabilityClass.POSTMATCH_OUTCOME
    assert classify_football_data_column("HST").availability == AvailabilityClass.POSTMATCH_STATS
    assert classify_football_data_column("FTR").default_prematch_safe is False
    assert classify_football_data_column("HST").default_prematch_safe is False


def test_closing_market_fields_are_blocked() -> None:
    for column in ("AvgCH", "AvgCD", "AvgCA", "B365CH", "B365CA"):
        decision = classify_football_data_column(column)
        assert decision.availability == AvailabilityClass.MARKET_CLOSING
        assert decision.default_prematch_safe is False


def test_coarse_market_fields_require_explicit_protocol() -> None:
    for column in ("B365H", "B365D", "B365A", "PSH", "AvgH"):
        decision = classify_football_data_column(column)
        assert decision.availability == AvailabilityClass.MARKET_FIRST_SET_UNKNOWN_TIME
        assert decision.default_prematch_safe is False


def test_unknown_context_is_fail_closed() -> None:
    decision = classify_football_data_column("SomeFutureVendorField")
    assert decision.availability == AvailabilityClass.UNKNOWN
    assert decision.default_prematch_safe is False


def test_default_safe_gate_rejects_unproven_columns() -> None:
    assert_default_prematch_safe(["Div", "Date", "HomeTeam", "AwayTeam"])
    with pytest.raises(ValueError, match="unsafe/unknown pre-match columns"):
        assert_default_prematch_safe(["HomeTeam", "B365H", "FTR"])
