from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


DATASET_SLUG = "eladsil/football-games-odds"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
CUTOFFS = (48, 24, 12, 6, 3, 1)
OUTCOMES = ("home", "draw", "away")
RANDOM_SEED = 20260718
FEATURE_COLUMNS = [
    "cur_h", "cur_d", "cur_a",
    "prev_h", "prev_d", "prev_a",
    "delta_h", "delta_d", "delta_a",
    "overround", "prev_overround", "overround_delta",
    "hours_since_last_update", "updates_1h", "updates_6h", "updates_24h",
    "hours_scaled",
]


def download(url: str, path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256()
    total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        final_url = str(response.url)
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
                fh.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "final_url": final_url}


def acquire_source(root: Path, source_root: Path | None) -> tuple[Path, Path, dict[str, Any]]:
    if source_root is not None:
        odds_path = source_root / "Matches_Odds.csv"
        results_path = source_root / "Matches_Results.csv"
        if not odds_path.exists() or not results_path.exists():
            raise FileNotFoundError(f"source-root must contain Matches_Odds.csv and Matches_Results.csv: {source_root}")
        return odds_path, results_path, {"mode": "local_source_root", "source_root": str(source_root)}

    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    meta = download(DOWNLOAD_URL, archive)
    if not zipfile.is_zipfile(archive):
        raise ValueError("downloaded source is not a ZIP archive")
    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extracted)
    odds_path = extracted / "Matches_Odds.csv"
    results_path = extracted / "Matches_Results.csv"
    if not odds_path.exists() or not results_path.exists():
        raise FileNotFoundError("source archive missing Matches_Odds.csv or Matches_Results.csv")
    return odds_path, results_path, {"mode": "download", "archive": meta}


def devig(odds: np.ndarray) -> tuple[np.ndarray, float]:
    implied = 1.0 / odds
    total = float(implied.sum())
    return implied / total, total - 1.0


