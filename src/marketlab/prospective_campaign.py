from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, Sequence

import pandas as pd


DEFAULT_SPORT_ALLOWLIST = (
    "soccer_usa_mls",
    "soccer_brazil_campeonato",
    "soccer_brazil_serie_b",
    "soccer_argentina_primera_division",
    "soccer_mexico_ligamx",
    "soccer_chile_campeonato",
    "soccer_finland_veikkausliiga",
    "soccer_norway_eliteserien",
    "soccer_sweden_allsvenskan",
    "soccer_sweden_superettan",
    "soccer_korea_kleague1",
    "soccer_china_superleague",
    "soccer_league_of_ireland",
    "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_copa_sudamericana",
    "soccer_denmark_superliga",
)


@dataclass(frozen=True, slots=True)
class CampaignPolicy:
    sports: tuple[str, ...] = DEFAULT_SPORT_ALLOWLIST
    maximum_paid_sports_per_run: int = 4
    horizon_hours: float = 60.0
    region: str = "uk"
    market: str = "h2h"
    maximum_paid_credits_per_run: int = 4

    def __post_init__(self) -> None:
        if not self.sports or len(set(self.sports)) != len(self.sports):
            raise ValueError("campaign sports must be non-empty and unique")
        if self.maximum_paid_sports_per_run < 1:
            raise ValueError("maximum paid sports must be positive")
        if self.horizon_hours <= 0:
            raise ValueError("horizon must be positive")
        if not self.region or "," in self.region:
            raise ValueError("campaign region must be exactly one region")
        if self.market != "h2h":
            raise ValueError("campaign is frozen to h2h")
        if self.maximum_paid_credits_per_run < self.maximum_paid_sports_per_run:
            raise ValueError("credit ceiling must cover the maximum selected sports")


@dataclass(frozen=True, slots=True)
class SportSelection:
    sport_key: str
    event_count: int
    weighted_event_score: int
    earliest_commence_time: str
    latest_commence_time: str
    minimum_hours_to_commence: float
    event_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["event_ids"] = list(self.event_ids)
        return result


def utc_iso(value: datetime) -> str:
    """Return provider-compatible UTC ISO-8601 without fractional seconds."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def campaign_window_active(
    now: datetime,
    *,
    start: datetime,
    end: datetime,
) -> bool:
    for value, label in ((now, "now"), (start, "start"), (end, "end")):
        if value.tzinfo is None:
            raise ValueError(f"{label} must be timezone-aware")
    if not start < end:
        raise ValueError("campaign start must precede end")
    return start <= now < end


def _event_rows(
    payload: Any,
    *,
    now: datetime,
    horizon_end: datetime,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for event in payload:
        if not isinstance(event, Mapping):
            continue
        event_id = str(event.get("id", "")).strip()
        commence = pd.to_datetime(event.get("commence_time"), utc=True, errors="coerce")
        if not event_id or pd.isna(commence):
            continue
        commence_dt = commence.to_pydatetime()
        if commence_dt < now or commence_dt > horizon_end:
            continue
        hours = (commence_dt - now).total_seconds() / 3600.0
        rows.append(
            {
                "event_id": event_id,
                "commence": commence_dt,
                "hours": hours,
            }
        )
    rows.sort(key=lambda item: (item["commence"], item["event_id"]))
    return rows


def select_near_event_sports(
    *,
    active_sport_keys: Sequence[str],
    events_by_sport: Mapping[str, Any],
    now: datetime,
    policy: CampaignPolicy = CampaignPolicy(),
) -> list[SportSelection]:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    horizon_end = now + timedelta(hours=policy.horizon_hours)
    active = set(active_sport_keys)
    priority = {sport: index for index, sport in enumerate(policy.sports)}
    ranked: list[tuple[tuple[Any, ...], SportSelection]] = []

    for sport in policy.sports:
        if sport not in active:
            continue
        rows = _event_rows(
            events_by_sport.get(sport),
            now=now,
            horizon_end=horizon_end,
        )
        if not rows:
            continue
        # Near events receive more weight while dense leagues still win ties.
        weighted = sum(
            3 if row["hours"] <= 18 else 2 if row["hours"] <= 36 else 1
            for row in rows
        )
        selection = SportSelection(
            sport_key=sport,
            event_count=len(rows),
            weighted_event_score=weighted,
            earliest_commence_time=utc_iso(rows[0]["commence"]),
            latest_commence_time=utc_iso(rows[-1]["commence"]),
            minimum_hours_to_commence=float(rows[0]["hours"]),
            event_ids=tuple(row["event_id"] for row in rows),
        )
        rank = (
            -selection.weighted_event_score,
            selection.minimum_hours_to_commence,
            -selection.event_count,
            priority[sport],
            sport,
        )
        ranked.append((rank, selection))

    ranked.sort(key=lambda item: item[0])
    return [
        selection
        for _, selection in ranked[: policy.maximum_paid_sports_per_run]
    ]
