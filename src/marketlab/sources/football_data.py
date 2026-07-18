from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Iterable

import requests


BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"


@dataclass(frozen=True, slots=True)
class FootballDataSample:
    season: str
    division: str
    rows: list[dict[str, str]]
    source_url: str


def fetch_season_division(
    season: str,
    division: str,
    *,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> FootballDataSample:
    """Fetch one public Football-Data CSV.

    Example season: ``2526``. Example division: ``E0`` (English Premier League).
    Raw bytes should be preserved by the caller before transformation in production.
    """
    client = session or requests.Session()
    url = BASE_URL.format(season=season, division=division)
    response = client.get(url, timeout=timeout)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError(f"No rows returned from {url}")
    return FootballDataSample(season=season, division=division, rows=rows, source_url=url)


def summarize_columns(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    result: dict[str, int] = {}
    count = 0
    for row in rows:
        count += 1
        for key, value in row.items():
            if value not in (None, ""):
                result[key] = result.get(key, 0) + 1
    result["__rows__"] = count
    return result
