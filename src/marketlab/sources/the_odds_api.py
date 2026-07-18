from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


BASE_URL = "https://api.the-odds-api.com/v4"
PUBLIC_SAMPLE_URLS = {
    "epl_2021": "https://public-odds-api-sample-data.s3.amazonaws.com/historical-epl.json",
    "bundesliga_2022": "https://public-odds-api-sample-data.s3.amazonaws.com/historical-bundesliga.json",
}
PUBLIC_EPL_SAMPLE_URL = PUBLIC_SAMPLE_URLS["epl_2021"]


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


def _validate_historical_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or "timestamp" not in payload or "data" not in payload:
        raise ValueError("Unexpected historical odds response shape")
    if not isinstance(payload["data"], list):
        raise ValueError("Historical odds data must be a list")
    return payload


def fetch_public_sample(
    sample_key: str,
    *,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    try:
        url = PUBLIC_SAMPLE_URLS[sample_key]
    except KeyError as exc:
        raise ValueError(f"unknown official public sample: {sample_key}") from exc
    client = session or requests.Session()
    response = client.get(url, timeout=timeout)
    response.raise_for_status()
    return _validate_historical_payload(response.json())


def fetch_public_epl_sample(
    *,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Backwards-compatible helper for the official historical EPL sample."""
    return fetch_public_sample("epl_2021", timeout=timeout, session=session)


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
    return _validate_historical_payload(response.json()), headers
