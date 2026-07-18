from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    source_id: str | None
    source_url: str | None
    ingested_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "ingested_at", _require_aware_utc(self.ingested_at, "ingested_at"))


@dataclass(frozen=True, slots=True)
class MarketQuote:
    match_id: str
    bookmaker_id: str
    market_id: str
    selection_id: str
    price_decimal: float
    event_time: datetime
    known_at: datetime
    provenance: Provenance
    line: float | None = None
    is_suspended: bool | None = None
    raw_payload_ref: str | None = None

    def __post_init__(self) -> None:
        if self.price_decimal <= 1.0:
            raise ValueError("price_decimal must be > 1.0")
        event_time = _require_aware_utc(self.event_time, "event_time")
        known_at = _require_aware_utc(self.known_at, "known_at")
        if known_at > event_time:
            raise ValueError("known_at cannot be after event_time for a pre-match quote")
        object.__setattr__(self, "event_time", event_time)
        object.__setattr__(self, "known_at", known_at)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_time"] = self.event_time.isoformat()
        data["known_at"] = self.known_at.isoformat()
        data["provenance"]["ingested_at"] = self.provenance.ingested_at.isoformat()
        return data


@dataclass(frozen=True, slots=True)
class MatchRecord:
    match_id: str
    competition_id: str
    home_team_id: str
    away_team_id: str
    kickoff_time: datetime
    known_at: datetime
    provenance: Provenance
    status: str | None = None
    home_score: int | None = None
    away_score: int | None = None

    def __post_init__(self) -> None:
        kickoff = _require_aware_utc(self.kickoff_time, "kickoff_time")
        known_at = _require_aware_utc(self.known_at, "known_at")
        object.__setattr__(self, "kickoff_time", kickoff)
        object.__setattr__(self, "known_at", known_at)

        # A record may be ingested after kickoff, but model-building code must filter by known_at.
        if self.home_score is not None and self.home_score < 0:
            raise ValueError("home_score cannot be negative")
        if self.away_score is not None and self.away_score < 0:
            raise ValueError("away_score cannot be negative")
