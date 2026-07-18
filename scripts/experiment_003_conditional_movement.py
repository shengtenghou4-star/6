from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from experiment_002_move_hazard import (
    BOOKMAKER_NAMES,
    BOOKS,
    CUTOFFS,
    DOWNLOAD_URL,
    RANDOM_SEED,
    SELECTED_BOOKS,
    SERIES_FILES,
    consensus_excluding_target,
    download,
    extract_required,
    other_move_fraction,
    raw_and_devig,
    split_names,
    state_columns,
)


def build_records(paths: list[Path], *, chunksize: int) -> dict[str, dict[str, Any]]:
    all_indices = {idx for current in CUTOFFS.values() for idx in (current - 1, current, current + 1)}
    usecols = ["match_id", "match_date"] + [
        f"{outcome}_b{book}_{idx}"
        for book in BOOKS
        for outcome in ("home", "draw", "away")
        for idx in sorted(all_indices)
    ]
    buffers: dict[str, dict[str, list[np.ndarray]]] = {
        split: {
            "X": [], "y": [], "current": [], "consensus_gap": [],
            "match_id": [], "book": [], "hours": [],
        }
        for split in ("train", "validation", "test")
    }
    candidate_states = 0
    mover_states = 0

    for path in paths:
        for frame in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
            dates = pd.to_datetime(frame["match_date"], errors="coerce")
            if dates.isna().any():
                raise ValueError(f"unparsed match dates in {path.name}")
            splits = split_names(dates)
            match_ids = frame["match_id"].astype(str).to_numpy()
            cache = {idx: raw_and_devig(frame, BOOKS, idx) for idx in sorted(all_indices)}

            for hours, current_idx in CUTOFFS.items():
                prior_idx, next_idx = current_idx - 1, current_idx + 1
                raw_prior, p_prior, over_prior, complete_prior = cache[prior_idx]
                raw_current, p_current, over_current, complete_current = cache[current_idx]
                raw_next, p_next, _, complete_next = cache[next_idx]

                for book_position, book in enumerate(SELECTED_BOOKS):
                    axis = book - 1
                    own_valid = complete_prior[:, axis] & complete_current[:, axis] & complete_next[:, axis]
                    consensus_current, dispersion_current, active_current = consensus_excluding_target(p_current, complete_current, axis)
                    consensus_prior, _, active_prior = consensus_excluding_target(p_prior, complete_prior, axis)
                    other_fraction, other_valid = other_move_fraction(raw_prior, raw_current, complete_prior, complete_current, axis)
                    market_valid = (active_current >= 3) & (active_prior >= 3) & (other_valid >= 3) & np.isfinite(other_fraction)
                    moved_next = np.any(np.abs(raw_next[:, axis, :] - raw_current[:, axis, :]) > 1e-12, axis=1)
                    eligible = own_valid & market_valid & moved_next
                    candidate_states += len(frame)
                    mover_states += int(eligible.sum())
                    if not eligible.any():
                        continue

                    own_current = p_current[:, axis, :]
                    own_prior = p_prior[:, axis, :]
                    own_next = p_next[:, axis, :]
                    own_delta_prior = own_current - own_prior
                    over_cur = over_current[:, axis][:, None]
                    over_prev = over_prior[:, axis][:, None]
                    over_delta = over_cur - over_prev
                    consensus_delta = consensus_current - consensus_prior
                    consensus_gap = consensus_current - own_current
                    deviation_current = own_current - consensus_current
                    active_scaled = active_current.astype(np.float64)[:, None] / 31.0
                    other_fraction_col = other_fraction[:, None]
                    hours_scaled = np.full((len(frame), 1), hours / 71.0, dtype=np.float64)
                    book_onehot = np.zeros((len(frame), len(SELECTED_BOOKS)), dtype=np.float64)
                    book_onehot[:, book_position] = 1.0

                    X = np.concatenate(
                        [
                            own_current, own_prior, own_delta_prior,
                            over_cur, over_prev, over_delta,
                            consensus_current, consensus_prior, consensus_delta,
                            deviation_current, dispersion_current,
                            active_scaled, other_fraction_col, hours_scaled, book_onehot,
                        ],
                        axis=1,
                    )
                    y = own_next - own_current

                    for split in ("train", "validation", "test"):
                        mask = eligible & (splits == split)
                        if not mask.any():
                            continue
                        buf = buffers[split]
                        buf["X"].append(X[mask].astype(np.float32, copy=False))
                        buf["y"].append(y[mask].astype(np.float32, copy=False))
                        buf["current"].append(own_current[mask].astype(np.float32, copy=False))
                        buf["consensus_gap"].append(consensus_gap[mask].astype(np.float32, copy=False))
                        buf["match_id"].append(match_ids[mask])
                        buf["book"].append(np.full(int(mask.sum()), book, dtype=np.int16))
                        buf["hours"].append(np.full(int(mask.sum()), hours, dtype=np.int16))

    result: dict[str, dict[str, Any]] = {}
    for split, buf in buffers.items():
        if not buf["X"]:
            raise RuntimeError(f"no eligible mover states for split {split}")
        result[split] = {key: np.concatenate(value) for key, value in buf.items()}
    result["diagnostics"] = {"candidate_states": candidate_states, "eligible_mover_states": mover_states}
    return result


