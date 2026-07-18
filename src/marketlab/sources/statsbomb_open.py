from __future__ import annotations

from typing import Any

import requests


RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def _get_json(path: str, *, timeout: float = 30.0, session: requests.Session | None = None) -> Any:
    client = session or requests.Session()
    url = f"{RAW_BASE}/{path.lstrip('/')}"
    response = client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_competitions(**kwargs: Any) -> list[dict[str, Any]]:
    payload = _get_json("competitions.json", **kwargs)
    if not isinstance(payload, list):
        raise ValueError("Unexpected competitions payload")
    return payload


def fetch_matches(competition_id: int, season_id: int, **kwargs: Any) -> list[dict[str, Any]]:
    payload = _get_json(f"matches/{competition_id}/{season_id}.json", **kwargs)
    if not isinstance(payload, list):
        raise ValueError("Unexpected matches payload")
    return payload


def fetch_events(match_id: int, **kwargs: Any) -> list[dict[str, Any]]:
    payload = _get_json(f"events/{match_id}.json", **kwargs)
    if not isinstance(payload, list):
        raise ValueError("Unexpected events payload")
    return payload


def fetch_lineups(match_id: int, **kwargs: Any) -> list[dict[str, Any]]:
    payload = _get_json(f"lineups/{match_id}.json", **kwargs)
    if not isinstance(payload, list):
        raise ValueError("Unexpected lineups payload")
    return payload
