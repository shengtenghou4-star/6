from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from marketlab.prospective_sequences import (
    build_closing_targets,
    build_consecutive_transitions,
    build_quote_ledger,
    discover_snapshot_directories,
    materialize_sequence_artifacts,
    verify_snapshot,
)


HOME = "Home FC"
AWAY = "Away FC"
COMMENCE = "2026-07-19T13:00:00Z"
BOOKS = ("book1", "book2", "book3", "book4")


def odds_for(step: int) -> dict[str, tuple[float, float, float]]:
    base = {
        "book1": (2.20, 3.30, 3.10),
        "book2": (2.18, 3.35, 3.12),
        "book3": (2.25, 3.25, 3.05),
        "book4": (2.22, 3.28, 3.08),
    }
    if step >= 2:
        base["book1"] = (2.05, 3.45, 3.35)
    if step >= 3:
        base["book2"] = (2.08, 3.42, 3.28)
    if step >= 4:
        base["book3"] = (2.30, 3.20, 2.98)
    return base


def write_snapshot(
    root: Path,
    *,
    snapshot_id: str,
    ingested_at: str,
    step: int,
    duplicate_time_nonce: str = "",
    include_incomplete: bool = False,
) -> Path:
    directory = root / snapshot_id
    directory.mkdir(parents=True)
    raw = json.dumps(
        {"snapshot": snapshot_id, "ingested_at": ingested_at, "nonce": duplicate_time_nonce},
        sort_keys=True,
    ).encode("utf-8")
    (directory / "raw-response.json").write_bytes(raw)
    raw_sha = hashlib.sha256(raw).hexdigest()
    rows: list[dict[str, object]] = []
    for book, (home, draw, away) in odds_for(step).items():
        provider_update = {
            1: "2026-07-19T09:59:00Z",
            2: "2026-07-19T09:59:00Z" if book == "book1" else "2026-07-19T10:59:00Z",
            3: "2026-07-19T11:59:00Z",
            4: "2026-07-19T13:59:00Z",
        }[step]
        for outcome, price in ((HOME, home), ("Draw", draw), (AWAY, away)):
            rows.append(
                {
                    "provider": "the_odds_api_v4",
                    "snapshot_ingested_at_utc": ingested_at,
                    "event_id": "event-1",
                    "sport_key": "soccer_epl",
                    "sport_title": "EPL",
                    "commence_time": COMMENCE,
                    "commence_time_valid": True,
                    "home_team": HOME,
                    "away_team": AWAY,
                    "bookmaker_key": book,
                    "bookmaker_title": book.title(),
                    "bookmaker_last_update": provider_update,
                    "bookmaker_last_update_valid": True,
                    "market_key": "h2h",
                    "market_last_update": provider_update,
                    "market_last_update_valid": True,
                    "outcome_name": outcome,
                    "outcome_description": "",
                    "price_decimal": price,
                    "price_valid_decimal": True,
                    "point": "",
                    "point_present": False,
                    "outcome_link": "",
                    "outcome_sid": "",
                }
            )
    if include_incomplete:
        for outcome, price in ((HOME, 2.10), (AWAY, 3.20)):
            rows.append(
                {
                    **rows[0],
                    "bookmaker_key": "incomplete-book",
                    "bookmaker_title": "Incomplete Book",
                    "outcome_name": outcome,
                    "price_decimal": price,
                }
            )
    normalized = directory / "normalized-outcomes.csv"
    with normalized.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema_version": 1,
        "provider": "the_odds_api_v4",
        "ingested_at_utc": ingested_at,
        "raw": {"path": "raw-response.json", "bytes": len(raw), "sha256": raw_sha},
        "normalized": {"path": "normalized-outcomes.csv", "rows": len(rows)},
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return directory


def build_fixture_root(tmp_path: Path) -> tuple[Path, list[Path]]:
    root = tmp_path / "snapshots"
    directories = [
        write_snapshot(root, snapshot_id="s1", ingested_at="2026-07-19T10:00:00Z", step=1),
        write_snapshot(
            root,
            snapshot_id="s2",
            ingested_at="2026-07-19T11:00:00Z",
            step=2,
            include_incomplete=True,
        ),
        write_snapshot(root, snapshot_id="s3", ingested_at="2026-07-19T12:00:00Z", step=3),
        write_snapshot(root, snapshot_id="s4", ingested_at="2026-07-19T14:00:00Z", step=4),
    ]
    return root, directories


def test_builds_quote_transition_and_pre_commence_closing_ledgers(tmp_path: Path) -> None:
    root, directories = build_fixture_root(tmp_path)
    assert discover_snapshot_directories(root) == directories
    ledger, diagnostics = build_quote_ledger(directories)
    assert len(ledger) == 16
    assert diagnostics.snapshots == 4
    assert diagnostics.incomplete_quote_groups == 1
    assert diagnostics.post_commence_quote_states == 4
    assert set(ledger["consensus_other_book_coverage"]) == {3}
    stale_change = ledger[
        (ledger["snapshot_id"] == "s2") & (ledger["bookmaker_key"] == "book1")
    ].iloc[0]
    assert bool(stale_change["quote_changed_from_previous"]) is True
    assert bool(stale_change["state_changed_without_provider_update_advance"]) is True

    transitions = build_consecutive_transitions(ledger)
    assert len(transitions) == 12
    assert set(transitions["other_book_transition_coverage"]) == {3}
    assert transitions["previous_raw_sha256"].str.len().eq(64).all()
    assert transitions["raw_sha256"].str.len().eq(64).all()

    closing = build_closing_targets(ledger)
    assert len(closing) == 8
    assert set(closing["closing_snapshot_id"]) == {"s3"}
    assert (closing["closing_snapshot_ingested_at"] < closing["commence_time"]).all()
    assert not closing["closing_snapshot_id"].eq("s4").any()
    assert closing.filter(like="closing_log_odds_clv_").notna().all().all()


def test_materialization_is_deterministic_and_outcome_blind(tmp_path: Path) -> None:
    root, _ = build_fixture_root(tmp_path)
    output = tmp_path / "derived"
    manifest = materialize_sequence_artifacts(snapshots_root=root, output_root=output)
    assert manifest["diagnostics"]["quote_states"] == 16
    assert manifest["outputs"]["transitions"]["rows"] == 12
    assert manifest["outputs"]["closing_targets"]["rows"] == 8
    assert manifest["outcome_blind"] is True
    for name in ("quote-ledger.csv.gz", "consecutive-transitions.csv.gz", "closing-targets.csv.gz"):
        assert (output / name).is_file()
    loaded = pd.read_csv(output / "closing-targets.csv.gz")
    assert not any(column in loaded.columns for column in ("result", "winner", "home_score", "away_score"))


def test_raw_tamper_is_rejected(tmp_path: Path) -> None:
    root, directories = build_fixture_root(tmp_path)
    victim = directories[0]
    (victim / "raw-response.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_snapshot(victim)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_quote_ledger(discover_snapshot_directories(root))


def test_duplicate_ingestion_timestamp_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "duplicates"
    first = write_snapshot(
        root,
        snapshot_id="a",
        ingested_at="2026-07-19T10:00:00Z",
        step=1,
        duplicate_time_nonce="a",
    )
    second = write_snapshot(
        root,
        snapshot_id="b",
        ingested_at="2026-07-19T10:00:00Z",
        step=2,
        duplicate_time_nonce="b",
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        build_quote_ledger([first, second])
