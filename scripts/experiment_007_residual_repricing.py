from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

import experiment_006_independent_residual_outcome as exp6


SIGNAL_CUTOFFS = (48, 24, 12, 6)
RANDOM_SEED = 20260718
TARGET_COLUMNS = ["future_delta_h", "future_delta_d", "future_delta_a"]
RESIDUAL_COLUMNS = [
    "move_surprise", "move_surprise_abs",
    "conditional_residual_home", "conditional_residual_draw", "conditional_residual_away",
    "conditional_residual_l2",
    "action_residual_home", "action_residual_draw", "action_residual_away",
    "action_residual_l2",
    "prior_residual_cutoffs", "prior_move_surprise_mean", "prior_abs_move_surprise_mean",
    "prior_action_residual_l2_mean",
    "prior_action_residual_home_sum", "prior_action_residual_draw_sum", "prior_action_residual_away_sum",
]


def filtered_source(odds_path: Path) -> pd.DataFrame:
    source = pd.read_csv(odds_path)
    source["date_start"] = pd.to_datetime(source["date_start"], format="%m/%d/%Y %H:%M", errors="coerce")
    source["date_created"] = pd.to_datetime(source["date_created"], format="%m/%d/%Y %H:%M", errors="coerce")
    for column in ("home_team_odd", "tie_odd", "away_team_odd"):
        source[column] = pd.to_numeric(source[column], errors="coerce")
    source = source.dropna(
        subset=["match_id", "date_start", "date_created", "home_team_odd", "tie_odd", "away_team_odd"]
    )
    source = source[
        (source["date_created"] <= source["date_start"])
        & (source[["home_team_odd", "tie_odd", "away_team_odd"]] > 1.0).all(axis=1)
    ].copy()
    source["match_id"] = source["match_id"].astype(str)
    source.sort_values(["match_id", "date_created"], inplace=True)
    return source


def add_future_targets(states: pd.DataFrame, odds_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    signals = states[states["hours"].isin(SIGNAL_CUTOFFS)].copy()
    source = filtered_source(odds_path)
    records: list[dict[str, Any]] = []
    states_by_match = {key: group for key, group in signals.groupby("match_id", sort=False)}

    for match_id, source_group in source.groupby("match_id", sort=False):
        state_group = states_by_match.get(str(match_id))
        if state_group is None:
            continue
        times_ns = source_group["date_created"].to_numpy(dtype="datetime64[ns]").astype(np.int64)
        odds = source_group[["home_team_odd", "tie_odd", "away_team_odd"]].to_numpy(dtype=float)
        for row in state_group.itertuples(index=False):
            observation_index = int(row.next_source_index)
            target_time = pd.Timestamp(row.kickoff).as_unit("ns") - pd.Timedelta(hours=int(row.hours) - 4)
            future_index = int(np.searchsorted(times_ns, target_time.value, side="right") - 1)
            if future_index < 0 or observation_index < 0 or observation_index >= len(odds):
                continue
            observation_odds = odds[observation_index]
            future_odds = odds[future_index]
            future_probability, future_overround = exp6.devig(future_odds)
            observation_probability = np.array([row.next_h, row.next_d, row.next_a], dtype=float)
            future_delta = future_probability - observation_probability
            records.append(
                {
                    "match_id": str(match_id),
                    "hours": int(row.hours),
                    "future_source_index": future_index,
                    "future_move": int(np.any(np.abs(future_odds - observation_odds) > 1e-12)),
                    "future_h": float(future_probability[0]),
                    "future_d": float(future_probability[1]),
                    "future_a": float(future_probability[2]),
                    "future_overround": float(future_overround),
                    "future_delta_h": float(future_delta[0]),
                    "future_delta_d": float(future_delta[1]),
                    "future_delta_a": float(future_delta[2]),
                }
            )

    target = pd.DataFrame.from_records(records)
    if target.empty:
        raise RuntimeError("no future repricing targets reconstructed")
    if target.duplicated(["match_id", "hours"]).any():
        raise RuntimeError("duplicate future repricing targets")
    output = signals.merge(target, on=["match_id", "hours"], how="inner", validate="one_to_one")
    profile = {
        "signal_states": int(len(signals)),
        "target_states": int(len(output)),
        "target_matches": int(output["match_id"].nunique()),
        "future_moves": int(output["future_move"].sum()),
        "future_move_rate": float(output["future_move"].mean()),
        "by_cutoff": {
            f"T-{int(hours)}h": {
                "states": int(len(group)),
                "future_moves": int(group["future_move"].sum()),
                "future_move_rate": float(group["future_move"].mean()),
            }
            for hours, group in output.groupby("hours", sort=False)
        },
    }
    return output, profile


def join_residuals(states_with_targets: pd.DataFrame, residuals: pd.DataFrame) -> pd.DataFrame:
    residual = residuals[residuals["hours"].isin(SIGNAL_CUTOFFS)].copy()
    needed = ["match_id", "hours", *RESIDUAL_COLUMNS]
    missing = sorted(set(needed) - set(residual.columns))
    if missing:
        raise ValueError(f"residual output missing columns: {missing}")
    joined = states_with_targets.merge(residual[needed], on=["match_id", "hours"], how="inner", validate="one_to_one")
    if joined.empty:
        raise RuntimeError("empty state/residual/target join")
    return joined


def add_model_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    output = frame.copy()
    cutoff_columns: list[str] = []
    for hours in SIGNAL_CUTOFFS:
        column = f"cutoff_T{hours}"
        output[column] = (output["hours"].to_numpy(dtype=int) == hours).astype(float)
        cutoff_columns.append(column)
    raw_columns = [
        *exp6.FEATURE_COLUMNS,
        "actual_move", "actual_delta_h", "actual_delta_d", "actual_delta_a",
        "next_h", "next_d", "next_a", "next_overround",
        *cutoff_columns,
    ]
    augmented_columns = raw_columns + RESIDUAL_COLUMNS
    for name, columns in (("raw", raw_columns), ("augmented", augmented_columns)):
        values = output[columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            bad = np.asarray(columns)[~np.isfinite(values).all(axis=0)].tolist()
            raise ValueError(f"non-finite {name} features: {bad}")
    return output, raw_columns, augmented_columns


def fixed_classifier() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )


def fixed_regressor() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )


