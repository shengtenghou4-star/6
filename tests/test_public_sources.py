from __future__ import annotations

import requests


TIMEOUT = 30


def test_the_odds_api_official_epl_historical_sample() -> None:
    url = "https://public-odds-api-sample-data.s3.amazonaws.com/historical-epl.json"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload.get("timestamp")
    assert isinstance(payload.get("data"), list)
    assert payload["data"]
    assert any(event.get("bookmakers") for event in payload["data"])


def test_football_data_public_epl_csv() -> None:
    url = "https://www.football-data.co.uk/mmz4281/2526/E0.csv"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="replace")
    header = text.splitlines()[0]
    assert "HomeTeam" in header
    assert "AwayTeam" in header
    assert len(text.splitlines()) > 20


def test_statsbomb_open_competitions() -> None:
    url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    assert {"competition_id", "season_id"}.issubset(payload[0])
