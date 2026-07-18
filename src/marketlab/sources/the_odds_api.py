from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


BASE_URL = "https://api.the-odds-api.com/v4"


@dataclass(frozen=True, slots=True)
class HistoricalQuery:
    sport: str
    regions: tuple[str, ...]
    markets: tuple[str, ...]
    snapshot_at: datetime

    @property
    def estimated_credits(self) -> int:
        # Official historical featured-market formula: 10 x regions x markets.
        return 10 * len(self.regions) * len(self.markets)


def estimate_snapshot_credits(*, regions: int, markets: int, snapshots: int) -> int:
    if min(regions, markets, snapshots) < 0:
        raise ValueError("regions, markets and snapshots must be non-negative")
    return 10 * regions * markets * snapshots


def fetch_historical_snapshot(
    api_key: str,
    query: HistoricalQuery,
    *,
    odds_format: str = "decimal",
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if not api_key:
        raise ValueError("api_key is required")
    if query.snapshot_at.tzinfo is None or query.snapshot_at.utcoffset() is None:
        raise ValueError("snapshot_at must be timezone-aware")
    client = session or requests.Session()
    url = f"{BASE_URL}/historical/sports/{query.sport}/odds"
    params = {
        "apiKey": api_key,
        "regions": ",".join(query.regions),
        "markets": ",".join(query.markets),
        "oddsFormat": odds_format,
        "date": query.snapshot_at.isoformat().replace("+00:00", "Z"),
    }
    response = client.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    headers = {
        key.lower(): value
        for key, value in response.headers.items()
        if key.lower() in {"x-requests-used", "x-requests-remaining", "x-requests-last"}
    }
    payload = response.json()
    if not isinstance(payload, dict) or "timestamp" not in payload or "data" not in payload:
        raise ValueError("Unexpected historical odds response shape")
    return payload, headers