def brier_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    p = np.clip(probability.astype(float), 1e-8, 1 - 1e-8)
    return {
        "brier": float(np.mean((y - p) ** 2)),
        "log_loss": float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p)))),
        "move_rate": float(y.mean()),
        "mean_prediction": float(p.mean()),
    }


def evaluate_hazard(test: pd.DataFrame, baseline_p: np.ndarray, augmented_p: np.ndarray) -> dict[str, Any]:
    y = test["future_move"].to_numpy(dtype=float)
    baseline = brier_metrics(y, baseline_p)
    augmented = brier_metrics(y, augmented_p)
    row_improvement = (y - baseline_p) ** 2 - (y - augmented_p) ** 2
    bootstrap = exp6.bootstrap_match_improvement(test["match_id"].to_numpy(), row_improvement, replicates=1000)
    by_cutoff: dict[str, Any] = {}
    improved_cutoffs = 0
    for hours in SIGNAL_CUTOFFS:
        mask = test["hours"].to_numpy(dtype=int) == hours
        base_brier = float(np.mean((y[mask] - baseline_p[mask]) ** 2))
        aug_brier = float(np.mean((y[mask] - augmented_p[mask]) ** 2))
        improvement = base_brier - aug_brier
        by_cutoff[f"T-{hours}h"] = {
            "states": int(mask.sum()),
            "baseline_brier": base_brier,
            "augmented_brier": aug_brier,
            "brier_improvement": float(improvement),
        }
        if improvement > 0:
            improved_cutoffs += 1
    checks = {
        "augmented_brier_lower": augmented["brier"] < baseline["brier"],
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "improves_at_least_3_of_4_cutoffs": improved_cutoffs >= 3,
    }
    return {
        "baseline": baseline,
        "augmented": augmented,
        "brier_improvement": float(baseline["brier"] - augmented["brier"]),
        "relative_brier_improvement": float((baseline["brier"] - augmented["brier"]) / baseline["brier"]),
        "paired_match_bootstrap": bootstrap,
        "by_cutoff": by_cutoff,
        "improved_cutoffs": improved_cutoffs,
        "checks": checks,
        "promoted": all(checks.values()),
    }


