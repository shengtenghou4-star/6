from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


@dataclass(frozen=True, slots=True)
class WeatherQuery:
    latitude: float
    longitude: float
    start_date: str
    end_date: str
    hourly: tuple[str, ...]


def fetch_historical_forecast(
    query: WeatherQuery,
    *,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch historical forecast data.

    Callers must preserve the source response and explicitly track forecast/run vintage.
    Do not reinterpret realized/reanalysis weather as a forecast known before kickoff.
    """
    client = session or requests.Session()
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {
        "latitude": query.latitude,
        "longitude": query.longitude,
        "start_date": query.start_date,
        "end_date": query.end_date,
        "hourly": ",".join(query.hourly),
        "timezone": "UTC",
    }
    response = client.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "hourly" not in payload:
        raise ValueError("Unexpected Open-Meteo response shape")
    return payload
