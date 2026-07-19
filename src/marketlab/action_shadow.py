from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import sklearn

from .action_shadow_schema import (
    ACTION_RESIDUAL_FEATURES,
    CLOSING_ACTION_FEATURES,
    CLOSING_RAW_FEATURES,
    MODEL_FILES,
    NORMAL_FEATURES,
    OUTCOMES,
    LoadedShadowBundle,
    _require_columns,
    build_shadow_feature_records as _build_shadow_feature_records,
    load_shadow_bundle as _load_shadow_bundle,
    normalize_probabilities,
    sha256,
)


# The generic closing models were trained only at T-48, T-24, T-12 and T-6.
# These non-overlapping windows permit collection jitter without silently
# extrapolating into the unsupported late market or far-future horizon.
CLOSING_CUTOFF_WINDOWS = (
    (48, 36.0, 60.0, True),
    (24, 18.0, 36.0, False),
    (12, 9.0, 18.0, False),
    (6, 4.0, 9.0, False),
)


def load_shadow_bundle(directory: Path) -> LoadedShadowBundle:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("bundle runtime metadata missing")
    actual = {
        "python_major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }
    mismatches = {
        key: {"bundle": runtime.get(key), "runtime": value}
        for key, value in actual.items()
        if runtime.get(key) != value
    }
    if mismatches:
        raise ValueError(f"bundle runtime mismatch: {mismatches}")
    return _load_shadow_bundle(directory)


def build_shadow_feature_records(
    quote_ledger: pd.DataFrame,
    transitions: pd.DataFrame,
    *,
    strict: bool = True,
) -> tuple[pd.DataFrame, dict[str, int]]:
    records, diagnostics = _build_shadow_feature_records(
        quote_ledger,
        transitions,
        strict=strict,
    )
    hours = records["hours_to_commence_scaled_71"].to_numpy(float) * 71.0
    bucket = np.zeros(len(records), dtype=np.int16)
    for cutoff, lower, upper, include_upper in CLOSING_CUTOFF_WINDOWS:
        mask = (hours >= lower) & ((hours <= upper) if include_upper else (hours < upper))
        bucket[mask] = cutoff
    unsupported = bucket == 0
    diagnostics = dict(diagnostics)
    diagnostics["unsupported_closing_horizon_chains"] = int(unsupported.sum())
    diagnostics["supported_closing_horizon_chains"] = int((~unsupported).sum())
    if strict and unsupported.any():
        raise ValueError(f"unsupported historical closing horizon: {diagnostics}")
    records = records.loc[~unsupported].copy()
    records["supported_closing_cutoff_hours"] = bucket[~unsupported]
    records.reset_index(drop=True, inplace=True)
    if records.empty:
        raise RuntimeError("no chains in historically supported closing horizons")
    return records, diagnostics


def _predict_raw_delta(models: Mapping[str, Any], prefix: str, x: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [models[f"{prefix}_delta_{outcome}"].predict(x) for outcome in OUTCOMES]
    )


def _predict_normal_action_delta(
    models: Mapping[str, Any],
    x: np.ndarray,
    current: np.ndarray,
) -> np.ndarray:
    raw = _predict_raw_delta(models, "normal", x)
    return normalize_probabilities(current + raw) - current


def score_shadow_records(records: pd.DataFrame, bundle: LoadedShadowBundle) -> pd.DataFrame:
    _require_columns(
        records,
        [*NORMAL_FEATURES, *CLOSING_RAW_FEATURES, "supported_closing_cutoff_hours"],
        "shadow records",
    )
    normal_x = records[list(NORMAL_FEATURES)].to_numpy(float)
    current = records[["own_current_home_p", "own_current_draw_p", "own_current_away_p"]].to_numpy(float)
    normal_probability = bundle.models["normal_hazard"].predict_proba(normal_x)[:, 1]
    predicted_action_delta = _predict_normal_action_delta(bundle.models, normal_x, current)
    actual_delta = records[["actual_delta_home_p", "actual_delta_draw_p", "actual_delta_away_p"]].to_numpy(float)
    actual_move = records["actual_move"].to_numpy(int)
    conditional_residual = actual_delta - predicted_action_delta
    conditional_residual[actual_move == 0] = 0.0
    action_residual = actual_delta - normal_probability[:, None] * predicted_action_delta

    raw_x = records[list(CLOSING_RAW_FEATURES)].to_numpy(float)
    action_values = np.column_stack(
        [
            conditional_residual,
            np.linalg.norm(conditional_residual, axis=1),
            action_residual,
            np.linalg.norm(action_residual, axis=1),
        ]
    )
    if action_values.shape[1] != len(ACTION_RESIDUAL_FEATURES):
        raise RuntimeError("action residual feature-width mismatch")
    action_x = np.column_stack([raw_x, action_values])
    raw_close_probability = bundle.models["closing_raw_hazard"].predict_proba(raw_x)[:, 1]
    action_close_probability = bundle.models["closing_action_hazard"].predict_proba(action_x)[:, 1]

    # Experiments 008/011/013 ranked closing candidates using the regressors'
    # direct probability-delta predictions. Only the normal-action layer projected
    # current + delta back to the probability simplex before residual formation.
    raw_close_delta = _predict_raw_delta(bundle.models, "closing_raw", raw_x)
    action_close_delta = _predict_raw_delta(bundle.models, "closing_action", action_x)
    raw_expected = raw_close_probability[:, None] * raw_close_delta
    action_expected = action_close_probability[:, None] * action_close_delta
    raw_outcome_index = np.argmax(raw_expected, axis=1)
    action_outcome_index = np.argmax(action_expected, axis=1)
    rows = np.arange(len(records))

    output = records.copy()
    output["normal_predicted_move_probability"] = normal_probability
    for index, outcome in enumerate(OUTCOMES):
        output[f"normal_predicted_conditional_delta_{outcome}"] = predicted_action_delta[:, index]
        output[f"conditional_residual_{outcome}"] = conditional_residual[:, index]
        output[f"action_residual_{outcome}"] = action_residual[:, index]
        output[f"raw_expected_closing_delta_{outcome}"] = raw_expected[:, index]
        output[f"action_expected_closing_delta_{outcome}"] = action_expected[:, index]
    output["conditional_residual_l2"] = np.linalg.norm(conditional_residual, axis=1)
    output["action_residual_l2"] = np.linalg.norm(action_residual, axis=1)
    output["raw_candidate_outcome"] = np.asarray(OUTCOMES, dtype=object)[raw_outcome_index]
    output["raw_candidate_score"] = raw_expected[rows, raw_outcome_index]
    output["action_rank_score_for_raw_candidate"] = action_expected[rows, raw_outcome_index]
    output["action_selector_outcome"] = np.asarray(OUTCOMES, dtype=object)[action_outcome_index]
    output["action_selector_score"] = action_expected[rows, action_outcome_index]
    output["bundle_id"] = bundle.bundle_id
    output["bundle_manifest_sha256"] = bundle.manifest_sha256
    output["research_only"] = True
    output["no_execution"] = True
    output["unvalidated_prospective_transfer"] = True
    return output


def select_event_shadow_candidates(scored: pd.DataFrame) -> pd.DataFrame:
    required = [
        "event_id", "realized_snapshot_id", "bookmaker_key", "raw_candidate_outcome",
        "raw_candidate_score", "action_rank_score_for_raw_candidate",
    ]
    _require_columns(scored, required, "scored shadow rows")
    ordered = scored.sort_values(
        ["event_id", "realized_snapshot_id", "raw_candidate_score", "bookmaker_key", "raw_candidate_outcome"],
        ascending=[True, True, False, True, True],
        kind="mergesort",
    )
    selected = ordered.groupby(["event_id", "realized_snapshot_id"], sort=False, as_index=False).first()
    selected["action_rank_percentile_within_snapshot"] = selected.groupby("realized_snapshot_id")[
        "action_rank_score_for_raw_candidate"
    ].rank(method="average", pct=True)
    return selected
