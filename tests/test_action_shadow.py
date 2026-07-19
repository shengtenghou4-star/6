from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.dummy import DummyClassifier, DummyRegressor

from marketlab.action_shadow import (
    ACTION_RESIDUAL_FEATURES,
    CLOSING_ACTION_FEATURES,
    CLOSING_RAW_FEATURES,
    MODEL_FILES,
    NORMAL_FEATURES,
    LoadedShadowBundle,
    build_shadow_feature_records,
    load_shadow_bundle,
    score_shadow_records,
    select_event_shadow_candidates,
    sha256,
)


HOME = "Home FC"
AWAY = "Away FC"


def frames(post_commence: bool = False, missing_consensus: bool = False):
    books = ["b1", "b2", "b3", "b4"]
    commence = pd.Timestamp("2026-07-19T23:00:00Z")
    times = {
        "s1": pd.Timestamp("2026-07-19T10:00:00Z"),
        "s2": pd.Timestamp("2026-07-19T11:00:00Z"),
        "s3": pd.Timestamp("2026-07-20T00:00:00Z") if post_commence else pd.Timestamp("2026-07-19T12:00:00Z"),
    }
    probs = {
        "s1": np.array([0.45, 0.28, 0.27]),
        "s2": np.array([0.46, 0.275, 0.265]),
        "s3": np.array([0.48, 0.265, 0.255]),
    }
    ledger_rows = []
    transition_rows = []
    for bi, book in enumerate(books):
        offset = np.array([bi * 0.001, -bi * 0.0005, -bi * 0.0005])
        for snap in ("s1", "s2", "s3"):
            p = probs[snap] + offset
            consensus = probs[snap]
            ledger_rows.append({
                "snapshot_id": snap, "event_id": "e1", "bookmaker_key": book, "market_key": "h2h",
                "raw_sha256": snap * 32, "snapshot_ingested_at": times[snap], "commence_time": commence,
                "home_p": p[0], "draw_p": p[1], "away_p": p[2], "overround": 0.05,
                "consensus_home_p_ex_target": np.nan if missing_consensus and snap == "s1" else consensus[0],
                "consensus_draw_p_ex_target": consensus[1], "consensus_away_p_ex_target": consensus[2],
            })
        for prev, cur in (("s1", "s2"), ("s2", "s3")):
            pp = probs[prev] + offset
            cp = probs[cur] + offset
            transition_rows.append({
                "event_id": "e1", "bookmaker_key": book, "market_key": "h2h",
                "previous_snapshot_id": prev, "snapshot_id": cur,
                "previous_snapshot_ingested_at": times[prev], "snapshot_ingested_at": times[cur],
                "previous_raw_sha256": prev * 32, "raw_sha256": cur * 32, "commence_time": commence,
                "previous_home_p": pp[0], "previous_draw_p": pp[1], "previous_away_p": pp[2],
                "home_p": cp[0], "draw_p": cp[1], "away_p": cp[2],
                "previous_overround": 0.05, "overround": 0.05,
                "delta_home_p": cp[0]-pp[0], "delta_draw_p": cp[1]-pp[1], "delta_away_p": cp[2]-pp[2],
                "target_book_moved": True, "other_book_move_fraction": 1.0,
                "consensus_other_book_coverage": 3,
                "consensus_home_p_ex_target": probs[cur][0],
                "consensus_draw_p_ex_target": probs[cur][1],
                "consensus_away_p_ex_target": probs[cur][2],
                "dispersion_home_p_ex_target": 0.002,
                "dispersion_draw_p_ex_target": 0.001,
                "dispersion_away_p_ex_target": 0.001,
                "hours_to_commence": (commence-times[cur]).total_seconds()/3600,
                "provider_update_advanced": False if book == "b1" and cur == "s3" else True,
                "state_changed_without_provider_update_advance": bool(book == "b1" and cur == "s3"),
            })
    return pd.DataFrame(ledger_rows), pd.DataFrame(transition_rows)


class FixedClassifier:
    def predict_proba(self, x):
        p = np.full(len(x), 0.6)
        return np.column_stack([1-p, p])


class FixedRegressor:
    def __init__(self, value: float):
        self.value = value

    def predict(self, x):
        return np.full(len(x), self.value)


def bundle() -> LoadedShadowBundle:
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
    return LoadedShadowBundle(Path("."), {"bundle_id": "test"}, models, "a" * 64)


def test_exact_feature_order_and_three_snapshot_alignment():
    ledger, transitions = frames()
    records, diagnostics = build_shadow_feature_records(ledger, transitions)
    assert len(records) == 4
    assert diagnostics["eligible_chains"] == 4
    assert diagnostics["unsupported_closing_horizon_chains"] == 0
    assert list(records.columns[:len(NORMAL_FEATURES)]) == list(NORMAL_FEATURES)
    assert records["context_previous_snapshot_id"].eq("s1").all()
    assert records["context_snapshot_id"].eq("s2").all()
    assert records["realized_snapshot_id"].eq("s3").all()
    assert records["supported_closing_cutoff_hours"].eq(12).all()
    assert records.loc[
        records["bookmaker_key"] == "b1",
        "state_changed_without_provider_update_advance",
    ].iloc[0]


def test_scoring_preserves_raw_identity_and_research_flags():
    records, _ = build_shadow_feature_records(*frames())
    scored = score_shadow_records(records, bundle())
    assert scored["raw_candidate_outcome"].eq("home").all()
    assert scored["action_rank_score_for_raw_candidate"].gt(scored["raw_candidate_score"]).all()
    assert scored["research_only"].all() and scored["no_execution"].all()
    selected = select_event_shadow_candidates(scored)
    assert len(selected) == 1
    assert selected["action_rank_percentile_within_snapshot"].iloc[0] == 1.0


def test_post_commence_and_missing_consensus_rejected():
    with pytest.raises(ValueError, match="invalid prospective shadow chains"):
        build_shadow_feature_records(*frames(post_commence=True))
    with pytest.raises(ValueError, match="invalid prospective shadow chains"):
        build_shadow_feature_records(*frames(missing_consensus=True))


def test_bundle_tamper_and_runtime_mismatch_rejected(tmp_path: Path):
    x = np.array([[0.0], [1.0]])
    clf = DummyClassifier(strategy="prior").fit(x, [0, 1])
    reg = DummyRegressor(strategy="mean").fit(x, [0.0, 0.1])
    files = {}
    for name in MODEL_FILES:
        path = tmp_path / f"{name}.joblib"
        joblib.dump(clf if name.endswith("hazard") else reg, path)
        files[name] = {"path": path.name, "sha256": sha256(path)}
    manifest = {
        "bundle_id": "fixture",
        "runtime": {
            "python_major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "feature_order": {
            "normal_features": list(NORMAL_FEATURES),
            "closing_raw_features": list(CLOSING_RAW_FEATURES),
            "action_residual_features": list(ACTION_RESIDUAL_FEATURES),
            "closing_action_features": list(CLOSING_ACTION_FEATURES),
        },
        "model_files": files,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_shadow_bundle(tmp_path)
    assert loaded.bundle_id == "fixture"

    manifest["runtime"]["scikit_learn"] = "0.0.invalid"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="runtime mismatch"):
        load_shadow_bundle(tmp_path)

    manifest["runtime"]["scikit_learn"] = sklearn.__version__
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "normal_hazard.joblib").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_shadow_bundle(tmp_path)