def row_mae(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    return np.mean(np.abs(actual - predicted), axis=1)


def evaluate_conditional(
    test_movers: pd.DataFrame,
    baseline_prediction: np.ndarray,
    augmented_prediction: np.ndarray,
) -> dict[str, Any]:
    actual = test_movers[TARGET_COLUMNS].to_numpy(dtype=float)
    baseline_row = row_mae(actual, baseline_prediction)
    augmented_row = row_mae(actual, augmented_prediction)
    row_improvement = baseline_row - augmented_row
    bootstrap = exp6.bootstrap_match_improvement(test_movers["match_id"].to_numpy(), row_improvement, replicates=1000)
    by_cutoff: dict[str, Any] = {}
    improved_cutoffs = 0
    for hours in SIGNAL_CUTOFFS:
        mask = test_movers["hours"].to_numpy(dtype=int) == hours
        baseline_mae = float(baseline_row[mask].mean())
        augmented_mae = float(augmented_row[mask].mean())
        improvement = baseline_mae - augmented_mae
        by_cutoff[f"T-{hours}h"] = {
            "mover_states": int(mask.sum()),
            "baseline_mae": baseline_mae,
            "augmented_mae": augmented_mae,
            "mae_improvement": float(improvement),
        }
        if improvement > 0:
            improved_cutoffs += 1
    baseline_mae = float(baseline_row.mean())
    augmented_mae = float(augmented_row.mean())
    checks = {
        "augmented_mae_lower": augmented_mae < baseline_mae,
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "improves_at_least_3_of_4_cutoffs": improved_cutoffs >= 3,
    }
    return {
        "mover_states": int(len(test_movers)),
        "matches": int(test_movers["match_id"].nunique()),
        "baseline_mae": baseline_mae,
        "augmented_mae": augmented_mae,
        "mae_improvement": float(baseline_mae - augmented_mae),
        "relative_mae_improvement": float((baseline_mae - augmented_mae) / baseline_mae),
        "paired_match_bootstrap": bootstrap,
        "by_cutoff": by_cutoff,
        "improved_cutoffs": improved_cutoffs,
        "checks": checks,
        "promoted": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Test whether abnormal residuals predict subsequent three-hour market repricing.")
    parser.add_argument("--output-root", default="artifacts/experiment-007")
    parser.add_argument("--source-root", default=None)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress_path = root / "progress.json"
    failure_path = root / "failure.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True), encoding="utf-8")

    try:
        progress("acquiring_source")
        source_root = Path(args.source_root) if args.source_root else None
        odds_path, _results_path, source_meta = exp6.acquire_source(root, source_root)
        progress("reconstructing_states")
        states, state_profile = exp6.reconstruct_states(odds_path)
        states["split"] = exp6.assign_split(states["kickoff"])
        train, validation, test = (
            states[states["split"] == label].copy()
            for label in ("train", "validation", "test")
        )

        progress("training_normal_models")
        hazard_model = exp6.fixed_hazard_model()
        hazard_model.fit(train[exp6.FEATURE_COLUMNS], train["actual_move"])
        train_movers = train[train["actual_move"] == 1].copy()
        movement_models: list[HistGradientBoostingRegressor] = []
        for target in ("actual_delta_h", "actual_delta_d", "actual_delta_a"):
            model = exp6.fixed_movement_model()
            model.fit(train_movers[exp6.FEATURE_COLUMNS], train_movers[target])
            movement_models.append(model)

        progress("freezing_residuals")
        validation_residuals = exp6.generate_residuals(validation, hazard_model, movement_models)
        test_residuals = exp6.generate_residuals(test, hazard_model, movement_models)

        progress("building_future_targets")
        validation_targets, validation_target_profile = add_future_targets(validation, odds_path)
        test_targets, test_target_profile = add_future_targets(test, odds_path)
        validation_model = join_residuals(validation_targets, validation_residuals)
        test_model = join_residuals(test_targets, test_residuals)
        validation_model, baseline_columns, augmented_columns = add_model_features(validation_model)
        test_model, baseline_test, augmented_test = add_model_features(test_model)
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test feature schemas differ")

        progress("training_repricing_hazard")
        baseline_hazard = fixed_classifier()
        augmented_hazard = fixed_classifier()
        baseline_hazard.fit(validation_model[baseline_columns], validation_model["future_move"])
        augmented_hazard.fit(validation_model[augmented_columns], validation_model["future_move"])
        baseline_probability = baseline_hazard.predict_proba(test_model[baseline_columns])[:, 1]
        augmented_probability = augmented_hazard.predict_proba(test_model[augmented_columns])[:, 1]
        hazard_result = evaluate_hazard(test_model, baseline_probability, augmented_probability)

        progress("training_conditional_repricing")
        validation_movers = validation_model[validation_model["future_move"] == 1].copy()
        test_movers = test_model[test_model["future_move"] == 1].copy()
        if validation_movers.empty or test_movers.empty:
            raise RuntimeError("empty validation/test future-mover set")
        baseline_prediction = np.empty((len(test_movers), 3), dtype=float)
        augmented_prediction = np.empty((len(test_movers), 3), dtype=float)
        for outcome_index, target in enumerate(TARGET_COLUMNS):
            baseline_model = fixed_regressor()
            augmented_model = fixed_regressor()
            baseline_model.fit(validation_movers[baseline_columns], validation_movers[target])
            augmented_model.fit(validation_movers[augmented_columns], validation_movers[target])
            baseline_prediction[:, outcome_index] = baseline_model.predict(test_movers[baseline_columns])
            augmented_prediction[:, outcome_index] = augmented_model.predict(test_movers[augmented_columns])
        conditional_result = evaluate_conditional(test_movers, baseline_prediction, augmented_prediction)

        report = {
            "experiment": "007_abnormal_residual_subsequent_market_repricing",
            "status": "completed",
            "source": source_meta,
            "state_profile": state_profile,
            "validation_target_profile": validation_target_profile,
            "test_target_profile": test_target_profile,
            "validation_rows": int(len(validation_model)),
            "validation_matches": int(validation_model["match_id"].nunique()),
            "test_rows": int(len(test_model)),
            "test_matches": int(test_model["match_id"].nunique()),
            "baseline_features": baseline_columns,
            "residual_features": RESIDUAL_COLUMNS,
            "future_move_hazard": hazard_result,
            "conditional_future_repricing": conditional_result,
            "overall_residual_repricing_promoted": bool(hazard_result["promoted"] and conditional_result["promoted"]),
        }
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
