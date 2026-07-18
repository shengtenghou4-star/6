from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .prospective_sequence_states import (
    QUOTE_KEYS,
    SNAPSHOT_QUOTE_KEYS,
    SequenceDiagnostics,
    SnapshotEvidence,
    _sha256,
    build_quote_ledger,
    discover_snapshot_directories,
    verify_snapshot,
)


def build_consecutive_transitions(ledger: pd.DataFrame) -> pd.DataFrame:
    required = set(SNAPSHOT_QUOTE_KEYS + [
        "previous_snapshot_id", "snapshot_ingested_at", "quote_changed_from_previous",
        "home_p", "draw_p", "away_p", "home_odds", "draw_odds", "away_odds",
        "raw_sha256", "hours_to_commence",
    ])
    missing = sorted(required - set(ledger.columns))
    if missing:
        raise ValueError(f"ledger missing transition columns: {missing}")
    current = ledger[ledger["previous_snapshot_id"].notna()].copy()
    if current.empty:
        raise RuntimeError("at least two observations per quote are required")
    previous_columns = {
        "snapshot_id": "previous_snapshot_id_join",
        "snapshot_ingested_at": "previous_snapshot_ingested_at",
        "raw_sha256": "previous_raw_sha256",
        "home_p": "previous_home_p",
        "draw_p": "previous_draw_p",
        "away_p": "previous_away_p",
        "home_odds": "previous_home_odds",
        "draw_odds": "previous_draw_odds",
        "away_odds": "previous_away_odds",
        "overround": "previous_overround",
    }
    previous = ledger[["snapshot_id", *QUOTE_KEYS, *[key for key in previous_columns if key != "snapshot_id"]]].rename(
        columns=previous_columns
    )
    transitions = current.merge(
        previous,
        left_on=["previous_snapshot_id", *QUOTE_KEYS],
        right_on=["previous_snapshot_id_join", *QUOTE_KEYS],
        how="inner",
        validate="many_to_one",
    )
    for outcome in ("home", "draw", "away"):
        transitions[f"delta_{outcome}_p"] = (
            transitions[f"{outcome}_p"] - transitions[f"previous_{outcome}_p"]
        )
    transitions["target_book_moved"] = transitions["quote_changed_from_previous"].astype(bool)
    pair_keys = ["event_id", "market_key", "previous_snapshot_id", "snapshot_id"]
    transitions["other_book_move_fraction"] = np.nan
    transitions["other_book_transition_coverage"] = 0
    for _, pair in transitions.groupby(pair_keys, sort=False):
        indices = pair.index.to_numpy()
        moved = pair["target_book_moved"].to_numpy(dtype=float)
        for position, index in enumerate(indices):
            other = np.delete(moved, position)
            transitions.at[index, "other_book_transition_coverage"] = len(other)
            if len(other):
                transitions.at[index, "other_book_move_fraction"] = float(other.mean())
    keep = [
        "event_id", "sport_key", "home_team", "away_team", "commence_time",
        "bookmaker_key", "bookmaker_title", "market_key",
        "previous_snapshot_id", "snapshot_id", "previous_snapshot_ingested_at",
        "snapshot_ingested_at", "previous_raw_sha256", "raw_sha256",
        "seconds_since_previous_observation", "hours_to_commence",
        "target_book_moved", "provider_update_advanced",
        "state_changed_without_provider_update_advance",
        "previous_home_odds", "previous_draw_odds", "previous_away_odds",
        "home_odds", "draw_odds", "away_odds",
        "previous_home_p", "previous_draw_p", "previous_away_p",
        "home_p", "draw_p", "away_p",
        "delta_home_p", "delta_draw_p", "delta_away_p",
        "previous_overround", "overround",
        "consensus_other_book_coverage",
        "consensus_home_p_ex_target", "consensus_draw_p_ex_target", "consensus_away_p_ex_target",
        "dispersion_home_p_ex_target", "dispersion_draw_p_ex_target", "dispersion_away_p_ex_target",
        "other_book_transition_coverage", "other_book_move_fraction",
    ]
    return transitions[keep].sort_values(
        ["snapshot_ingested_at", "event_id", "bookmaker_key"], kind="mergesort"
    ).reset_index(drop=True)


