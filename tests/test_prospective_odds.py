from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from marketlab.prospective_odds import (
    SnapshotRequest,
    archive_current_odds_snapshot,
    normalize_current_odds_payload,
    parse_csv_tuple,
)


FIXTURE = Path(__file__).parent / "fixtures" / "the_odds_api_current_odds_sample.json"
INGESTED_AT = "2026-07-19T12:35:00.123456Z"


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def fixture_payload() -> object:
    return json.loads(fixture_bytes().decode("utf-8"))


def test_request_exposes_no_secret_parameters() -> None:
    request = SnapshotRequest(
        sport="soccer_epl",
        markets=("h2h", "spreads"),
        bookmakers=("bet365", "pinnacle"),
    )
    public = request.public_parameters()
    secure = request.secure_parameters("secret-value")
    assert "apiKey" not in public
    assert secure["apiKey"] == "secret-value"
    assert public["bookmakers"] == "bet365,pinnacle"
    assert "regions" not in public


def test_request_requires_exactly_one_location_selector() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        SnapshotRequest(sport="soccer_epl", regions=(), bookmakers=())
    with pytest.raises(ValueError, match="exactly one"):
        SnapshotRequest(sport="soccer_epl", regions=("uk",), bookmakers=("bet365",))


def test_fixture_normalizes_without_silent_loss() -> None:
    rows, diagnostics = normalize_current_odds_payload(
        fixture_payload(),
        ingested_at_utc=INGESTED_AT,
    )
    assert diagnostics.events_seen == 1
    assert diagnostics.bookmakers_seen == 2
    assert diagnostics.markets_seen == 3
    assert diagnostics.outcomes_seen == 8
    assert diagnostics.normalized_rows == 8
    assert diagnostics.invalid_decimal_prices == 0
    assert diagnostics.invalid_commence_times == 0
    assert {row["bookmaker_key"] for row in rows} == {"bet365", "pinnacle"}
    spread_rows = [row for row in rows if row["market_key"] == "spreads"]
    assert len(spread_rows) == 2
    assert all(row["point_present"] is True for row in spread_rows)


def test_invalid_values_are_retained_and_flagged() -> None:
    payload = fixture_payload()
    payload[0]["commence_time"] = "not-a-time"
    payload[0]["bookmakers"][0]["last_update"] = "bad-update"
    payload[0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = 1.0
    rows, diagnostics = normalize_current_odds_payload(payload, ingested_at_utc=INGESTED_AT)
    assert len(rows) == 8
    assert diagnostics.invalid_commence_times == 1
    assert diagnostics.invalid_bookmaker_update_times == 1
    assert diagnostics.invalid_decimal_prices == 1
    bad = next(row for row in rows if row["bookmaker_key"] == "bet365" and row["outcome_name"] == "Home FC")
    assert bad["price_decimal"] == 1.0
    assert bad["price_valid_decimal"] is False
    assert bad["commence_time_valid"] is False


def test_archive_preserves_raw_bytes_manifest_and_immutability(tmp_path: Path) -> None:
    request = SnapshotRequest(
        sport="soccer_epl",
        markets=("h2h", "spreads"),
        regions=("uk", "eu"),
    )
    raw = fixture_bytes()
    directory = archive_current_odds_snapshot(
        output_root=tmp_path,
        request=request,
        raw_response_bytes=raw,
        response_headers={
            "content-type": "application/json",
            "x-requests-remaining": "499",
            "x-requests-used": "1",
            "x-requests-last": "2",
        },
        ingested_at_utc=INGESTED_AT,
        http_status=200,
        response_url_without_api_key=(
            "https://api.the-odds-api.com/v4/sports/soccer_epl/odds?"
            "markets=h2h%2Cspreads&regions=uk%2Ceu&oddsFormat=decimal&dateFormat=iso"
        ),
    )
    assert (directory / "raw-response.json").read_bytes() == raw
    manifest_text = (directory / "manifest.json").read_text(encoding="utf-8")
    assert "secret-value" not in manifest_text
    assert "apikey" not in manifest_text.casefold()
    manifest = json.loads(manifest_text)
    assert manifest["normalized"]["rows"] == 8
    assert manifest["normalized"]["unique_events"] == 1
    assert manifest["normalized"]["unique_bookmakers"] == 2
    assert manifest["response_headers"]["quota"]["x-requests-last"] == "2"
    with (directory / "normalized-outcomes.csv").open(encoding="utf-8", newline="") as fh:
        normalized = list(csv.DictReader(fh))
    assert len(normalized) == 8

    with pytest.raises(FileExistsError, match="immutable snapshot directory"):
        archive_current_odds_snapshot(
            output_root=tmp_path,
            request=request,
            raw_response_bytes=raw,
            response_headers={},
            ingested_at_utc=INGESTED_AT,
            http_status=200,
            response_url_without_api_key="https://api.the-odds-api.com/v4/sports/soccer_epl/odds",
        )


def test_parse_csv_tuple_is_deterministic() -> None:
    assert parse_csv_tuple(" uk, eu ,, ") == ("uk", "eu")
    assert parse_csv_tuple(None) == ()
