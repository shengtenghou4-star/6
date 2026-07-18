from __future__ import annotations

import bz2
import json
from pathlib import Path

from marketlab.sources.betfair_historical import (
    flatten_market_change_message,
    iter_bz2_updates,
    publish_time_from_ms,
)


def test_publish_time_is_utc() -> None:
    dt = publish_time_from_ms(1719210499670)
    assert dt.isoformat() == "2024-06-24T06:28:19.670000+00:00"


def test_definition_only_message_is_preserved() -> None:
    # Structure based on Betfair's official Advanced Historical Data interpretation example.
    message = {
        "op": "mcm",
        "pt": 1719210499670,
        "mc": [
            {
                "id": "1.229978426",
                "marketDefinition": {
                    "eventId": "33356803",
                    "marketType": "MATCH_ODDS",
                    "marketTime": "2024-07-01T00:00:00.000Z",
                    "status": "OPEN",
                    "inPlay": False,
                    "eventName": "Jamaica v Venezuela",
                },
            }
        ],
    }
    updates = flatten_market_change_message(message)
    assert len(updates) == 1
    update = updates[0]
    assert update.market_id == "1.229978426"
    assert update.event_id == "33356803"
    assert update.market_type == "MATCH_ODDS"
    assert update.runner_id is None


def test_runner_price_ladders_are_normalized() -> None:
    message = {
        "op": "mcm",
        "pt": 1719210499670,
        "mc": [
            {
                "id": "1.229978426",
                "rc": [
                    {
                        "id": 54786,
                        "ltp": 2.18,
                        "tv": 1234.5,
                        "batb": [[0, 2.16, 100.0], [1, 2.14, 50]],
                        "batl": [[0, 2.2, 80.0]],
                        "trd": [[2.18, 500.0]],
                    }
                ],
            }
        ],
    }
    update = flatten_market_change_message(message)[0]
    assert update.runner_id == 54786
    assert update.last_traded_price == 2.18
    assert update.runner_total_matched == 1234.5
    assert update.available_to_back == [[0.0, 2.16, 100.0], [1.0, 2.14, 50.0]]
    assert update.available_to_lay == [[0.0, 2.2, 80.0]]
    assert update.traded_volume == [[2.18, 500.0]]


def test_bz2_line_stream(tmp_path: Path) -> None:
    path = tmp_path / "market.bz2"
    messages = [
        {"op": "status", "statusCode": "SUCCESS"},
        {"op": "mcm", "pt": 1719210499670, "mc": [{"id": "1.1", "rc": [{"id": 1, "ltp": 3.5}]}]},
    ]
    with bz2.open(path, "wt", encoding="utf-8") as fh:
        for message in messages:
            fh.write(json.dumps(message) + "\n")

    updates = list(iter_bz2_updates(path))
    assert len(updates) == 1
    assert updates[0].market_id == "1.1"
    assert updates[0].runner_id == 1
    assert updates[0].last_traded_price == 3.5