def fit_baselines(train: dict[str, Any]) -> tuple[dict[tuple[int, int], np.ndarray], dict[tuple[int, int], float]]:
    means: dict[tuple[int, int], np.ndarray] = {}
    alphas: dict[tuple[int, int], float] = {}
    for book in SELECTED_BOOKS:
        for hours in CUTOFFS:
            mask = (train["book"] == book) & (train["hours"] == hours)
            if not mask.any():
                raise RuntimeError(f"no train mover states for b{book} T-{hours}h")
            y = train["y"][mask].astype(np.float64)
            gap = train["consensus_gap"][mask].astype(np.float64)
            means[(book, hours)] = y.mean(axis=0)
            denominator = float(np.sum(gap * gap))
            alpha = float(np.sum(gap * y) / denominator) if denominator > 0 else 0.0
            alphas[(book, hours)] = float(np.clip(alpha, -2.0, 2.0))
    return means, alphas


def normalize_probabilities(raw: np.ndarray) -> np.ndarray:
    clipped = np.clip(raw, 1e-6, 1.0)
    return clipped / clipped.sum(axis=1, keepdims=True)


def baseline_predictions(
    data: dict[str, Any],
    means: dict[tuple[int, int], np.ndarray],
    alphas: dict[tuple[int, int], float],
) -> tuple[np.ndarray, np.ndarray]:
    mean_delta = np.vstack([means[(int(book), int(hours))] for book, hours in zip(data["book"], data["hours"], strict=True)])
    alpha = np.array([alphas[(int(book), int(hours))] for book, hours in zip(data["book"], data["hours"], strict=True)])[:, None]
    consensus_delta = alpha * data["consensus_gap"]
    return normalize_probabilities(data["current"] + mean_delta), normalize_probabilities(data["current"] + consensus_delta)


