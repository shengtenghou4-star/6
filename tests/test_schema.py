from datetime import datetime, timedelta, timezone

import pytest

from marketlab.schema import MarketQuote, Provenance
from marketlab.sources.the_odds_api import estimate_snapshot_credits


def test_historical_cost_formula() -> None:
    assert estimate_snapshot_credits(regions=3, markets=3, snapshots=10) == 900


def test_market_quote_rejects_future_known_at() -> None:
    kickoff = datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc)
    provenance = Provenance(
        source="test",
        source_id="x",
        source_url=None,
        ingested_at=kickoff + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="known_at cannot be after event_time"):
        MarketQuote(
            match_id="m1",
            bookmaker_id="b1",
            market_id="1x2",
            selection_id="home",
            price_decimal=2.0,
            event_time=kickoff,
            known_at=kickoff + timedelta(seconds=1),
            provenance=provenance,
        )


def test_market_quote_normalizes_timezone_to_utc() -> None:
    tz8 = timezone(timedelta(hours=8))
    kickoff = datetime(2026, 8, 1, 23, 0, tzinfo=tz8)
    known = datetime(2026, 8, 1, 20, 0, tzinfo=tz8)
    provenance = Provenance(
        source="test",
        source_id=None,
        source_url=None,
        ingested_at=datetime(2026, 8, 2, 0, 0, tzinfo=tz8),
    )
    quote = MarketQuote(
        match_id="m1",
        bookmaker_id="b1",
        market_id="1x2",
        selection_id="home",
        price_decimal=2.0,
        event_time=kickoff,
        known_at=known,
        provenance=provenance,
    )
    assert quote.event_time.utcoffset() == timedelta(0)
    assert quote.known_at.utcoffset() == timedelta(0)
