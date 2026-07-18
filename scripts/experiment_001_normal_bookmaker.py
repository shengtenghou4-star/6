from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


DATASET_SLUG = "austro/beat-the-bookie-worldwide-football-dataset"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
SERIES_FILES = ("odds_series.csv.gz", "odds_series_b.csv.gz")
OUTCOMES = ("home", "draw", "away")
BOOKS = tuple(range(1, 33))
CUTOFFS = {
    48: 23,
    24: 47,
    12: 59,
    6: 65,
    3: 68,
    1: 70,
}
RANDOM_SEED = 20260718
BOOKMAKER_NAMES = {
    1: "Interwetten", 2: "bwin", 3: "bet-at-home", 4: "Unibet", 5: "Stan James", 6: "Expekt",
    7: "10Bet", 8: "William Hill", 9: "bet365", 10: "Pinnacle", 11: "DOXXbet", 12: "Betsafe",
    13: "Betway", 14: "888sport", 15: "Ladbrokes", 16: "Betclic", 17: "Sportingbet", 18: "myBet",
    19: "Betsson", 20: "188BET", 21: "Jetbull", 22: "Paddy Power", 23: "Tipico", 24: "Coral",
    25: "SBOBET", 26: "BetVictor", 27: "12BET", 28: "Titanbet", 29: "youwin", 30: "ComeOn",
    31: "Betadonis", 32: "Betfair Sports",
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
                raise ValueError(f"missing required file: {name}")
            target = destination / name
            with zf.open(name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            result[name] = target
    return result


def split_name(dates: pd.Series) -> np.ndarray:
    values = dates.to_numpy(dtype="datetime64[D]")
    train_end = np.datetime64("2016-06-30")
    val_end = np.datetime64("2016-08-31")
    output = np.full(len(values), "test", dtype=object)
    output[values <= train_end] = "train"
    output[(values > train_end) & (values <= val_end)] = "validation"
    return output


def odds_columns(books: tuple[int, ...] | list[int], indices: set[int]) -> list[str]:
    return [
        f"{outcome}_b{book}_{index}"
        for book in books
        for outcome in OUTCOMES
        for index in sorted(indices)
    ]


def state_columns(books: tuple[int, ...] | list[int], index: int) -> list[str]:
    return [f"{outcome}_b{book}_{index}" for book in books for outcome in OUTCOMES]


def numeric_state(frame: pd.DataFrame, books: tuple[int, ...] | list[int], index: int) -> tuple[np.ndarray, np.ndarray]:
    arr = frame[state_columns(books, index)].to_numpy(dtype=np.float64, copy=False).reshape(len(frame), len(books), 3)
    valid = np.isfinite(arr) & (arr > 1.0)
    complete = valid.all(axis=2)
    implied = np.divide(1.0, arr, out=np.full_like(arr, np.nan), where=valid)
    totals = np.nansum(implied, axis=2, keepdims=True)
    probs = np.divide(implied, totals, out=np.full_like(implied, np.nan), where=(totals > 0) & complete[:, :, None])
    probs[~complete] = np.nan
    return probs, complete


def pass1_select_books(paths: list[Path], *, chunksize: int) -> tuple[list[int], dict[str, Any]]:
    current_indices = set(CUTOFFS.values())
    usecols = ["match_date"] + odds_columns(BOOKS, current_indices)
    counts = Counter()
    train_matches = 0
    for path in paths:
        for frame in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
            dates = pd.to_datetime(frame["match_date"], errors="coerce")
            if dates.isna().any():
                raise ValueError(f"unparsed match_date in {path.name}")
            train_mask = dates <= pd.Timestamp("2016-06-30")
            train_matches += int(train_mask.sum())
            if not train_mask.any():
                continue
            sub = frame.loc[train_mask]
            for index in CUTOFFS.values():
                _, complete = numeric_state(sub, BOOKS, index)
                sums = complete.sum(axis=0)
                for book, count in zip(BOOKS, sums, strict=True):
                    counts[book] += int(count)
    selected = [book for book, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]]
    if len(selected) != 8:
        raise RuntimeError(f"could not select 8 bookmakers, got {selected}")
    return selected, {
        "training_match_rows_seen": train_matches,
        "complete_current_state_counts": {f"b{book}": counts[book] for book in BOOKS},
        "selected_books": [
            {"slot": f"b{book}", "source_name": BOOKMAKER_NAMES[book], "complete_states": counts[book]}
            for book in selected
        ],
    }


def consensus_excluding_target(
    probs: np.ndarray,
    complete: np.ndarray,
    target_index: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # probs: rows × 32 × 3. Target is excluded. Require >=3 other complete books.
    masked = np.where(complete[:, :, None], probs, np.nan)
    sums = np.nansum(masked, axis=1)
    sumsq = np.nansum(masked * masked, axis=1)
    counts = complete.sum(axis=1).astype(np.int64)

    target_valid = complete[:, target_index]
    target_probs = probs[:, target_index, :]
    counts_ex = counts - target_valid.astype(np.int64)
    sums_ex = sums - np.where(target_valid[:, None], target_probs, 0.0)
    sumsq_ex = sumsq - np.where(target_valid[:, None], target_probs * target_probs, 0.0)
    ok = counts_ex >= 3
    consensus = np.divide(sums_ex, counts_ex[:, None], out=np.full_like(sums_ex, np.nan), where=ok[:, None])
    variance = np.divide(sumsq_ex, counts_ex[:, None], out=np.full_like(sumsq_ex, np.nan), where=ok[:, None]) - consensus * consensus
    dispersion = np.sqrt(np.maximum(variance, 0.0))
    return consensus, dispersion, counts_ex


def build_records(paths: list[Path], selected_books: list[int], *, chunksize: int) -> dict[str, dict[str, Any]]:
    needed_indices = set()
    for index in CUTOFFS.values():
        needed_indices.update({index - 1, index, index + 1})
    # All books needed for current/prior consensus; selected books need next state too.
    all_consensus_indices = {index for cutoff in CUTOFFS.values() for index in (cutoff - 1, cutoff)}
    selected_next_indices = {cutoff + 1 for cutoff in CUTOFFS.values()}
    usecols = ["match_id", "match_date"]
    usecols += odds_columns(BOOKS, all_consensus_indices)
    extra_next = odds_columns(selected_books, selected_next_indices)
    usecols = list(dict.fromkeys(usecols + extra_next))

    buffers: dict[str, dict[str, list[np.ndarray]]] = {
        split: {"X": [], "y": [], "current": [], "match_id": [], "book": [], "hours": []}
        for split in ("train", "validation", "test")
    }
    diagnostics = Counter()

    for path in paths:
        for frame in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
            dates = pd.to_datetime(frame["match_date"], errors="coerce")
            if dates.isna().any():
                raise ValueError(f"unparsed match_date in {path.name}")
            splits = split_name(dates)
            match_ids_all = frame["match_id"].astype(str).to_numpy()

            state_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
            for index in sorted(all_consensus_indices):
                state_cache[index] = numeric_state(frame, BOOKS, index)
            next_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
            for index in sorted(selected_next_indices):
                next_cache[index] = numeric_state(frame, selected_books, index)

            for hours, current_index in CUTOFFS.items():
                prior_index = current_index - 1
                next_index = current_index + 1
                current_probs, current_complete = state_cache[current_index]
                prior_probs, prior_complete = state_cache[prior_index]
                next_selected_probs, next_selected_complete = next_cache[next_index]

                for selected_position, book in enumerate(selected_books):
                    book_axis = book - 1
                    own_current = current_probs[:, book_axis, :]
                    own_prior = prior_probs[:, book_axis, :]
                    own_next = next_selected_probs[:, selected_position, :]
                    own_valid = (
                        current_complete[:, book_axis]
                        & prior_complete[:, book_axis]
                        & next_selected_complete[:, selected_position]
                    )
                    consensus_current, dispersion_current, active_current = consensus_excluding_target(current_probs, current_complete, book_axis)
                    consensus_prior, _, active_prior = consensus_excluding_target(prior_probs, prior_complete, book_axis)
                    consensus_valid = (active_current >= 3) & (active_prior >= 3)
                    eligible = own_valid & consensus_valid
                    diagnostics["candidate_states"] += len(frame)
                    diagnostics["eligible_states"] += int(eligible.sum())
                    if not eligible.any():
                        continue

                    own_delta_prior = own_current - own_prior
                    consensus_delta = consensus_current - consensus_prior
                    deviation_current = own_current - consensus_current
                    active_scaled = active_current.astype(np.float64)[:, None] / 31.0
                    hours_scaled = np.full((len(frame), 1), hours / 71.0, dtype=np.float64)
                    book_onehot = np.zeros((len(frame), 8), dtype=np.float64)
                    book_onehot[:, selected_position] = 1.0

                    features = np.concatenate(
                        [
                            own_current,
                            own_prior,
                            own_delta_prior,
                            consensus_current,
                            consensus_prior,
                            consensus_delta,
                            deviation_current,
                            dispersion_current,
                            active_scaled,
                            hours_scaled,
                            book_onehot,
                        ],
                        axis=1,
                    )
                    target_delta = own_next - own_current

                    for split in ("train", "validation", "test"):
                        mask = eligible & (splits == split)
                        if not mask.any():
                            continue
                        buf = buffers[split]
                        buf["X"].append(features[mask].astype(np.float32, copy=False))
                        buf["y"].append(target_delta[mask].astype(np.float32, copy=False))
                        buf["current"].append(own_current[mask].astype(np.float32, copy=False))
                        buf["match_id"].append(match_ids_all[mask])
                        buf["book"].append(np.full(int(mask.sum()), book, dtype=np.int16))
                        buf["hours"].append(np.full(int(mask.sum()), hours, dtype=np.int16))

    result: dict[str, dict[str, Any]] = {}
    for split, buf in buffers.items():
        if not buf["X"]:
            raise RuntimeError(f"no eligible states for split {split}")
        result[split] = {
            "X": np.concatenate(buf["X"], axis=0),
            "y": np.concatenate(buf["y"], axis=0),
            "current": np.concatenate(buf["current"], axis=0),
            "match_id": np.concatenate(buf["match_id"], axis=0),
            "book": np.concatenate(buf["book"], axis=0),
            "hours": np.concatenate(buf["hours"], axis=0),
        }
    result["diagnostics"] = dict(diagnostics)
    return result


def normalize_probabilities(raw: np.ndarray) -> np.ndarray:
    clipped = np.clip(raw, 1e-6, 1.0)
    totals = clipped.sum(axis=1, keepdims=True)
    return clipped / totals


def error_vectors(pred: np.ndarray, truth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    abs_error = np.abs(pred - truth).mean(axis=1)
    sq_error = ((pred - truth) ** 2).mean(axis=1)
    return abs_error, sq_error


def summarize_predictions(
    data: dict[str, Any],
    pred_next: np.ndarray,
    *,
    selected_books: list[int],
) -> dict[str, Any]:
    truth = normalize_probabilities(data["current"] + data["y"])
    persistence = normalize_probabilities(data["current"])
    pred_next = normalize_probabilities(pred_next)
    base_abs, base_sq = error_vectors(persistence, truth)
    model_abs, model_sq = error_vectors(pred_next, truth)

    by_book: dict[str, Any] = {}
    for book in selected_books:
        mask = data["book"] == book
        if not mask.any():
            continue
        by_book[f"b{book}"] = {
            "source_name": BOOKMAKER_NAMES[book],
            "states": int(mask.sum()),
            "persistence_mae": float(base_abs[mask].mean()),
            "model_mae": float(model_abs[mask].mean()),
            "mae_improvement": float(base_abs[mask].mean() - model_abs[mask].mean()),
        }

    by_cutoff: dict[str, Any] = {}
    for hours in CUTOFFS:
        mask = data["hours"] == hours
        if not mask.any():
            continue
        by_cutoff[f"T-{hours}h"] = {
            "states": int(mask.sum()),
            "persistence_mae": float(base_abs[mask].mean()),
            "model_mae": float(model_abs[mask].mean()),
            "mae_improvement": float(base_abs[mask].mean() - model_abs[mask].mean()),
        }

    return {
        "states": int(len(truth)),
        "persistence_mae": float(base_abs.mean()),
        "model_mae": float(model_abs.mean()),
        "mae_improvement": float(base_abs.mean() - model_abs.mean()),
        "relative_mae_improvement": float((base_abs.mean() - model_abs.mean()) / base_abs.mean()),
        "persistence_rmse": float(np.sqrt(base_sq.mean())),
        "model_rmse": float(np.sqrt(model_sq.mean())),
        "by_book": by_book,
        "by_cutoff": by_cutoff,
        "_per_state_improvement": base_abs - model_abs,
    }


def bootstrap_match_improvement(data: dict[str, Any], per_state_improvement: np.ndarray, *, replicates: int = 500) -> dict[str, float]:
    # Aggregate to match first so matches with many eligible book/cutoff states do not dominate bootstrap unit counts.
    frame = pd.DataFrame({"match_id": data["match_id"], "improvement": per_state_improvement})
    match_means = frame.groupby("match_id", sort=False)["improvement"].mean().to_numpy(dtype=np.float64)
    rng = np.random.default_rng(RANDOM_SEED)
    bootstrap = np.empty(replicates, dtype=np.float64)
    n = len(match_means)
    for i in range(replicates):
        indices = rng.integers(0, n, size=n)
        bootstrap[i] = match_means[indices].mean()
    low, high = np.quantile(bootstrap, [0.025, 0.975])
    return {
        "matches": int(n),
        "mean_improvement": float(match_means.mean()),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "replicates": replicates,
    }


def clean_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def evaluate_model(
    name: str,
    model_predictor: Any,
    datasets: dict[str, dict[str, Any]],
    selected_books: list[int],
) -> dict[str, Any]:
    output: dict[str, Any] = {"model": name, "splits": {}}
    for split in ("validation", "test"):
        data = datasets[split]
        pred_delta = model_predictor(data["X"])
        pred_next = data["current"] + pred_delta
        summary = summarize_predictions(data, pred_next, selected_books=selected_books)
        bootstrap = bootstrap_match_improvement(data, summary["_per_state_improvement"])
        output["splits"][split] = {**clean_summary(summary), "match_bootstrap": bootstrap}
    return output


def promotion(model_result: dict[str, Any], selected_books: list[int]) -> dict[str, Any]:
    test = model_result["splits"]["test"]
    improved_books = sum(1 for item in test["by_book"].values() if item["mae_improvement"] > 0)
    improved_cutoffs = sum(1 for item in test["by_cutoff"].values() if item["mae_improvement"] > 0)
    checks = {
        "overall_mae_better": test["mae_improvement"] > 0,
        "bootstrap_ci_above_zero": test["match_bootstrap"]["ci95_low"] > 0,
        "improved_at_least_5_of_8_books": improved_books >= 5,
        "improved_at_least_4_of_6_cutoffs": improved_cutoffs >= 4,
    }
    return {
        "promoted": all(checks.values()),
        "checks": checks,
        "improved_books": improved_books,
        "improved_cutoffs": improved_cutoffs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run preregistered Experiment 001 normal-bookmaker behavior model.")
    parser.add_argument("--output-root", default="artifacts/experiment-001")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--nonlinear-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    archive_meta = download(DOWNLOAD_URL, archive)
    paths = extract_required(archive, extracted)
    source_paths = [paths[name] for name in SERIES_FILES]

    selected_books, selection_report = pass1_select_books(source_paths, chunksize=args.chunksize)
    datasets = build_records(source_paths, selected_books, chunksize=args.chunksize)
    diagnostics = datasets.pop("diagnostics")

    # Sanity: the experiment must never use result/score columns. Only match_id/date + odds were requested.
    split_counts = {split: int(len(data["X"])) for split, data in datasets.items()}

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    ridge.fit(datasets["train"]["X"], datasets["train"]["y"])
    ridge_result = evaluate_model("ridge_alpha_10", ridge.predict, datasets, selected_books)
    ridge_result["promotion"] = promotion(ridge_result, selected_books)

    rng = np.random.default_rng(RANDOM_SEED)
    train_x = datasets["train"]["X"]
    train_y = datasets["train"]["y"]
    if len(train_x) > args.nonlinear_max_train:
        sample_idx = np.sort(rng.choice(len(train_x), size=args.nonlinear_max_train, replace=False))
        hgb_x = train_x[sample_idx]
        hgb_y = train_y[sample_idx]
    else:
        hgb_x = train_x
        hgb_y = train_y
    hgb_models = []
    for target_index in range(3):
        model = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.08,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            random_state=RANDOM_SEED,
        )
        model.fit(hgb_x, hgb_y[:, target_index])
        hgb_models.append(model)

    def hgb_predict(x: np.ndarray) -> np.ndarray:
        return np.column_stack([model.predict(x) for model in hgb_models])

    hgb_result = evaluate_model("hist_gradient_boosting_fixed", hgb_predict, datasets, selected_books)
    hgb_result["training_states_used"] = int(len(hgb_x))
    hgb_result["promotion"] = promotion(hgb_result, selected_books)

    report = {
        "experiment": "001_conditional_normal_bookmaker_behavior",
        "status": "executed",
        "archive": archive_meta,
        "protocol": {
            "cutoffs_hours_before_kickoff": sorted(CUTOFFS, reverse=True),
            "train_end": "2016-06-30",
            "validation": ["2016-07-01", "2016-08-31"],
            "test_start": "2016-09-01",
            "invalid_decimal_odds_rule": "<=1.0 treated as missing",
            "target": "next-hour de-vigged 1X2 probability delta",
            "baseline": "persistence",
        },
        "bookmaker_selection": selection_report,
        "eligible_state_counts": split_counts,
        "diagnostics": diagnostics,
        "models": [ridge_result, hgb_result],
        "any_model_promoted": bool(ridge_result["promotion"]["promoted"] or hgb_result["promotion"]["promoted"]),
    }
    (root / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "selected_books": selection_report["selected_books"],
                "eligible_state_counts": split_counts,
                "ridge_test": ridge_result["splits"]["test"],
                "ridge_promotion": ridge_result["promotion"],
                "hgb_test": hgb_result["splits"]["test"],
                "hgb_promotion": hgb_result["promotion"],
                "any_model_promoted": report["any_model_promoted"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