def error_vectors(pred: np.ndarray, truth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return np.abs(pred - truth).mean(axis=1), ((pred - truth) ** 2).mean(axis=1)


def cosine_similarity(pred_delta: np.ndarray, actual_delta: np.ndarray) -> np.ndarray:
    numerator = np.sum(pred_delta * actual_delta, axis=1)
    denom = np.linalg.norm(pred_delta, axis=1) * np.linalg.norm(actual_delta, axis=1)
    return np.divide(numerator, denom, out=np.zeros_like(numerator), where=denom > 1e-15)


def dominant_direction(delta: np.ndarray) -> np.ndarray:
    axis = np.argmax(np.abs(delta), axis=1)
    sign = (delta[np.arange(len(delta)), axis] >= 0).astype(np.int8)
    return axis * 2 + sign


def summarize(data: dict[str, Any], pred: np.ndarray, baseline: np.ndarray) -> dict[str, Any]:
    truth = normalize_probabilities(data["current"] + data["y"])
    pred = normalize_probabilities(pred)
    baseline = normalize_probabilities(baseline)
    base_abs, base_sq = error_vectors(baseline, truth)
    model_abs, model_sq = error_vectors(pred, truth)
    actual_delta = truth - data["current"]
    pred_delta = pred - data["current"]
    cosine = cosine_similarity(pred_delta, actual_delta)
    direction_accuracy = float((dominant_direction(pred_delta) == dominant_direction(actual_delta)).mean())

    by_book: dict[str, Any] = {}
    for book in SELECTED_BOOKS:
        mask = data["book"] == book
        if mask.any():
            by_book[f"b{book}"] = {
                "source_name": BOOKMAKER_NAMES[book],
                "states": int(mask.sum()),
                "baseline_mae": float(base_abs[mask].mean()),
                "model_mae": float(model_abs[mask].mean()),
                "mae_improvement": float(base_abs[mask].mean() - model_abs[mask].mean()),
            }
    by_cutoff: dict[str, Any] = {}
    for hours in CUTOFFS:
        mask = data["hours"] == hours
        if mask.any():
            by_cutoff[f"T-{hours}h"] = {
                "states": int(mask.sum()),
                "baseline_mae": float(base_abs[mask].mean()),
                "model_mae": float(model_abs[mask].mean()),
                "mae_improvement": float(base_abs[mask].mean() - model_abs[mask].mean()),
            }
    return {
        "states": int(len(truth)),
        "baseline_mae": float(base_abs.mean()),
        "model_mae": float(model_abs.mean()),
        "mae_improvement": float(base_abs.mean() - model_abs.mean()),
        "relative_mae_improvement": float((base_abs.mean() - model_abs.mean()) / base_abs.mean()),
        "baseline_rmse": float(np.sqrt(base_sq.mean())),
        "model_rmse": float(np.sqrt(model_sq.mean())),
        "mean_cosine_similarity": float(cosine.mean()),
        "dominant_direction_accuracy": direction_accuracy,
        "by_book": by_book,
        "by_cutoff": by_cutoff,
        "_per_state_improvement": base_abs - model_abs,
    }


def bootstrap_match(data: dict[str, Any], improvement: np.ndarray, replicates: int = 500) -> dict[str, Any]:
    frame = pd.DataFrame({"match_id": data["match_id"], "improvement": improvement})
    values = frame.groupby("match_id", sort=False)["improvement"].mean().to_numpy(dtype=np.float64)
    rng = np.random.default_rng(RANDOM_SEED)
    draws = np.empty(replicates, dtype=np.float64)
    for i in range(replicates):
        idx = rng.integers(0, len(values), size=len(values))
        draws[i] = values[idx].mean()
    low, high = np.quantile(draws, [0.025, 0.975])
    return {"matches": int(len(values)), "mean_improvement": float(values.mean()), "ci95_low": float(low), "ci95_high": float(high), "replicates": replicates}


def clean(summary: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in summary.items() if not k.startswith("_")}


def promotion(test: dict[str, Any]) -> dict[str, Any]:
    books = sum(1 for item in test["by_book"].values() if item["mae_improvement"] > 0)
    cutoffs = sum(1 for item in test["by_cutoff"].values() if item["mae_improvement"] > 0)
    checks = {
        "overall_mae_better": test["mae_improvement"] > 0,
        "bootstrap_ci_above_zero": test["match_bootstrap"]["ci95_low"] > 0,
        "improved_at_least_5_of_8_books": books >= 5,
        "improved_at_least_4_of_6_cutoffs": cutoffs >= 4,
    }
    return {"promoted": all(checks.values()), "checks": checks, "improved_books": books, "improved_cutoffs": cutoffs}


def score_model(name: str, predictor: Any, datasets: dict[str, dict[str, Any]], means: dict[tuple[int, int], np.ndarray], alphas: dict[tuple[int, int], float]) -> dict[str, Any]:
    result: dict[str, Any] = {"model": name, "splits": {}}
    for split in ("validation", "test"):
        data = datasets[split]
        pred = normalize_probabilities(data["current"] + predictor(data["X"]))
        mean_base, consensus_base = baseline_predictions(data, means, alphas)
        scored = summarize(data, pred, consensus_base)
        mean_scored = summarize(data, pred, mean_base)
        boot = bootstrap_match(data, scored["_per_state_improvement"])
        result["splits"][split] = {
            **clean(scored),
            "conditional_mean_baseline_mae": mean_scored["baseline_mae"],
            "improvement_vs_conditional_mean": mean_scored["mae_improvement"],
            "match_bootstrap": boot,
        }
    result["promotion"] = promotion(result["splits"]["test"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Experiment 003 conditional bookmaker movement model.")
    parser.add_argument("--output-root", default="artifacts/experiment-003")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--nonlinear-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    archive_meta = download(DOWNLOAD_URL, archive)
    paths = extract_required(archive, extracted)
    datasets = build_records([paths[name] for name in SERIES_FILES], chunksize=args.chunksize)
    diagnostics = datasets.pop("diagnostics")
    means, alphas = fit_baselines(datasets["train"])

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    ridge.fit(datasets["train"]["X"], datasets["train"]["y"])
    ridge_result = score_model("ridge_alpha_10", ridge.predict, datasets, means, alphas)

    train_x, train_y = datasets["train"]["X"], datasets["train"]["y"]
    rng = np.random.default_rng(RANDOM_SEED)
    if len(train_x) > args.nonlinear_max_train:
        idx = np.sort(rng.choice(len(train_x), size=args.nonlinear_max_train, replace=False))
        hgb_x, hgb_y = train_x[idx], train_y[idx]
    else:
        hgb_x, hgb_y = train_x, train_y
    models = []
    for outcome_idx in range(3):
        model = HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.08, max_leaf_nodes=31,
            l2_regularization=1.0, random_state=RANDOM_SEED,
        )
        model.fit(hgb_x, hgb_y[:, outcome_idx])
        models.append(model)

    def hgb_predict(x: np.ndarray) -> np.ndarray:
        return np.column_stack([model.predict(x) for model in models])

    hgb_result = score_model("hist_gradient_boosting_fixed", hgb_predict, datasets, means, alphas)
    hgb_result["training_states_used"] = int(len(hgb_x))

    baseline_parameters = {
        f"b{book}_T-{hours}h": {
            "conditional_mean_delta": [float(x) for x in means[(book, hours)]],
            "consensus_response_alpha": float(alphas[(book, hours)]),
        }
        for book in SELECTED_BOOKS for hours in CUTOFFS
    }
    report = {
        "experiment": "003_conditional_bookmaker_movement",
        "status": "executed",
        "archive": archive_meta,
        "eligible_mover_state_counts": {split: int(len(data["X"])) for split, data in datasets.items()},
        "diagnostics": diagnostics,
        "baseline_parameters": baseline_parameters,
        "models": [ridge_result, hgb_result],
        "any_model_promoted": bool(ridge_result["promotion"]["promoted"] or hgb_result["promotion"]["promoted"]),
    }
    (root / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "eligible_mover_state_counts": report["eligible_mover_state_counts"],
        "ridge_test": ridge_result["splits"]["test"],
        "ridge_promotion": ridge_result["promotion"],
        "hgb_test": hgb_result["splits"]["test"],
        "hgb_promotion": hgb_result["promotion"],
        "any_model_promoted": report["any_model_promoted"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
