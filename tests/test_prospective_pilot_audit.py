from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlab.prospective_odds import SnapshotRequest, archive_current_odds_snapshot
from marketlab.prospective_pilot_audit import (
    PilotAuditPolicy,
    audit_snapshot_directory,
    audit_snapshot_root,
)


INGESTED_AT = "2026-07-19T12:00:00Z"
SECRET = "pilot-secret-value"


def payload(*, books: int = 4, events: int = 2) -> list[dict[str, object]]:
    output = []
    for event_index in range(events):
        home = f"Home {event_index}"
        away = f"Away {event_index}"
        bookmakers = []
        for book_index in range(books):
            update = "2026-07-19T11:58:00Z"
            bookmakers.append(
                {
                    "key": f"book{book_index}",
                    "title": f"Book {book_index}",
                    "last_update": update,
                    "markets": [
                        {
                            "key": "h2h",
                            "last_update": update,
                            "outcomes": [
                                {"name": home, "price": 2.10 + book_index * 0.01},
                                {"name": "Draw", "price": 3.30},
                                {"name": away, "price": 3.20 - book_index * 0.01},
                            ],
                        }
                    ],
                }
            )
        output.append(
            {
                "id": f"event-{event_index}",
                "sport_key": "soccer_epl",
                "sport_title": "EPL",
                "commence_time": "2026-07-20T12:00:00Z",
                "home_team": home,
                "away_team": away,
                "bookmakers": bookmakers,
            }
        )
    return output


def archive(
    root: Path,
    *,
    regions: tuple[str, ...] = ("uk",),
    bookmakers: tuple[str, ...] = (),
    books: int = 4,
    events: int = 2,
    cost: str = "1",
) -> Path:
    request = SnapshotRequest(
        sport="soccer_epl",
        markets=("h2h",),
        regions=regions,
        bookmakers=bookmakers,
    )
    return archive_current_odds_snapshot(
        output_root=root,
        request=request,
        raw_response_bytes=json.dumps(payload(books=books, events=events)).encode("utf-8"),
        response_headers={
            "content-type": "application/json",
            "x-requests-remaining": "499",
            "x-requests-used": "1",
            "x-requests-last": cost,
        },
        ingested_at_utc=INGESTED_AT,
        http_status=200,
        response_url_without_api_key=(
            "https://api.the-odds-api.com/v4/sports/soccer_epl/odds?"
            "markets=h2h&regions=uk&oddsFormat=decimal&dateFormat=iso"
        ),
    )


def test_authenticated_snapshot_passes_connection_and_repeated_pilot_gate(tmp_path: Path) -> None:
    directory = archive(tmp_path)
    report = audit_snapshot_directory(directory, secret_value=SECRET)
    assert report["decisions"]["authenticated_source_connected"] is True
    assert report["decisions"]["suitable_for_repeated_snapshot_pilot"] is True
    assert report["decisions"]["suitable_for_untouched_repricing_clv_now"] is False
    assert report["quota"]["last"] == 1
    assert report["coverage"]["events"] == 2
    assert report["coverage"]["complete_h2h_quote_states"] == 8
    assert report["coverage"]["complete_books_per_event_min"] == 4
    assert report["blocking_reasons"] == []
    assert audit_snapshot_root(tmp_path, secret_value=SECRET)["snapshot"]["snapshot_id"] == directory.name


def test_cost_and_book_coverage_fail_repeated_pilot_without_breaking_connectivity(tmp_path: Path) -> None:
    directory = archive(tmp_path, books=3, cost="2")
    report = audit_snapshot_directory(directory, secret_value=SECRET)
    assert report["decisions"]["authenticated_source_connected"] is True
    assert report["decisions"]["suitable_for_repeated_snapshot_pilot"] is False
    assert "quota.pilot_cost_at_most_one" in report["blocking_reasons"]
    assert "coverage.event_book_coverage_fraction" in report["blocking_reasons"]


def test_two_region_request_fails_frozen_pilot_scope(tmp_path: Path) -> None:
    directory = archive(tmp_path, regions=("uk", "eu"), cost="2")
    report = audit_snapshot_directory(directory, secret_value=SECRET)
    assert report["request_scope"]["checks"]["one_region_maximum"] is False
    assert report["decisions"]["suitable_for_repeated_snapshot_pilot"] is False


def test_secret_leak_and_tampering_are_rejected(tmp_path: Path) -> None:
    directory = archive(tmp_path)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["debug_secret"] = SECRET
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = audit_snapshot_directory(directory, secret_value=SECRET)
    assert report["secret_safety"]["passed"] is False
    assert report["decisions"]["authenticated_source_connected"] is False

    (directory / "raw-response.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit_snapshot_directory(directory, secret_value=SECRET)


def test_first_pilot_root_requires_exactly_one_snapshot(tmp_path: Path) -> None:
    archive(tmp_path / "one")
    archive(tmp_path / "two")
    with pytest.raises(ValueError, match="exactly one snapshot"):
        audit_snapshot_root(tmp_path, secret_value=SECRET)
