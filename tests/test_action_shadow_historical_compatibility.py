from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marketlab.action_shadow import (
    CLOSING_RAW_FEATURES,
    NORMAL_FEATURES,
    LoadedShadowBundle,
    score_shadow_records,
)


class FixedClassifier:
    def predict_proba(self, x):
        p = np.full(len(x), 0.6)
        return np.column_stack([1.0 - p, p])


class FixedRegressor:
    def __init__(self, value: float):
        self.value = value

    def predict(self, x):
        return np.full(len(x), self.value)


def test_closing_regressor_deltas_are_not_simplex_reprojected():
    row = {column: 0.0 for column in CLOSING_RAW_FEATURES}
    row.update(
        {
            "own_current_home_p": 0.45,
            "own_current_draw_p": 0.28,
            "own_current_away_p": 0.27,
            "own_prior_home_p": 0.45,
            "own_prior_draw_p": 0.28,
            "own_prior_away_p": 0.27,
            "observation_home_p": 0.48,
            "observation_draw_p": 0.265,
            "observation_away_p": 0.255,
            "actual_move": 1,
            "event_id": "event",
            "bookmaker_key": "book",
            "market_key": "h2h",
            "realized_snapshot_id": "snapshot",
        }
    )
    records = pd.DataFrame([row])
    models = {
        "normal_hazard": FixedClassifier(),
        "normal_delta_home": FixedRegressor(0.01),
        "normal_delta_draw": FixedRegressor(-0.005),
        "normal_delta_away": FixedRegressor(-0.005),
        "closing_raw_hazard": FixedClassifier(),
        "closing_raw_delta_home": FixedRegressor(0.02),
        "closing_raw_delta_draw": FixedRegressor(-0.01),
        "closing_raw_delta_away": FixedRegressor(-0.01),
        "closing_action_hazard": FixedClassifier(),
        "closing_action_delta_home": FixedRegressor(0.03),
        "closing_action_delta_draw": FixedRegressor(-0.015),
        "closing_action_delta_away": FixedRegressor(-0.015),
    }
    bundle = LoadedShadowBundle(Path("."), {"bundle_id": "compatibility"}, models, "a" * 64)
    scored = score_shadow_records(records, bundle)

    # Experiments 008/011/013 used probability(move) × the direct closing
    # regressor delta. Reprojecting observation + delta would change both values.
    assert scored["raw_candidate_score"].iloc[0] == pytest.approx(0.6 * 0.02)
    assert scored["action_rank_score_for_raw_candidate"].iloc[0] == pytest.approx(0.6 * 0.03)
    assert scored["raw_candidate_outcome"].iloc[0] == "home"