def reconstruct_states(odds_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = pd.read_csv(odds_path)
    required = {
        "match_id", "date_start", "date_created",
        "home_team_odd", "tie_odd", "away_team_odd",
    }
    missing = sorted(required - set(source.columns))
    if missing:
        raise ValueError(f"Matches_Odds.csv missing columns: {missing}")

    source["date_start"] = pd.to_datetime(source["date_start"], format="%m/%d/%Y %H:%M", errors="coerce")
    source["date_created"] = pd.to_datetime(source["date_created"], format="%m/%d/%Y %H:%M", errors="coerce")
    for column in ("home_team_odd", "tie_odd", "away_team_odd"):
        source[column] = pd.to_numeric(source[column], errors="coerce")

    source_rows = int(len(source))
    source = source.dropna(
        subset=["match_id", "date_start", "date_created", "home_team_odd", "tie_odd", "away_team_odd"]
    ).copy()
    after_required = int(len(source))
    prematch_mask = source["date_created"] <= source["date_start"]
    valid_odds_mask = (source[["home_team_odd", "tie_odd", "away_team_odd"]] > 1.0).all(axis=1)
    excluded_post_start = int((~prematch_mask).sum())
    excluded_invalid_odds = int((prematch_mask & ~valid_odds_mask).sum())
    source = source[prematch_mask & valid_odds_mask].copy()
    source.sort_values(["match_id", "date_created"], inplace=True)

    records: list[dict[str, Any]] = []
    for match_id, group in source.groupby("match_id", sort=False):
        kickoff = pd.Timestamp(group["date_start"].iloc[0]).as_unit("ns")
        if group["date_start"].nunique(dropna=False) != 1:
            raise ValueError(f"conflicting kickoff times for match_id={match_id}")
        times_ns = group["date_created"].to_numpy(dtype="datetime64[ns]").astype(np.int64)
        odds = group[["home_team_odd", "tie_odd", "away_team_odd"]].to_numpy(dtype=np.float64)
        if len(times_ns) == 0:
            continue

        def state_at(timestamp: pd.Timestamp) -> tuple[int, np.ndarray] | None:
            index = int(np.searchsorted(times_ns, timestamp.value, side="right") - 1)
            if index < 0:
                return None
            return index, odds[index]

        for hours in CUTOFFS:
            prior_t = kickoff - pd.Timedelta(hours=hours + 1)
            current_t = kickoff - pd.Timedelta(hours=hours)
            next_t = kickoff - pd.Timedelta(hours=max(hours - 1, 0))
            prior = state_at(prior_t)
            current = state_at(current_t)
            nxt = state_at(next_t)
            if prior is None or current is None or nxt is None:
                continue

            prior_index, prior_odds = prior
            current_index, current_odds = current
            next_index, next_odds = nxt
            prior_p, prior_overround = devig(prior_odds)
            current_p, current_overround = devig(current_odds)
            next_p, next_overround = devig(next_odds)
            actual_delta = next_p - current_p
            actual_move = int(np.any(np.abs(next_odds - current_odds) > 1e-12))

            def count_since(window_hours: int) -> int:
                left = np.searchsorted(
                    times_ns,
                    (current_t - pd.Timedelta(hours=window_hours)).value,
                    side="right",
                )
                right = np.searchsorted(times_ns, current_t.value, side="right")
                return int(max(0, right - left))

            hours_since_last_update = max(
                0.0,
                (current_t - pd.Timestamp(times_ns[current_index], unit="ns")).total_seconds() / 3600.0,
            )
            record = {
                "match_id": str(match_id),
                "kickoff": kickoff,
                "hours": int(hours),
                "actual_move": actual_move,
                "cur_h": float(current_p[0]),
                "cur_d": float(current_p[1]),
                "cur_a": float(current_p[2]),
                "prev_h": float(prior_p[0]),
                "prev_d": float(prior_p[1]),
                "prev_a": float(prior_p[2]),
                "delta_h": float(current_p[0] - prior_p[0]),
                "delta_d": float(current_p[1] - prior_p[1]),
                "delta_a": float(current_p[2] - prior_p[2]),
                "overround": float(current_overround),
                "prev_overround": float(prior_overround),
                "overround_delta": float(current_overround - prior_overround),
                "hours_since_last_update": float(hours_since_last_update),
                "updates_1h": count_since(1),
                "updates_6h": count_since(6),
                "updates_24h": count_since(24),
                "hours_scaled": float(hours / 48.0),
                "next_h": float(next_p[0]),
                "next_d": float(next_p[1]),
                "next_a": float(next_p[2]),
                "next_overround": float(next_overround),
                "actual_delta_h": float(actual_delta[0]),
                "actual_delta_d": float(actual_delta[1]),
                "actual_delta_a": float(actual_delta[2]),
                "prior_source_index": int(prior_index),
                "current_source_index": int(current_index),
                "next_source_index": int(next_index),
            }
            records.append(record)

    states = pd.DataFrame.from_records(records)
    if states.empty:
        raise RuntimeError("no eligible reconstructed states")
    if states.duplicated(["match_id", "hours"]).any():
        raise RuntimeError("duplicate match/cutoff states")
    numeric = states.select_dtypes(include=[np.number])
    if not np.isfinite(numeric.to_numpy(dtype=np.float64)).all():
        bad = numeric.columns[~np.isfinite(numeric.to_numpy(dtype=np.float64)).all(axis=0)].tolist()
        raise ValueError(f"non-finite reconstructed states: {bad}")

    profile = {
        "source_rows": source_rows,
        "rows_after_required_fields": after_required,
        "eligible_prematch_valid_odds_rows": int(len(source)),
        "excluded_post_start_rows": excluded_post_start,
        "excluded_invalid_odds_rows": excluded_invalid_odds,
        "state_rows": int(len(states)),
        "unique_matches": int(states["match_id"].nunique()),
    }
    return states, profile


def assign_split(kickoff: pd.Series) -> np.ndarray:
    dates = pd.to_datetime(kickoff, errors="raise").to_numpy(dtype="datetime64[ns]")
    train_end = np.datetime64("2017-10-31T23:59:59", "ns")
    validation_start = np.datetime64("2017-11-01T00:00:00", "ns")
    validation_end = np.datetime64("2017-12-31T23:59:59", "ns")
    return np.where(
        dates <= train_end,
        "train",
        np.where((dates >= validation_start) & (dates <= validation_end), "validation", "test"),
    ).astype(object)


def split_profile(states: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for split, group in states.groupby("split", sort=True):
        output[str(split)] = {
            "states": int(len(group)),
            "matches": int(group["match_id"].nunique()),
            "moves": int(group["actual_move"].sum()),
            "move_rate": float(group["actual_move"].mean()),
            "by_cutoff": {
                f"T-{int(hours)}h": {
                    "states": int(len(cutoff_group)),
                    "moves": int(cutoff_group["actual_move"].sum()),
                    "move_rate": float(cutoff_group["actual_move"].mean()),
                }
                for hours, cutoff_group in group.groupby("hours", sort=False)
            },
        }
    return output


def fixed_hazard_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )


def fixed_movement_model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )


def conditional_means(train_movers: pd.DataFrame) -> dict[int, np.ndarray]:
    target_columns = ["actual_delta_h", "actual_delta_d", "actual_delta_a"]
    global_mean = train_movers[target_columns].mean().to_numpy(dtype=float)
    output: dict[int, np.ndarray] = {}
    for hours in CUTOFFS:
        group = train_movers[train_movers["hours"] == hours]
        output[hours] = group[target_columns].mean().to_numpy(dtype=float) if not group.empty else global_mean.copy()
    return output


def predict_conditional_baseline(frame: pd.DataFrame, means: dict[int, np.ndarray]) -> np.ndarray:
    return np.vstack([means[int(hours)] for hours in frame["hours"].to_numpy(dtype=int)])


def movement_row_mae(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    return np.mean(np.abs(actual - predicted), axis=1)


def bootstrap_match_improvement(
    match_ids: np.ndarray,
    row_improvement: np.ndarray,
    *,
    replicates: int = 1000,
) -> dict[str, Any]:
    temp = pd.DataFrame({"match_id": match_ids.astype(str), "improvement": row_improvement})
    grouped = temp.groupby("match_id", sort=False)["improvement"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(dtype=np.float64)
    counts = grouped["count"].to_numpy(dtype=np.int64)
    rng = np.random.default_rng(RANDOM_SEED)
    draws = np.empty(replicates, dtype=np.float64)
    for index in range(replicates):
        sampled = rng.integers(0, len(sums), size=len(sums))
        draws[index] = sums[sampled].sum() / counts[sampled].sum()
    low, high = np.quantile(draws, [0.025, 0.975])
    return {
        "matches": int(len(sums)),
        "replicates": int(replicates),
        "mean_improvement": float(sums.sum() / counts.sum()),
        "ci95_low": float(low),
        "ci95_high": float(high),
    }


def evaluate_conditional_movement(
    test_movers: pd.DataFrame,
    model_prediction: np.ndarray,
    baseline_prediction: np.ndarray,
) -> dict[str, Any]:
    actual = test_movers[["actual_delta_h", "actual_delta_d", "actual_delta_a"]].to_numpy(dtype=float)
    model_row = movement_row_mae(actual, model_prediction)
    baseline_row = movement_row_mae(actual, baseline_prediction)
    row_improvement = baseline_row - model_row
    by_cutoff: dict[str, Any] = {}
    improved_cutoffs = 0
    for hours in CUTOFFS:
        mask = test_movers["hours"].to_numpy(dtype=int) == hours
        if not mask.any():
            by_cutoff[f"T-{hours}h"] = {"mover_states": 0, "available": False}
            continue
        baseline_mae = float(baseline_row[mask].mean())
        model_mae = float(model_row[mask].mean())
        improvement = baseline_mae - model_mae
        by_cutoff[f"T-{hours}h"] = {
            "available": True,
            "mover_states": int(mask.sum()),
            "baseline_mae": baseline_mae,
            "model_mae": model_mae,
            "mae_improvement": float(improvement),
        }
        if improvement > 0:
            improved_cutoffs += 1
    bootstrap = bootstrap_match_improvement(
        test_movers["match_id"].to_numpy(),
        row_improvement,
        replicates=1000,
    )
    baseline_mae = float(baseline_row.mean())
    model_mae = float(model_row.mean())
    checks = {
        "model_mae_lower": model_mae < baseline_mae,
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "improves_at_least_4_of_6_cutoffs": improved_cutoffs >= 4,
    }
    return {
        "mover_states": int(len(test_movers)),
        "matches": int(test_movers["match_id"].nunique()),
        "baseline_mae": baseline_mae,
        "model_mae": model_mae,
        "mae_improvement": float(baseline_mae - model_mae),
        "relative_mae_improvement": float((baseline_mae - model_mae) / baseline_mae),
        "by_cutoff": by_cutoff,
        "improved_cutoffs": improved_cutoffs,
        "paired_match_bootstrap": bootstrap,
        "checks": checks,
        "conditional_movement_promoted": all(checks.values()),
    }


def generate_residuals(
    frame: pd.DataFrame,
    hazard_model: HistGradientBoostingClassifier,
    movement_models: list[HistGradientBoostingRegressor],
) -> pd.DataFrame:
    output = frame.copy()
    output["predicted_move_probability"] = hazard_model.predict_proba(output[FEATURE_COLUMNS])[:, 1]
    predicted_delta = np.column_stack([model.predict(output[FEATURE_COLUMNS]) for model in movement_models])
    actual_delta = output[["actual_delta_h", "actual_delta_d", "actual_delta_a"]].to_numpy(dtype=float)
    actual_move = output["actual_move"].to_numpy(dtype=float)
    move_probability = output["predicted_move_probability"].to_numpy(dtype=float)

    output["move_surprise"] = actual_move - move_probability
    output["move_surprise_abs"] = np.abs(output["move_surprise"].to_numpy(dtype=float))

    conditional_residual = actual_delta - predicted_delta
    conditional_residual[actual_move == 0.0, :] = 0.0
    expected_delta = move_probability[:, None] * predicted_delta
    action_residual = actual_delta - expected_delta

    for index, outcome in enumerate(OUTCOMES):
        output[f"predicted_conditional_delta_{outcome}"] = predicted_delta[:, index]
        output[f"conditional_residual_{outcome}"] = conditional_residual[:, index]
        output[f"expected_delta_{outcome}"] = expected_delta[:, index]
        output[f"action_residual_{outcome}"] = action_residual[:, index]

    output["conditional_residual_l2"] = np.linalg.norm(conditional_residual, axis=1)
    output["action_residual_l2"] = np.linalg.norm(action_residual, axis=1)

    output["prior_residual_cutoffs"] = 0.0
    output["prior_move_surprise_mean"] = 0.0
    output["prior_abs_move_surprise_mean"] = 0.0
    output["prior_action_residual_l2_mean"] = 0.0
    for outcome in OUTCOMES:
        output[f"prior_action_residual_{outcome}_sum"] = 0.0

    order_rank = {hours: index for index, hours in enumerate(CUTOFFS)}
    output["_cutoff_rank"] = output["hours"].map(order_rank).astype(int)
    output.sort_values(["match_id", "_cutoff_rank"], inplace=True)

    for _match_id, group in output.groupby("match_id", sort=False):
        prior_move: list[float] = []
        prior_abs_move: list[float] = []
        prior_l2: list[float] = []
        prior_sums = np.zeros(3, dtype=float)
        for index in group.sort_values("_cutoff_rank").index:
            output.at[index, "prior_residual_cutoffs"] = float(len(prior_move))
            if prior_move:
                output.at[index, "prior_move_surprise_mean"] = float(np.mean(prior_move))
                output.at[index, "prior_abs_move_surprise_mean"] = float(np.mean(prior_abs_move))
                output.at[index, "prior_action_residual_l2_mean"] = float(np.mean(prior_l2))
                for outcome_index, outcome in enumerate(OUTCOMES):
                    output.at[index, f"prior_action_residual_{outcome}_sum"] = float(prior_sums[outcome_index])
            move_value = float(output.at[index, "move_surprise"])
            action_l2_value = float(output.at[index, "action_residual_l2"])
            prior_move.append(move_value)
            prior_abs_move.append(abs(move_value))
            prior_l2.append(action_l2_value)
            prior_sums += output.loc[index, [f"action_residual_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)

    output.drop(columns=["_cutoff_rank"], inplace=True)
    output.sort_values(["kickoff", "match_id", "hours"], ascending=[True, True, False], inplace=True)
    output.reset_index(drop=True, inplace=True)

    residual_columns = [
        "match_id", "kickoff", "hours",
        "next_h", "next_d", "next_a",
        "actual_move", "predicted_move_probability", "move_surprise", "move_surprise_abs",
        *[f"conditional_residual_{outcome}" for outcome in OUTCOMES],
        "conditional_residual_l2",
        *[f"action_residual_{outcome}" for outcome in OUTCOMES],
        "action_residual_l2",
        "prior_residual_cutoffs", "prior_move_surprise_mean", "prior_abs_move_surprise_mean",
        "prior_action_residual_l2_mean",
        *[f"prior_action_residual_{outcome}_sum" for outcome in OUTCOMES],
    ]
    residuals = output[residual_columns].copy()
    numeric = residuals.select_dtypes(include=[np.number])
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        bad = numeric.columns[~np.isfinite(numeric.to_numpy(dtype=float)).all(axis=0)].tolist()
        raise ValueError(f"non-finite residual values: {bad}")
    if residuals.duplicated(["match_id", "hours"]).any():
        raise RuntimeError("duplicate residual match/cutoff rows")
    return residuals


def load_outcomes(results_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    results = pd.read_csv(results_path)
    required = {"match_id", "home_team_score", "away_team_score"}
    missing = sorted(required - set(results.columns))
    if missing:
        raise ValueError(f"Matches_Results.csv missing columns: {missing}")
    results["match_id"] = results["match_id"].astype(str)
    results["home_team_score"] = pd.to_numeric(results["home_team_score"], errors="coerce")
    results["away_team_score"] = pd.to_numeric(results["away_team_score"], errors="coerce")
    results = results.dropna(subset=["match_id", "home_team_score", "away_team_score"]).copy()
    conflict = results.groupby("match_id")[["home_team_score", "away_team_score"]].nunique(dropna=False)
    conflict = conflict[(conflict["home_team_score"] > 1) | (conflict["away_team_score"] > 1)]
    if not conflict.empty:
        raise ValueError(f"conflicting scores for {len(conflict)} match IDs")
    results = results.drop_duplicates("match_id", keep="first").copy()
    home_score = results["home_team_score"].to_numpy(dtype=float)
    away_score = results["away_team_score"].to_numpy(dtype=float)
    results["outcome_class"] = np.where(home_score > away_score, 0, np.where(home_score == away_score, 1, 2)).astype(np.int8)
    return results[["match_id", "outcome_class"]], {
        "outcome_matches": int(len(results)),
        "class_counts": {str(int(key)): int(value) for key, value in results["outcome_class"].value_counts().sort_index().items()},
    }


def add_outcome_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    output = frame.copy()
    for short, outcome in zip(("h", "d", "a"), OUTCOMES, strict=True):
        probability = np.clip(output[f"next_{short}"].to_numpy(dtype=float), 1e-8, 1.0)
        output[f"log_market_{outcome}_p"] = np.log(probability)
    cutoff_columns: list[str] = []
    for hours in CUTOFFS:
        column = f"cutoff_T{hours}"
        output[column] = (output["hours"].to_numpy(dtype=int) == hours).astype(float)
        cutoff_columns.append(column)
    baseline_columns = [f"log_market_{outcome}_p" for outcome in OUTCOMES] + cutoff_columns
    residual_columns = [
        "move_surprise", "move_surprise_abs",
        *[f"conditional_residual_{outcome}" for outcome in OUTCOMES],
        "conditional_residual_l2",
        *[f"action_residual_{outcome}" for outcome in OUTCOMES],
        "action_residual_l2",
        "prior_residual_cutoffs", "prior_move_surprise_mean", "prior_abs_move_surprise_mean",
        "prior_action_residual_l2_mean",
        *[f"prior_action_residual_{outcome}_sum" for outcome in OUTCOMES],
    ]
    augmented_columns = baseline_columns + residual_columns
    return output, baseline_columns, augmented_columns


def fixed_outcome_model() -> Any:
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, random_state=RANDOM_SEED),
    )


def aligned_probabilities(model: Any, features: pd.DataFrame) -> np.ndarray:
    raw = model.predict_proba(features)
    classes = model.named_steps["logisticregression"].classes_.astype(int)
    output = np.full((len(features), 3), 1e-12, dtype=np.float64)
    for column_index, class_value in enumerate(classes):
        output[:, class_value] = raw[:, column_index]
    output /= output.sum(axis=1, keepdims=True)
    return output


def one_hot(y: np.ndarray) -> np.ndarray:
    output = np.zeros((len(y), 3), dtype=float)
    output[np.arange(len(y)), y.astype(int)] = 1.0
    return output


def outcome_metrics(y: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    p = np.clip(probabilities.astype(float), 1e-12, 1.0)
    p /= p.sum(axis=1, keepdims=True)
    log_loss_rows = -np.log(p[np.arange(len(y)), y.astype(int)])
    brier_rows = np.sum((one_hot(y) - p) ** 2, axis=1)
    return {
        "rows": int(len(y)),
        "log_loss": float(log_loss_rows.mean()),
        "multiclass_brier": float(brier_rows.mean()),
        "accuracy": float((np.argmax(p, axis=1) == y).mean()),
        "mean_predicted": {str(index): float(p[:, index].mean()) for index in range(3)},
        "observed_frequency": {str(index): float((y == index).mean()) for index in range(3)},
    }


def outcome_by_cutoff(frame: pd.DataFrame, probabilities: np.ndarray) -> dict[str, Any]:
    y = frame["outcome_class"].to_numpy(dtype=np.int8)
    output: dict[str, Any] = {}
    for hours in CUTOFFS:
        mask = frame["hours"].to_numpy(dtype=int) == hours
        if not mask.any():
            output[f"T-{hours}h"] = {"available": False, "rows": 0}
            continue
        output[f"T-{hours}h"] = {"available": True, **outcome_metrics(y[mask], probabilities[mask])}
    return output


def evaluate_outcome_layer(validation: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    validation, baseline_columns, augmented_columns = add_outcome_features(validation)
    test, baseline_test, augmented_test = add_outcome_features(test)
    if baseline_columns != baseline_test or augmented_columns != augmented_test:
        raise RuntimeError("validation/test outcome feature schemas differ")
    for name, frame in (("validation", validation), ("test", test)):
        if sorted(frame["outcome_class"].unique().tolist()) != [0, 1, 2]:
            raise RuntimeError(f"{name} outcome split does not contain all three classes")
        values = frame[augmented_columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            bad = np.asarray(augmented_columns)[~np.isfinite(values).all(axis=0)].tolist()
            raise ValueError(f"non-finite {name} outcome features: {bad}")

    baseline_model = fixed_outcome_model()
    augmented_model = fixed_outcome_model()
    baseline_model.fit(validation[baseline_columns], validation["outcome_class"])
    augmented_model.fit(validation[augmented_columns], validation["outcome_class"])

    direct_market = test[["next_h", "next_d", "next_a"]].to_numpy(dtype=float, copy=True)
    direct_market /= direct_market.sum(axis=1, keepdims=True)
    fitted_baseline = aligned_probabilities(baseline_model, test[baseline_columns])
    augmented = aligned_probabilities(augmented_model, test[augmented_columns])
    y = test["outcome_class"].to_numpy(dtype=np.int8)

    direct_metrics = outcome_metrics(y, direct_market)
    baseline_metrics = outcome_metrics(y, fitted_baseline)
    augmented_metrics = outcome_metrics(y, augmented)
    baseline_cutoff = outcome_by_cutoff(test, fitted_baseline)
    augmented_cutoff = outcome_by_cutoff(test, augmented)

    improved_cutoffs = 0
    cutoff_improvements: dict[str, Any] = {}
    for hours in CUTOFFS:
        key = f"T-{hours}h"
        if not baseline_cutoff[key].get("available"):
            cutoff_improvements[key] = {"available": False}
            continue
        improvement = baseline_cutoff[key]["log_loss"] - augmented_cutoff[key]["log_loss"]
        cutoff_improvements[key] = {
            "available": True,
            "fitted_market_log_loss": baseline_cutoff[key]["log_loss"],
            "augmented_log_loss": augmented_cutoff[key]["log_loss"],
            "log_loss_improvement": float(improvement),
        }
        if improvement > 0:
            improved_cutoffs += 1

    row_improvement = (
        -np.log(np.clip(fitted_baseline[np.arange(len(y)), y], 1e-12, 1.0))
        + np.log(np.clip(augmented[np.arange(len(y)), y], 1e-12, 1.0))
    )
    bootstrap = bootstrap_match_improvement(
        test["match_id"].to_numpy(),
        row_improvement,
        replicates=1000,
    )
    checks = {
        "augmented_beats_fitted_market_log_loss": augmented_metrics["log_loss"] < baseline_metrics["log_loss"],
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "augmented_brier_improves": augmented_metrics["multiclass_brier"] < baseline_metrics["multiclass_brier"],
        "improves_at_least_4_of_6_cutoffs": improved_cutoffs >= 4,
        "augmented_beats_direct_market_log_loss": augmented_metrics["log_loss"] < direct_metrics["log_loss"],
    }
    return {
        "validation_rows": int(len(validation)),
        "validation_matches": int(validation["match_id"].nunique()),
        "test_rows": int(len(test)),
        "test_matches": int(test["match_id"].nunique()),
        "baseline_features": baseline_columns,
        "residual_features": [column for column in augmented_columns if column not in baseline_columns],
        "direct_t_plus_1_market": direct_metrics,
        "fitted_market_only": baseline_metrics,
        "augmented_residual": augmented_metrics,
        "fitted_market_minus_augmented_log_loss": float(baseline_metrics["log_loss"] - augmented_metrics["log_loss"]),
        "direct_market_minus_augmented_log_loss": float(direct_metrics["log_loss"] - augmented_metrics["log_loss"]),
        "fitted_market_minus_augmented_brier": float(baseline_metrics["multiclass_brier"] - augmented_metrics["multiclass_brier"]),
        "paired_match_bootstrap": bootstrap,
        "cutoff_improvements": cutoff_improvements,
        "improved_cutoffs": improved_cutoffs,
        "checks": checks,
        "residual_outcome_information_promoted": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run independent exact-timestamp residual outcome-information experiment.")
    parser.add_argument("--output-root", default="artifacts/experiment-006")
    parser.add_argument("--source-root", default=None)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    failure_path = root / "failure.json"
    progress_path = root / "progress.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True), encoding="utf-8")

    try:
        source_root = Path(args.source_root) if args.source_root else None
        progress("acquiring_source")
        odds_path, results_path, source_meta = acquire_source(root, source_root)

        progress("reconstructing_states")
        states, state_source_profile = reconstruct_states(odds_path)
        states["split"] = assign_split(states["kickoff"])
        profile = split_profile(states)
        (root / "state_profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
        train, validation, test = (
            states[states["split"] == label].copy()
            for label in ("train", "validation", "test")
        )
        for label, frame in (("train", train), ("validation", validation), ("test", test)):
            if frame.empty:
                raise RuntimeError(f"empty split: {label}")
            if len(np.unique(frame["actual_move"].to_numpy(dtype=int))) < 2:
                raise RuntimeError(f"split contains one move class: {label}")

        progress("training_normal_models", train_states=int(len(train)))
        hazard_model = fixed_hazard_model()
        hazard_model.fit(train[FEATURE_COLUMNS], train["actual_move"])
        train_movers = train[train["actual_move"] == 1].copy()
        if train_movers.empty:
            raise RuntimeError("no training mover states")
        movement_models: list[HistGradientBoostingRegressor] = []
        for target in ("actual_delta_h", "actual_delta_d", "actual_delta_a"):
            model = fixed_movement_model()
            model.fit(train_movers[FEATURE_COLUMNS], train_movers[target])
            movement_models.append(model)
        mean_baseline = conditional_means(train_movers)

        progress("evaluating_conditional_movement")
        test_movers = test[test["actual_move"] == 1].copy()
        model_prediction = np.column_stack([model.predict(test_movers[FEATURE_COLUMNS]) for model in movement_models])
        baseline_prediction = predict_conditional_baseline(test_movers, mean_baseline)
        movement_result = evaluate_conditional_movement(test_movers, model_prediction, baseline_prediction)

        report: dict[str, Any] = {
            "experiment": "006_independent_exact_timestamp_residual_outcome_information",
            "status": "completed_normal_action_gate",
            "source": source_meta,
            "state_source_profile": state_source_profile,
            "split_profile": profile,
            "conditional_movement": movement_result,
            "outcomes_loaded": False,
            "outcome_test_executed": False,
        }

        if not movement_result["conditional_movement_promoted"]:
            report["status"] = "stopped_at_conditional_movement_gate"
            report["overall_residual_outcome_information_promoted"] = False
            (root / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            print(json.dumps(report, indent=2, sort_keys=True))
            failure_path.unlink(missing_ok=True)
            progress_path.unlink(missing_ok=True)
            return

        progress("generating_outcome_blind_residuals")
        validation_residuals = generate_residuals(validation, hazard_model, movement_models)
        test_residuals = generate_residuals(test, hazard_model, movement_models)
        validation_residuals.to_csv(root / "residuals_validation.csv.gz", index=False, compression="gzip")
        test_residuals.to_csv(root / "residuals_test.csv.gz", index=False, compression="gzip")

        progress("loading_outcomes_after_residual_freeze")
        outcomes, outcome_profile = load_outcomes(results_path)
        report["outcomes_loaded"] = True
        validation_joined = validation_residuals.merge(outcomes, on="match_id", how="inner", validate="many_to_one")
        test_joined = test_residuals.merge(outcomes, on="match_id", how="inner", validate="many_to_one")
        if validation_joined.empty or test_joined.empty:
            raise RuntimeError("empty residual/outcome join")

        progress("running_outcome_layer", validation_rows=int(len(validation_joined)), test_rows=int(len(test_joined)))
        outcome_result = evaluate_outcome_layer(validation_joined, test_joined)
        report["status"] = "completed"
        report["outcome_profile"] = outcome_profile
        report["outcome_test_executed"] = True
        report["outcome_layer"] = outcome_result
        report["overall_residual_outcome_information_promoted"] = bool(
            movement_result["conditional_movement_promoted"]
            and outcome_result["residual_outcome_information_promoted"]
        )
        (root / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        failure_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "progress": json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else None,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
