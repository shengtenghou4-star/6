from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


DATASET_SLUG = "austro/beat-the-bookie-worldwide-football-dataset"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
SERIES_FILES = ("odds_series.csv.gz", "odds_series_b.csv.gz")
OUTCOMES = ("home", "draw", "away")
BOOKS = tuple(range(1, 33))
SELECTED_BOOKS = (30, 3, 9, 7, 26, 16, 6, 23)
CUTOFFS = {48: 23, 24: 47, 12: 59, 6: 65, 3: 68, 1: 70}
RANDOM_SEED = 20260718
BOOKMAKER_NAMES = {
    30: "ComeOn", 3: "bet-at-home", 9: "bet365", 7: "10Bet",
    26: "BetVictor", 16: "Betclic", 6: "Expekt", 23: "Tipico",
}


def download(url: str, path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256()
    total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
                fh.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "final_url": str(response.url)}


def extract_required(archive: Path, destination: Path) -> dict[str, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        for name in SERIES_FILES:
            if name not in names:
                raise ValueError(f"archive missing required file: {name}")
            target = destination / name
            with zf.open(name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            result[name] = target
    return result


def state_columns(books: tuple[int, ...] | list[int], index: int) -> list[str]:
    return [f"{outcome}_b{book}_{index}" for book in books for outcome in OUTCOMES]


def split_names(dates: pd.Series) -> np.ndarray:
    values = dates.to_numpy(dtype="datetime64[D]")
    output = np.full(len(values), "test", dtype=object)
    output[values <= np.datetime64("2016-06-30")] = "train"
    output[(values > np.datetime64("2016-06-30")) & (values <= np.datetime64("2016-08-31"))] = "validation"
    return output


def raw_and_devig(frame: pd.DataFrame, books: tuple[int, ...] | list[int], index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    raw = frame[state_columns(books, index)].to_numpy(dtype=np.float64, copy=False).reshape(len(frame), len(books), 3)
    valid = np.isfinite(raw) & (raw > 1.0)
    complete = valid.all(axis=2)
    implied = np.divide(1.0, raw, out=np.full_like(raw, np.nan), where=valid)
    sums = np.nansum(implied, axis=2)
    probs = np.divide(implied, sums[:, :, None], out=np.full_like(implied, np.nan), where=complete[:, :, None] & (sums[:, :, None] > 0))
    probs[~complete] = np.nan
    overround = sums - 1.0
    overround[~complete] = np.nan
    return raw, probs, overround, complete


def consensus_excluding_target(
    probs: np.ndarray,
    complete: np.ndarray,
    target_axis: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    masked = np.where(complete[:, :, None], probs, np.nan)
    sums = np.nansum(masked, axis=1)
    sumsq = np.nansum(masked * masked, axis=1)
    counts = complete.sum(axis=1).astype(np.int64)
    target_valid = complete[:, target_axis]
    target_probs = probs[:, target_axis, :]
    counts_ex = counts - target_valid.astype(np.int64)
    sums_ex = sums - np.where(target_valid[:, None], target_probs, 0.0)
    sumsq_ex = sumsq - np.where(target_valid[:, None], target_probs * target_probs, 0.0)
    ok = counts_ex >= 3
    mean = np.divide(sums_ex, counts_ex[:, None], out=np.full_like(sums_ex, np.nan), where=ok[:, None])
    variance = np.divide(sumsq_ex, counts_ex[:, None], out=np.full_like(sumsq_ex, np.nan), where=ok[:, None]) - mean * mean
    dispersion = np.sqrt(np.maximum(variance, 0.0))
    return mean, dispersion, counts_ex


def other_move_fraction(
    raw_prior: np.ndarray,
    raw_current: np.ndarray,
    complete_prior: np.ndarray,
    complete_current: np.ndarray,
    target_axis: int,
) -> tuple[np.ndarray, np.ndarray]:
    jointly_valid = complete_prior & complete_current
    moved = jointly_valid & np.any(np.abs(raw_current - raw_prior) > 1e-12, axis=2)
    other_valid = jointly_valid.sum(axis=1) - jointly_valid[:, target_axis].astype(np.int64)
    other_moved = moved.sum(axis=1) - moved[:, target_axis].astype(np.int64)
    fraction = np.divide(
        other_moved.astype(np.float64),
        other_valid.astype(np.float64),
        out=np.full(len(raw_prior), np.nan, dtype=np.float64),
        where=other_valid >= 3,
    )
    return fraction, other_valid


def build_records(paths: list[Path], *, chunksize: int) -> dict[str, dict[str, Any]]:
    all_indices = {idx for current in CUTOFFS.values() for idx in (current - 1, current, current + 1)}
    usecols = ["match_id", "match_date"] + [
        f"{outcome}_b{book}_{idx}"
        for book in BOOKS
        for outcome in OUTCOMES
        for idx in sorted(all_indices)
    ]
    buffers: dict[str, dict[str, list[np.ndarray]]] = {
        split: {"X": [], "y": [], "match_id": [], "book": [], "hours": []}
        for split in ("train", "validation", "test")
    }
    diagnostics = Counter()

    for path in paths:
        for frame in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
            dates = pd.to_datetime(frame["match_date"], errors="coerce")
            if dates.isna().any():
                raise ValueError(f"unparsed match dates in {path.name}")
            splits = split_names(dates)
            match_ids = frame["match_id"].astype(str).to_numpy()
            cache: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {
                idx: raw_and_devig(frame, BOOKS, idx) for idx in sorted(all_indices)
            }

            for hours, current_idx in CUTOFFS.items():
                prior_idx, next_idx = current_idx - 1, current_idx + 1
                raw_prior, p_prior, over_prior, complete_prior = cache[prior_idx]
                raw_current, p_current, over_current, complete_current = cache[current_idx]
                raw_next, _, _, complete_next = cache[next_idx]

                for book_position, book in enumerate(SELECTED_BOOKS):
                    axis = book - 1
                    own_valid = complete_prior[:, axis] & complete_current[:, axis] & complete_next[:, axis]
                    consensus_current, dispersion_current, active_current = consensus_excluding_target(p_current, complete_current, axis)
                    consensus_prior, _, active_prior = consensus_excluding_target(p_prior, complete_prior, axis)
                    other_fraction, other_valid = other_move_fraction(raw_prior, raw_current, complete_prior, complete_current, axis)
                    market_valid = (active_current >= 3) & (active_prior >= 3) & (other_valid >= 3) & np.isfinite(other_fraction)
                    eligible = own_valid & market_valid
                    diagnostics["candidate_states"] += len(frame)
                    diagnostics["eligible_states"] += int(eligible.sum())
                    if not eligible.any():
                        continue

                    own_current = p_current[:, axis, :]
                    own_prior = p_prior[:, axis, :]
                    own_delta = own_current - own_prior
                    over_cur = over_current[:, axis][:, None]
                    over_prev = over_prior[:, axis][:, None]
                    over_delta = over_cur - over_prev
                    consensus_delta = consensus_current - consensus_prior
                    deviation_current = own_current - consensus_current
                    active_scaled = active_current.astype(np.float64)[:, None] / 31.0
                    other_fraction_col = other_fraction[:, None]
                    hours_scaled = np.full((len(frame), 1), hours / 71.0, dtype=np.float64)
                    book_onehot = np.zeros((len(frame), len(SELECTED_BOOKS)), dtype=np.float64)
                    book_onehot[:, book_position] = 1.0

                    X = np.concatenate(
                        [
                            own_current, own_prior, own_delta,
                            over_cur, over_prev, over_delta,
                            consensus_current, consensus_prior, consensus_delta,
                            deviation_current, dispersion_current,
                            active_scaled, other_fraction_col, hours_scaled, book_onehot,
                        ],
                        axis=1,
                    )
                    y = np.any(np.abs(raw_next[:, axis, :] - raw_current[:, axis, :]) > 1e-12, axis=1).astype(np.int8)

                    for split in ("train", "validation", "test"):
                        mask = eligible & (splits == split)
                        if not mask.any():
                            continue
                        buf = buffers[split]
                        buf["X"].append(X[mask].astype(np.float32, copy=False))
                        buf["y"].append(y[mask])
                        buf["match_id"].append(match_ids[mask])
                        buf["book"].append(np.full(int(mask.sum()), book, dtype=np.int16))
                        buf["hours"].append(np.full(int(mask.sum()), hours, dtype=np.int16))

    result: dict[str, dict[str, Any]] = {}
    for split, buf in buffers.items():
        if not buf["X"]:
            raise RuntimeError(f"no eligible records for {split}")
        result[split] = {
            "X": np.concatenate(buf["X"]),
            "y": np.concatenate(buf["y"]),
            "match_id": np.concatenate(buf["match_id"]),
            "book": np.concatenate(buf["book"]),
            "hours": np.concatenate(buf["hours"]),
        }
    result["diagnostics"] = dict(diagnostics)
    return result


def baseline_rates(train: dict[str, Any]) -> dict[tuple[int, int], float]:
    rates: dict[tuple[int, int], float] = {}
    for book in SELECTED_BOOKS:
        for hours in CUTOFFS:
            mask = (train["book"] == book) & (train["hours"] == hours)
            n = int(mask.sum())
            if n == 0:
                raise RuntimeError(f"no training baseline states for b{book} T-{hours}h")
            moves = int(train["y"][mask].sum())
            rates[(book, hours)] = (moves + 1.0) / (n + 2.0)
    return rates


def baseline_predictions(data: dict[str, Any], rates: dict[tuple[int, int], float]) -> np.ndarray:
    return np.array([rates[(int(book), int(hours))] for book, hours in zip(data["book"], data["hours"], strict=True)], dtype=np.float64)


def calibration(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict[str, Any]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    ids = np.minimum(np.digitize(p, edges[1:-1], right=False), bins - 1)
    output = []
    for bin_id in range(bins):
        mask = ids == bin_id
        if not mask.any():
            continue
        output.append({
            "bin": bin_id,
            "states": int(mask.sum()),
            "mean_predicted": float(p[mask].mean()),
            "observed_move_rate": float(y[mask].mean()),
        })
    return output


def metric_summary(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    clipped = np.clip(p, 1e-8, 1 - 1e-8)
    return {
        "brier": float(brier_score_loss(y, clipped)),
        "log_loss": float(log_loss(y, clipped, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, clipped)) if len(np.unique(y)) == 2 else float("nan"),
        "move_prevalence": float(y.mean()),
        "mean_predicted": float(clipped.mean()),
    }


def evaluate(data: dict[str, Any], model_p: np.ndarray, baseline_p: np.ndarray) -> dict[str, Any]:
    y = data["y"].astype(np.int8)
    base = metric_summary(y, baseline_p)
    model = metric_summary(y, model_p)
    by_book: dict[str, Any] = {}
    for book in SELECTED_BOOKS:
        mask = data["book"] == book
        if not mask.any():
            continue
        b = metric_summary(y[mask], baseline_p[mask])
        m = metric_summary(y[mask], model_p[mask])
        by_book[f"b{book}"] = {
            "source_name": BOOKMAKER_NAMES[book],
            "states": int(mask.sum()),
            "baseline_brier": b["brier"],
            "model_brier": m["brier"],
            "brier_improvement": b["brier"] - m["brier"],
            "model_auc": m["roc_auc"],
        }
    by_cutoff: dict[str, Any] = {}
    for hours in CUTOFFS:
        mask = data["hours"] == hours
        if not mask.any():
            continue
        b = metric_summary(y[mask], baseline_p[mask])
        m = metric_summary(y[mask], model_p[mask])
        by_cutoff[f"T-{hours}h"] = {
            "states": int(mask.sum()),
            "baseline_brier": b["brier"],
            "model_brier": m["brier"],
            "brier_improvement": b["brier"] - m["brier"],
            "model_auc": m["roc_auc"],
        }
    per_state_improvement = (y - baseline_p) ** 2 - (y - model_p) ** 2
    return {
        "states": int(len(y)),
        "baseline": base,
        "model": model,
        "brier_improvement": base["brier"] - model["brier"],
        "relative_brier_improvement": (base["brier"] - model["brier"]) / base["brier"],
        "by_book": by_book,
        "by_cutoff": by_cutoff,
        "calibration": calibration(y, model_p),
        "_per_state_improvement": per_state_improvement,
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


def clean_eval(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def promotion(test: dict[str, Any]) -> dict[str, Any]:
    improved_books = sum(1 for item in test["by_book"].values() if item["brier_improvement"] > 0)
    improved_cutoffs = sum(1 for item in test["by_cutoff"].values() if item["brier_improvement"] > 0)
    checks = {
        "overall_brier_better": test["brier_improvement"] > 0,
        "bootstrap_ci_above_zero": test["match_bootstrap"]["ci95_low"] > 0,
        "improved_at_least_5_of_8_books": improved_books >= 5,
        "improved_at_least_4_of_6_cutoffs": improved_cutoffs >= 4,
    }
    return {"promoted": all(checks.values()), "checks": checks, "improved_books": improved_books, "improved_cutoffs": improved_cutoffs}


def score_model(name: str, predictor: Any, datasets: dict[str, dict[str, Any]], rates: dict[tuple[int, int], float]) -> dict[str, Any]:
    result: dict[str, Any] = {"model": name, "splits": {}}
    for split in ("validation", "test"):
        data = datasets[split]
        model_p = np.asarray(predictor(data["X"]), dtype=np.float64)
        baseline_p = baseline_predictions(data, rates)
        scored = evaluate(data, model_p, baseline_p)
        boot = bootstrap_match(data, scored["_per_state_improvement"])
        result["splits"][split] = {**clean_eval(scored), "match_bootstrap": boot}
    result["promotion"] = promotion(result["splits"]["test"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Experiment 002 bookmaker move/no-move hazard model.")
    parser.add_argument("--output-root", default="artifacts/experiment-002")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--nonlinear-max-train", type=int, default=500000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    archive_meta = download(DOWNLOAD_URL, archive)
    paths = extract_required(archive, extracted)
    datasets = build_records([paths[name] for name in SERIES_FILES], chunksize=args.chunksize)
    diagnostics = datasets.pop("diagnostics")
    rates = baseline_rates(datasets["train"])

    logistic = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=250, solver="lbfgs"))
    logistic.fit(datasets["train"]["X"], datasets["train"]["y"])
    logistic_result = score_model("logistic_c1", lambda x: logistic.predict_proba(x)[:, 1], datasets, rates)

    rng = np.random.default_rng(RANDOM_SEED)
    train_x, train_y = datasets["train"]["X"], datasets["train"]["y"]
    if len(train_x) > args.nonlinear_max_train:
        idx = np.sort(rng.choice(len(train_x), size=args.nonlinear_max_train, replace=False))
        hgb_x, hgb_y = train_x[idx], train_y[idx]
    else:
        hgb_x, hgb_y = train_x, train_y
    hgb = HistGradientBoostingClassifier(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )
    hgb.fit(hgb_x, hgb_y)
    hgb_result = score_model("hist_gradient_boosting_fixed", lambda x: hgb.predict_proba(x)[:, 1], datasets, rates)
    hgb_result["training_states_used"] = int(len(hgb_x))

    baseline_rate_report = {
        f"b{book}_T-{hours}h": rates[(book, hours)] for book in SELECTED_BOOKS for hours in CUTOFFS
    }
    report = {
        "experiment": "002_bookmaker_move_hazard",
        "status": "executed",
        "archive": archive_meta,
        "selected_books": [{"slot": f"b{book}", "source_name": BOOKMAKER_NAMES[book]} for book in SELECTED_BOOKS],
        "eligible_state_counts": {split: int(len(data["X"])) for split, data in datasets.items()},
        "diagnostics": diagnostics,
        "training_baseline_move_rates": baseline_rate_report,
        "models": [logistic_result, hgb_result],
        "any_model_promoted": bool(logistic_result["promotion"]["promoted"] or hgb_result["promotion"]["promoted"]),
    }
    (root / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "eligible_state_counts": report["eligible_state_counts"],
        "logistic_test": logistic_result["splits"]["test"],
        "logistic_promotion": logistic_result["promotion"],
        "hgb_test": hgb_result["splits"]["test"],
        "hgb_promotion": hgb_result["promotion"],
        "any_model_promoted": report["any_model_promoted"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