def build_closing_targets(ledger: pd.DataFrame) -> pd.DataFrame:
    pre = ledger[ledger["snapshot_ingested_at"] < ledger["commence_time"]].copy()
    if pre.empty:
        raise RuntimeError("no pre-commence quote states")
    pre.sort_values([*QUOTE_KEYS, "snapshot_ingested_at", "snapshot_id"], inplace=True, kind="mergesort")
    closing = pre.groupby(QUOTE_KEYS, sort=False, as_index=False).tail(1).copy()
    close_columns = {
        "snapshot_id": "closing_snapshot_id",
        "snapshot_ingested_at": "closing_snapshot_ingested_at",
        "raw_sha256": "closing_raw_sha256",
        "home_odds": "closing_home_odds",
        "draw_odds": "closing_draw_odds",
        "away_odds": "closing_away_odds",
        "home_p": "closing_home_p",
        "draw_p": "closing_draw_p",
        "away_p": "closing_away_p",
        "overround": "closing_overround",
    }
    closing = closing[[*QUOTE_KEYS, *close_columns]].rename(columns=close_columns)
    targets = pre.merge(closing, on=QUOTE_KEYS, how="inner", validate="many_to_one")
    targets = targets[
        targets["snapshot_ingested_at"] < targets["closing_snapshot_ingested_at"]
    ].copy()
    if targets.empty:
        raise RuntimeError("no earlier observations before closing states")
    for outcome in ("home", "draw", "away"):
        targets[f"closing_delta_{outcome}_p"] = (
            targets[f"closing_{outcome}_p"] - targets[f"{outcome}_p"]
        )
        targets[f"closing_log_odds_clv_{outcome}"] = np.log(
            targets[f"{outcome}_odds"] / targets[f"closing_{outcome}_odds"]
        )
    keep = [
        "event_id", "sport_key", "home_team", "away_team", "commence_time",
        "bookmaker_key", "bookmaker_title", "market_key",
        "snapshot_id", "snapshot_ingested_at", "raw_sha256",
        "closing_snapshot_id", "closing_snapshot_ingested_at", "closing_raw_sha256",
        "hours_to_commence",
        "home_odds", "draw_odds", "away_odds",
        "closing_home_odds", "closing_draw_odds", "closing_away_odds",
        "home_p", "draw_p", "away_p",
        "closing_home_p", "closing_draw_p", "closing_away_p",
        "closing_delta_home_p", "closing_delta_draw_p", "closing_delta_away_p",
        "closing_log_odds_clv_home", "closing_log_odds_clv_draw", "closing_log_odds_clv_away",
        "overround", "closing_overround",
    ]
    return targets[keep].sort_values(
        ["snapshot_ingested_at", "event_id", "bookmaker_key"], kind="mergesort"
    ).reset_index(drop=True)


def materialize_sequence_artifacts(
    *,
    snapshots_root: Path,
    output_root: Path,
    market_key: str = "h2h",
    minimum_other_books: int = 3,
) -> dict[str, Any]:
    directories = discover_snapshot_directories(snapshots_root)
    ledger, diagnostics = build_quote_ledger(
        directories,
        market_key=market_key,
        minimum_other_books=minimum_other_books,
    )
    transitions = build_consecutive_transitions(ledger)
    closing = build_closing_targets(ledger)
    output_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "quote_ledger": output_root / "quote-ledger.csv.gz",
        "transitions": output_root / "consecutive-transitions.csv.gz",
        "closing_targets": output_root / "closing-targets.csv.gz",
    }
    ledger.to_csv(paths["quote_ledger"], index=False, compression="gzip")
    transitions.to_csv(paths["transitions"], index=False, compression="gzip")
    closing.to_csv(paths["closing_targets"], index=False, compression="gzip")
    manifest = {
        "schema_version": 1,
        "market_key": market_key,
        "minimum_other_books": minimum_other_books,
        "snapshots_root": str(snapshots_root),
        "snapshot_directories": [path.name for path in directories],
        "diagnostics": asdict(diagnostics),
        "outputs": {
            name: {
                "path": path.name,
                "rows": int(len(frame)),
                "sha256": _sha256(path),
            }
            for name, path, frame in (
                ("quote_ledger", paths["quote_ledger"], ledger),
                ("transitions", paths["transitions"], transitions),
                ("closing_targets", paths["closing_targets"], closing),
            )
        },
        "outcome_blind": True,
        "forbidden_fields": ["home_score", "away_score", "result", "winner"],
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest
