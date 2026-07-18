from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd

OUTCOMES = ("home", "draw", "away")
QUOTE_KEYS = ("event_id", "bookmaker_key", "market_key")
NORMAL_FEATURES = (
    "own_current_home_p", "own_current_draw_p", "own_current_away_p",
    "own_prior_home_p", "own_prior_draw_p", "own_prior_away_p",
    "own_delta_home_p", "own_delta_draw_p", "own_delta_away_p",
    "overround_current", "overround_prior", "overround_delta",
    "consensus_current_home_p", "consensus_current_draw_p", "consensus_current_away_p",
    "consensus_prior_home_p", "consensus_prior_draw_p", "consensus_prior_away_p",
    "consensus_delta_home_p", "consensus_delta_draw_p", "consensus_delta_away_p",
    "deviation_current_home_p", "deviation_current_draw_p", "deviation_current_away_p",
    "dispersion_current_home_p", "dispersion_current_draw_p", "dispersion_current_away_p",
    "active_other_books_scaled_31", "other_book_move_fraction", "hours_to_commence_scaled_71",
)
CLOSING_RAW_FEATURES = NORMAL_FEATURES + (
    "actual_move", "actual_delta_home_p", "actual_delta_draw_p", "actual_delta_away_p",
    "observation_home_p", "observation_draw_p", "observation_away_p", "observation_overround",
)
ACTION_RESIDUAL_FEATURES = (
    "conditional_residual_home", "conditional_residual_draw", "conditional_residual_away",
    "conditional_residual_l2", "action_residual_home", "action_residual_draw",
    "action_residual_away", "action_residual_l2",
)
CLOSING_ACTION_FEATURES = CLOSING_RAW_FEATURES + ACTION_RESIDUAL_FEATURES
MODEL_FILES = (
    "normal_hazard", "normal_delta_home", "normal_delta_draw", "normal_delta_away",
    "closing_raw_hazard", "closing_raw_delta_home", "closing_raw_delta_draw", "closing_raw_delta_away",
    "closing_action_hazard", "closing_action_delta_home", "closing_action_delta_draw", "closing_action_delta_away",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_probabilities(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, 1e-6, 1.0)
    return clipped / clipped.sum(axis=1, keepdims=True)


@dataclass(slots=True)
class LoadedShadowBundle:
    directory: Path
    manifest: dict[str, Any]
    models: dict[str, Any]
    manifest_sha256: str

    @property
    def bundle_id(self) -> str:
        return str(self.manifest["bundle_id"])


def load_shadow_bundle(directory: Path) -> LoadedShadowBundle:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_orders = {
        "normal_features": list(NORMAL_FEATURES),
        "closing_raw_features": list(CLOSING_RAW_FEATURES),
        "action_residual_features": list(ACTION_RESIDUAL_FEATURES),
        "closing_action_features": list(CLOSING_ACTION_FEATURES),
    }
    for key, expected in expected_orders.items():
        if manifest.get("feature_order", {}).get(key) != expected:
            raise ValueError(f"bundle feature-order mismatch: {key}")
    models: dict[str, Any] = {}
    files = manifest.get("model_files", {})
    if set(files) != set(MODEL_FILES):
        raise ValueError("bundle model-file set mismatch")
    for name in MODEL_FILES:
        metadata = files[name]
        path = directory / str(metadata["path"])
        if sha256(path) != str(metadata["sha256"]):
            raise ValueError(f"bundle model checksum mismatch: {name}")
        models[name] = joblib.load(path)
    return LoadedShadowBundle(
        directory=directory,
        manifest=manifest,
        models=models,
        manifest_sha256=sha256(manifest_path),
    )


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def build_shadow_feature_records(
    quote_ledger: pd.DataFrame,
    transitions: pd.DataFrame,
    *,
    strict: bool = True,
) -> tuple[pd.DataFrame, dict[str, int]]:
    ledger_required = [
        *QUOTE_KEYS, "snapshot_id", "raw_sha256", "snapshot_ingested_at", "commence_time",
        "home_p", "draw_p", "away_p", "overround",
        "consensus_home_p_ex_target", "consensus_draw_p_ex_target", "consensus_away_p_ex_target",
    ]
    transition_required = [
        *QUOTE_KEYS, "previous_snapshot_id", "snapshot_id", "previous_snapshot_ingested_at",
        "snapshot_ingested_at", "previous_raw_sha256", "raw_sha256", "commence_time",
        "previous_home_p", "previous_draw_p", "previous_away_p", "home_p", "draw_p", "away_p",
        "previous_overround", "overround", "delta_home_p", "delta_draw_p", "delta_away_p",
        "target_book_moved", "other_book_move_fraction", "consensus_other_book_coverage",
        "consensus_home_p_ex_target", "consensus_draw_p_ex_target", "consensus_away_p_ex_target",
        "dispersion_home_p_ex_target", "dispersion_draw_p_ex_target", "dispersion_away_p_ex_target",
        "hours_to_commence", "provider_update_advanced", "state_changed_without_provider_update_advance",
    ]
    _require_columns(quote_ledger, ledger_required, "quote ledger")
    _require_columns(transitions, transition_required, "transitions")
    if quote_ledger.duplicated(["snapshot_id", *QUOTE_KEYS]).any():
        raise ValueError("duplicate quote-ledger snapshot identity")
    if transitions.duplicated(["previous_snapshot_id", "snapshot_id", *QUOTE_KEYS]).any():
        raise ValueError("duplicate transition identity")

    context = transitions.copy()
    realized = transitions.copy()
    context_prefix = {column: f"context_{column}" for column in context.columns if column not in QUOTE_KEYS}
    realized_prefix = {column: f"realized_{column}" for column in realized.columns if column not in QUOTE_KEYS}
    context.rename(columns=context_prefix, inplace=True)
    realized.rename(columns=realized_prefix, inplace=True)
    joined = context.merge(realized, on=list(QUOTE_KEYS), how="inner", validate="many_to_many")
    joined = joined[
        joined["context_snapshot_id"].astype(str)
        == joined["realized_previous_snapshot_id"].astype(str)
    ].copy()
    if joined.empty:
        raise RuntimeError("no three-snapshot context/realization chains")
    if joined.duplicated(["realized_snapshot_id", *QUOTE_KEYS]).any():
        raise ValueError("non-unique three-snapshot chain")

    prior_consensus_columns = [
        "snapshot_id", *QUOTE_KEYS,
        "consensus_home_p_ex_target", "consensus_draw_p_ex_target", "consensus_away_p_ex_target",
    ]
    prior = quote_ledger[prior_consensus_columns].rename(
        columns={
            "snapshot_id": "context_previous_snapshot_id_join",
            "consensus_home_p_ex_target": "consensus_prior_home_p",
            "consensus_draw_p_ex_target": "consensus_prior_draw_p",
            "consensus_away_p_ex_target": "consensus_prior_away_p",
        }
    )
    joined = joined.merge(
        prior,
        left_on=["context_previous_snapshot_id", *QUOTE_KEYS],
        right_on=["context_previous_snapshot_id_join", *QUOTE_KEYS],
        how="left",
        validate="many_to_one",
    )
    invalid_post = joined["realized_snapshot_ingested_at"] >= joined["realized_commence_time"]
    consensus_columns = [
        "consensus_prior_home_p", "consensus_prior_draw_p", "consensus_prior_away_p",
        "context_consensus_home_p_ex_target", "context_consensus_draw_p_ex_target",
        "context_consensus_away_p_ex_target", "context_dispersion_home_p_ex_target",
        "context_dispersion_draw_p_ex_target", "context_dispersion_away_p_ex_target",
        "context_other_book_move_fraction",
    ]
    missing_consensus = joined[consensus_columns].isna().any(axis=1)
    nonpositive_gap = joined["realized_snapshot_ingested_at"] <= joined["context_snapshot_ingested_at"]
    invalid = invalid_post | missing_consensus | nonpositive_gap
    diagnostics = {
        "candidate_chains": int(len(joined)),
        "post_commence_chains": int(invalid_post.sum()),
        "missing_consensus_chains": int(missing_consensus.sum()),
        "nonpositive_time_chains": int(nonpositive_gap.sum()),
        "eligible_chains": int((~invalid).sum()),
    }
    if strict and invalid.any():
        raise ValueError(f"invalid prospective shadow chains: {diagnostics}")
    joined = joined[~invalid].copy()
    if joined.empty:
        raise RuntimeError("no eligible prospective shadow chains")

    current = joined[[f"context_{outcome}_p" for outcome in OUTCOMES]].to_numpy(float)
    prior_p = joined[[f"context_previous_{outcome}_p" for outcome in OUTCOMES]].to_numpy(float)
    consensus_current = joined[[f"context_consensus_{outcome}_p_ex_target" for outcome in OUTCOMES]].to_numpy(float)
    consensus_prior = joined[[f"consensus_prior_{outcome}_p" for outcome in OUTCOMES]].to_numpy(float)
    dispersion = joined[[f"context_dispersion_{outcome}_p_ex_target" for outcome in OUTCOMES]].to_numpy(float)
    delta = current - prior_p
    consensus_delta = consensus_current - consensus_prior
    deviation = current - consensus_current
    features = np.column_stack(
        [
            current, prior_p, delta,
            joined["context_overround"].to_numpy(float),
            joined["context_previous_overround"].to_numpy(float),
            (joined["context_overround"] - joined["context_previous_overround"]).to_numpy(float),
            consensus_current, consensus_prior, consensus_delta, deviation, dispersion,
            joined["context_consensus_other_book_coverage"].to_numpy(float) / 31.0,
            joined["context_other_book_move_fraction"].to_numpy(float),
            joined["context_hours_to_commence"].to_numpy(float) / 71.0,
        ]
    )
    if features.shape[1] != len(NORMAL_FEATURES):
        raise RuntimeError("normal feature-width mismatch")
    if not np.isfinite(features).all():
        raise ValueError("non-finite normal features")

    output = pd.DataFrame(features, columns=NORMAL_FEATURES, index=joined.index)
    provenance = {
        "event_id": joined["event_id"].astype(str),
        "bookmaker_key": joined["bookmaker_key"].astype(str),
        "market_key": joined["market_key"].astype(str),
        "context_previous_snapshot_id": joined["context_previous_snapshot_id"].astype(str),
        "context_snapshot_id": joined["context_snapshot_id"].astype(str),
        "realized_snapshot_id": joined["realized_snapshot_id"].astype(str),
        "context_previous_raw_sha256": joined["context_previous_raw_sha256"].astype(str),
        "context_raw_sha256": joined["context_raw_sha256"].astype(str),
        "realized_raw_sha256": joined["realized_raw_sha256"].astype(str),
        "context_snapshot_ingested_at": joined["context_snapshot_ingested_at"],
        "realized_snapshot_ingested_at": joined["realized_snapshot_ingested_at"],
        "commence_time": joined["realized_commence_time"],
        "provider_update_advanced": joined["realized_provider_update_advanced"],
        "state_changed_without_provider_update_advance": joined[
            "realized_state_changed_without_provider_update_advance"
        ],
        "actual_move": joined["realized_target_book_moved"].astype(int),
        "actual_delta_home_p": joined["realized_delta_home_p"].astype(float),
        "actual_delta_draw_p": joined["realized_delta_draw_p"].astype(float),
        "actual_delta_away_p": joined["realized_delta_away_p"].astype(float),
        "observation_home_p": joined["realized_home_p"].astype(float),
        "observation_draw_p": joined["realized_draw_p"].astype(float),
        "observation_away_p": joined["realized_away_p"].astype(float),
        "observation_overround": joined["realized_overround"].astype(float),
    }
    for name, values in provenance.items():
        output.insert(len(output.columns), name, values.to_numpy() if hasattr(values, "to_numpy") else values)
    output.reset_index(drop=True, inplace=True)
    return output, diagnostics
