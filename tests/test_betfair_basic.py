from marketlab.sources.betfair_basic import extract_ltp_changes


def test_extract_ltp_changes() -> None:
    messages = [
        {
            "op": "mcm",
            "pt": 1700000000000,
            "mc": [
                {
                    "id": "1.23456789",
                    "marketDefinition": {"status": "OPEN", "inPlay": False},
                    "rc": [
                        {"id": 101, "ltp": 2.12},
                        {"id": 102, "ltp": 3.4},
                        {"id": 103},
                    ],
                }
            ],
        }
    ]
    changes = list(extract_ltp_changes(messages))
    assert len(changes) == 2
    assert changes[0].market_id == "1.23456789"
    assert changes[0].selection_id == 101
    assert changes[0].last_traded_price == 2.12
    assert changes[0].market_status == "OPEN"
    assert changes[0].in_play is False
