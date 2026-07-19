from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import build_generic_action_shadow_bundle as bundle_build
import experiment_008_named_book_clv as exp8
import experiment_011_closing_line_residual as exp11
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import DOWNLOAD_URL, SERIES_FILES, download, extract_required
from marketlab.action_shadow import load_shadow_bundle
from marketlab.action_shadow_schema import (
    ACTION_RESIDUAL_FEATURES,
    CLOSING_RAW_FEATURES,
    OUTCOMES,
)


RANDOM_SEED = 20260719
SCORE_COLUMNS = (
    "raw_candidate_score",
    "action_rank_score_for_raw_candidate",
    "residual_uplift",
)
DOMAIN_FEATURES = (*CLOSING_RAW_FEATURES, *ACTION_RESIDUAL_FEATURES, *SCORE_COLUMNS)


def _predict_delta(models: dict[str, Any], prefix: str, x: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [models[f"{prefix}_delta_{outcome}"].predict(x) for outcome in OUTCOMES]
    )


def build_historical_reference(
    source_paths: list[Path],
    bundle_root: Path,
    *,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    bundle = load_shadow_bundle(bundle_root)
    datasets = residual_gen.build_all_state_records(source_paths, chunksize=chunksize)
    diagnostics = datasets.pop("diagnostics")
    generic_test = bundle_build.generic_data(datasets["test"])
    residual = residual_gen.build_residual_frame(
        "test",
        generic_test,
        bundle.models["normal_hazard"],
        [bundle.models[f"normal_delta_{outcome}"] for outcome in OUTCOMES],
    )
    x_frame, raw_feature_columns = exp8.x_frame(generic_test)
    closing, closing_profile = exp11.build_closing_prices(
        source_paths,
        [residual],
        chunksize=chunksize,
    )
    frame, baseline_columns, _ = exp8.model_frame(
        residual,
        x_frame,
        closing,
        raw_feature_columns,
    )
    if len(baseline_columns) != len(CLOSING_RAW_FEATURES):
        raise RuntimeError(
            "historical closing raw feature width does not match the frozen bundle schema"
        )
    baseline_rename = dict(zip(baseline_columns, CLOSING_RAW_FEATURES, strict=True))
    action_columns = baseline_columns + list(ACTION_RESIDUAL_FEATURES)
    raw_x = frame[baseline_columns].to_numpy(float)
    action_x = frame[action_columns].to_numpy(float)
    raw_probability = bundle.models["closing_raw_hazard"].predict_proba(raw_x)[:, 1]
    action_probability = bundle.models["closing_action_hazard"].predict_proba(action_x)[:, 1]
    raw_expected = raw_probability[:, None] * _predict_delta(
        bundle.models, "closing_raw", raw_x
    )
    action_expected = action_probability[:, None] * _predict_delta(
        bundle.models, "closing_action", action_x
    )
    candidate = np.argmax(raw_expected, axis=1)
    row = np.arange(len(frame))
    output = frame[
        ["match_id", "book_slot", "hours_before_kickoff", *action_columns]
    ].copy()
    output.rename(
        columns={
            "hours_before_kickoff": "supported_closing_cutoff_hours",
            **baseline_rename,
        },
        inplace=True,
    )
    output["raw_candidate_score"] = raw_expected[row, candidate]
    output["action_rank_score_for_raw_candidate"] = action_expected[row, candidate]
    output["residual_uplift"] = (
        output["action_rank_score_for_raw_candidate"]
        - output["raw_candidate_score"]
    )
    output["domain_group"] = output["match_id"].astype(str)
    missing = sorted(set(DOMAIN_FEATURES) - set(output.columns))
    if missing:
        raise RuntimeError(f"historical reference missing frozen domain features: {missing}")
    return output, {
        "rows": int(len(output)),
        "matches": int(output["match_id"].nunique()),
        "cutoffs": {
            str(key): int(value)
            for key, value in output[
                "supported_closing_cutoff_hours"
            ].value_counts().sort_index().items()
        },
        "normal_state_diagnostics": diagnostics,
        "closing_price_profile": closing_profile,
        "bundle_id": bundle.bundle_id,
        "bundle_manifest_sha256": bundle.manifest_sha256,
        "domain_feature_count": len(DOMAIN_FEATURES),
    }


def population_stability_index(reference: np.ndarray, current: np.ndarray) -> float:
    reference = reference[np.isfinite(reference)]
    current = current[np.isfinite(current)]
    if len(reference) < 20 or len(current) < 10:
        return float("nan")
    edges = np.unique(np.quantile(reference, np.linspace(0.0, 1.0, 11)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_count, _ = np.histogram(reference, bins=edges)
    cur_count, _ = np.histogram(current, bins=edges)
    eps = 1e-6
    ref_share = np.maximum(ref_count / ref_count.sum(), eps)
    cur_share = np.maximum(cur_count / cur_count.sum(), eps)
    return float(np.sum((cur_share - ref_share) * np.log(cur_share / ref_share)))


def feature_metric(reference: np.ndarray, current: np.ndarray) -> dict[str, float | int]:
    reference = reference[np.isfinite(reference)]
    current = current[np.isfinite(current)]
    if len(reference) < 20 or len(current) < 10:
        return {
            "reference_rows": int(len(reference)),
            "prospective_rows": int(len(current)),
            "standardized_mean_difference": float("nan"),
            "psi": float("nan"),
            "out_of_support_fraction": float("nan"),
            "central_90pct_overlap": float("nan"),
        }
    pooled = np.sqrt(
        max((reference.var(ddof=1) + current.var(ddof=1)) / 2.0, 1e-18)
    )
    smd = abs(float(current.mean() - reference.mean())) / pooled
    low, high = np.quantile(reference, [0.005, 0.995])
    out_of_support = float(np.mean((current < low) | (current > high)))
    r05, r95 = np.quantile(reference, [0.05, 0.95])
    c05, c95 = np.quantile(current, [0.05, 0.95])
    intersection = max(0.0, min(r95, c95) - max(r05, c05))
    union = max(r95, c95) - min(r05, c05)
    return {
        "reference_rows": int(len(reference)),
        "prospective_rows": int(len(current)),
        "standardized_mean_difference": float(smd),
        "psi": population_stability_index(reference, current),
        "out_of_support_fraction": out_of_support,
        "central_90pct_overlap": float(intersection / union if union > 0 else 1.0),
    }


def domain_auc(
    historical: pd.DataFrame,
    prospective: pd.DataFrame,
    columns: list[str],
    *,
    repeats: int = 20,
) -> dict[str, Any]:
    rng = np.random.default_rng(RANDOM_SEED)
    historical_groups = historical["domain_group"].drop_duplicates().to_numpy()
    prospective_groups = prospective["domain_group"].drop_duplicates().to_numpy()
    aucs: list[float] = []
    for _ in range(repeats):
        h_groups = rng.permutation(historical_groups)
        p_groups = rng.permutation(prospective_groups)
        h_cut = max(1, int(len(h_groups) * 0.7))
        p_cut = max(1, int(len(p_groups) * 0.7))
        train = pd.concat(
            [
                historical[historical["domain_group"].isin(set(h_groups[:h_cut]))],
                prospective[prospective["domain_group"].isin(set(p_groups[:p_cut]))],
            ],
            ignore_index=True,
        )
        test = pd.concat(
            [
                historical[~historical["domain_group"].isin(set(h_groups[:h_cut]))],
                prospective[~prospective["domain_group"].isin(set(p_groups[:p_cut]))],
            ],
            ignore_index=True,
        )
        if train.empty or test.empty or test["domain_label"].nunique() < 2:
            continue
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=500,
                class_weight="balanced",
                random_state=RANDOM_SEED,
            ),
        )
        model.fit(train[columns], train["domain_label"])
        aucs.append(
            float(
                roc_auc_score(
                    test["domain_label"], model.predict_proba(test[columns])[:, 1]
                )
            )
        )
    if not aucs:
        raise RuntimeError("domain discriminator produced no valid grouped split")
    return {
        "repeats": int(len(aucs)),
        "mean_auc": float(np.mean(aucs)),
        "median_auc": float(np.median(aucs)),
        "q10_auc": float(np.quantile(aucs, 0.10)),
        "q90_auc": float(np.quantile(aucs, 0.90)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--prospective-scores", required=True)
    parser.add_argument("--output-root", default="artifacts/experiment-020")
    parser.add_argument("--chunksize", type=int, default=128)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    source_meta = download(DOWNLOAD_URL, archive)
    paths = extract_required(archive, root / "extracted")
    historical, historical_profile = build_historical_reference(
        [paths[name] for name in SERIES_FILES],
        Path(args.bundle_root),
        chunksize=args.chunksize,
    )
    prospective = pd.read_csv(args.prospective_scores, low_memory=False)
    prospective["domain_group"] = prospective["event_id"].astype(str)
    prospective["residual_uplift"] = (
        prospective["action_rank_score_for_raw_candidate"]
        - prospective["raw_candidate_score"]
    )
    missing = sorted(set(DOMAIN_FEATURES) - set(prospective.columns))
    if missing:
        raise ValueError(f"prospective scores missing frozen domain features: {missing}")
    for column in DOMAIN_FEATURES:
        historical[column] = pd.to_numeric(historical[column], errors="coerce")
        prospective[column] = pd.to_numeric(prospective[column], errors="coerce")

    common_features = list(DOMAIN_FEATURES)
    rows: list[dict[str, Any]] = []
    cutoffs = sorted(
        set(historical["supported_closing_cutoff_hours"].astype(int))
        & set(prospective["supported_closing_cutoff_hours"].astype(int))
    )
    for cutoff in [None, *cutoffs]:
        h = (
            historical
            if cutoff is None
            else historical[
                historical["supported_closing_cutoff_hours"] == cutoff
            ]
        )
        p = (
            prospective
            if cutoff is None
            else prospective[
                prospective["supported_closing_cutoff_hours"] == cutoff
            ]
        )
        for column in common_features:
            rows.append(
                {
                    "cutoff": "all" if cutoff is None else int(cutoff),
                    "feature": column,
                    **feature_metric(
                        h[column].to_numpy(float), p[column].to_numpy(float)
                    ),
                }
            )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(root / "feature-shift-metrics.csv", index=False)

    discriminator_columns = [
        column
        for column in common_features
        if historical[column].notna().all() and prospective[column].notna().all()
    ]
    if len(discriminator_columns) != len(common_features):
        missing_finite = sorted(set(common_features) - set(discriminator_columns))
        raise ValueError(f"non-finite frozen domain features: {missing_finite}")
    h_disc = historical[[*discriminator_columns, "domain_group"]].copy()
    p_disc = prospective[[*discriminator_columns, "domain_group"]].copy()
    h_disc["domain_label"] = 0
    p_disc["domain_label"] = 1
    max_historical = min(len(h_disc), max(len(p_disc) * 5, 2000))
    if len(h_disc) > max_historical:
        h_disc = h_disc.sample(max_historical, random_state=RANDOM_SEED)
    discriminator = domain_auc(h_disc, p_disc, discriminator_columns)

    overall = metrics[metrics["cutoff"].astype(str) == "all"].copy()
    severe = (
        (overall["standardized_mean_difference"] >= 1.0)
        | (overall["psi"] >= 0.25)
        | (overall["out_of_support_fraction"] >= 0.10)
    )
    warning = (
        (overall["standardized_mean_difference"] >= 0.5)
        | (overall["psi"] >= 0.10)
        | (overall["out_of_support_fraction"] >= 0.05)
    )
    prospective_events = int(prospective["event_id"].nunique())
    if len(prospective) < 300 or prospective_events < 20:
        risk = "insufficient_interim_volume"
    elif discriminator["median_auc"] >= 0.85 or severe.mean() >= 0.25:
        risk = "high_transfer_risk"
    elif discriminator["median_auc"] >= 0.70 or warning.mean() >= 0.25:
        risk = "moderate_transfer_risk"
    else:
        risk = "low_detected_transfer_risk"

    report = {
        "status": "completed",
        "experiment": "020_historical_to_prospective_domain_shift",
        "transfer_risk_status": risk,
        "evidence_boundary": {
            "match_outcomes_used": False,
            "closing_targets_used": False,
            "policy_changed": False,
            "interim_diagnostic_only": True,
        },
        "historical": historical_profile,
        "prospective": {
            "rows": int(len(prospective)),
            "events": prospective_events,
            "snapshots": int(prospective["realized_snapshot_id"].nunique()),
            "bookmakers": int(prospective["bookmaker_key"].nunique()),
            "cutoffs": {
                str(key): int(value)
                for key, value in prospective[
                    "supported_closing_cutoff_hours"
                ].value_counts().sort_index().items()
            },
        },
        "source_archive": source_meta,
        "features_compared": int(len(common_features)),
        "feature_schema": common_features,
        "domain_discriminator": discriminator,
        "overall_feature_summary": {
            "severe_features": int(severe.sum()),
            "warning_features": int(warning.sum()),
            "feature_count": int(len(overall)),
            "median_absolute_smd": float(
                overall["standardized_mean_difference"].median()
            ),
            "median_psi": float(overall["psi"].median()),
            "median_out_of_support_fraction": float(
                overall["out_of_support_fraction"].median()
            ),
            "median_central_90pct_overlap": float(
                overall["central_90pct_overlap"].median()
            ),
        },
        "frozen_thresholds": {
            "high_risk_discriminator_auc": 0.85,
            "moderate_risk_discriminator_auc": 0.70,
            "severe_feature_smd": 1.0,
            "warning_feature_smd": 0.5,
            "severe_psi": 0.25,
            "warning_psi": 0.10,
            "severe_out_of_support_fraction": 0.10,
            "warning_out_of_support_fraction": 0.05,
        },
    }
    (root / "result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
