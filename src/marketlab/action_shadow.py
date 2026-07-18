from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from .action_shadow_schema import (
    ACTION_RESIDUAL_FEATURES,
    CLOSING_ACTION_FEATURES,
    CLOSING_RAW_FEATURES,
    MODEL_FILES,
    NORMAL_FEATURES,
    OUTCOMES,
    LoadedShadowBundle,
    _require_columns,
    build_shadow_feature_records,
    load_shadow_bundle,
    normalize_probabilities,
    sha256,
)


def _predict_delta(models: Mapping[str, Any], prefix: str, x: np.ndarray, current: np.ndarray) -> np.ndarray:
    raw = np.column_stack([models[f"{prefix}_delta_{outcome}"].predict(x) for outcome in OUTCOMES])
    return normalize_probabilities(current + raw) - current


def score_shadow_records(records: pd.DataFrame, bundle: LoadedShadowBundle) -> pd.DataFrame:
    _require_columns(records, [*NORMAL_FEATURES, *CLOSING_RAW_FEATURES], "shadow records")
    normal_x = records[list(NORMAL_FEATURES)].to_numpy(float)
    current = records[["own_current_home_p", "own_current_draw_p", "own_current_away_p"]].to_numpy(float)
    normal_probability = bundle.models["normal_hazard"].predict_proba(normal_x)[:, 1]
    predicted_action_delta = _predict_delta(bundle.models, "normal", normal_x, current)
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
    observation = records[["observation_home_p", "observation_draw_p", "observation_away_p"]].to_numpy(float)
    raw_close_probability = bundle.models["closing_raw_hazard"].predict_proba(raw_x)[:, 1]
    action_close_probability = bundle.models["closing_action_hazard"].predict_proba(action_x)[:, 1]
    raw_close_delta = _predict_delta(bundle.models, "closing_raw", raw_x, observation)
    action_close_delta = _predict_delta(bundle.models, "closing_action", action_x, observation)
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
