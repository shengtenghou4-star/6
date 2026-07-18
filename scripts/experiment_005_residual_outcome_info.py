from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


OUTCOMES = ("home", "draw", "away")
CLASSES = np.array([0, 1, 2], dtype=np.int8)
CUTOFFS = (48, 24, 12, 6, 3, 1)
RANDOM_SEED = 20260718
MIN_BOOKS = 4
SERIES_FILES = ("odds_series.csv.gz", "odds_series_b.csv.gz")


def require_columns(frame: pd.DataFrame, columns: list[str], *, source: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{source} missing required columns: {missing}")


def safe_std(series: pd.Series) -> float:
    value = float(series.std(ddof=0))
    return value if np.isfinite(value) else 0.0


def mean_or_zero(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    return float(numeric.mean()) if numeric.notna().any() else 0.0


def max_or_zero(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    return float(numeric.max()) if numeric.notna().any() else 0.0


def aggregate_residual_file(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_csv(path, compression="gzip", low_memory=False)
    forbidden = [column for column in frame.columns if column.casefold() in {"score_home", "score_away", "result", "ftr"}]
    if forbidden:
        raise ValueError(f"outcome fields unexpectedly present in frozen residual file {path.name}: {forbidden}")

    required = [
        "match_id", "book_slot", "hours_before_kickoff", "actual_move",
        "predicted_move_probability", "move_surprise_signed", "no_move_surprise",
        "unexpected_move_surprise", "action_residual_l2", "conditional_residual_l2",
        "consensus_gap_l2", "prior_residual_cutoffs", "prior_move_surprise_mean",
        "prior_abs_move_surprise_mean", "prior_action_residual_l2_mean",
        "prior_abnormality_mean",
    ]
    for outcome in OUTCOMES:
        required.extend(
            [
                f"target_current_{outcome}_p", f"actual_delta_{outcome}",
                f"action_residual_{outcome}", f"conditional_residual_{outcome}",
                f"prior_action_residual_{outcome}_sum",
            ]
        )
    require_columns(frame, required, source=path.name)

    frame["match_id"] = frame["match_id"].astype(str)
    frame["book_slot"] = frame["book_slot"].astype(str)
    frame["hours_before_kickoff"] = pd.to_numeric(frame["hours_before_kickoff"], errors="raise").astype(int)
    if not set(frame["hours_before_kickoff"].unique()).issubset(set(CUTOFFS)):
        raise ValueError(f"unexpected cutoffs in {path.name}: {sorted(frame['hours_before_kickoff'].unique())}")

    duplicate_mask = frame.duplicated(["match_id", "book_slot", "hours_before_kickoff"], keep=False)
    if duplicate_mask.any():
        sample = frame.loc[duplicate_mask, ["match_id", "book_slot", "hours_before_kickoff"]].head(20).to_dict("records")
        raise ValueError(f"duplicate match/book/cutoff residual rows in {path.name}: {sample}")

    for outcome in OUTCOMES:
        next_column = f"market_next_{outcome}_p"
        frame[next_column] = (
            pd.to_numeric(frame[f"target_current_{outcome}_p"], errors="coerce")
            + pd.to_numeric(frame[f"actual_delta_{outcome}"], errors="coerce")
        )
        action_column = f"action_residual_{outcome}"
        frame[f"{action_column}_abs"] = pd.to_numeric(frame[action_column], errors="coerce").abs()
        frame[f"{action_column}_positive"] = (pd.to_numeric(frame[action_column], errors="coerce") > 0.0).astype(float)

    frame["move_surprise_abs"] = pd.to_numeric(frame["move_surprise_signed"], errors="coerce").abs()
    frame["actual_move"] = pd.to_numeric(frame["actual_move"], errors="raise").astype(int)

    keys = ["match_id", "hours_before_kickoff"]
    grouped = frame.groupby(keys, sort=False, observed=True)
    rows: list[dict[str, Any]] = []
    for (match_id, hours), group in grouped:
        book_count = int(group["book_slot"].nunique())
        if book_count != len(group):
            raise ValueError(f"non-unique frozen books for match={match_id}, cutoff={hours}")
        if book_count < MIN_BOOKS:
            continue

        record: dict[str, Any] = {
            "match_id": str(match_id),
            "hours_before_kickoff": int(hours),
            "book_count": book_count,
            "mover_fraction": float(group["actual_move"].mean()),
            "predicted_move_probability_mean": float(group["predicted_move_probability"].mean()),
            "move_surprise_mean": float(group["move_surprise_signed"].mean()),
            "move_surprise_std": safe_std(group["move_surprise_signed"]),
            "move_surprise_sum": float(group["move_surprise_signed"].sum()),
            "move_surprise_max_abs": float(group["move_surprise_abs"].max()),
            "no_move_surprise_mean": mean_or_zero(group["no_move_surprise"]),
            "no_move_surprise_max": max_or_zero(group["no_move_surprise"]),
            "unexpected_move_surprise_mean": mean_or_zero(group["unexpected_move_surprise"]),
            "unexpected_move_surprise_max": max_or_zero(group["unexpected_move_surprise"]),
            "action_residual_l2_mean": float(group["action_residual_l2"].mean()),
            "action_residual_l2_std": safe_std(group["action_residual_l2"]),
            "action_residual_l2_max": float(group["action_residual_l2"].max()),
            "conditional_residual_l2_mean": mean_or_zero(group["conditional_residual_l2"]),
            "conditional_residual_l2_max": max_or_zero(group["conditional_residual_l2"]),
            "consensus_gap_l2_mean": float(group["consensus_gap_l2"].mean()),
            "prior_residual_cutoffs_mean": float(group["prior_residual_cutoffs"].mean()),
            "prior_move_surprise_mean_mean": float(group["prior_move_surprise_mean"].fillna(0.0).mean()),
            "prior_abs_move_surprise_mean_mean": float(group["prior_abs_move_surprise_mean"].fillna(0.0).mean()),
            "prior_action_residual_l2_mean_mean": float(group["prior_action_residual_l2_mean"].fillna(0.0).mean()),
            "prior_abnormality_mean_mean": float(group["prior_abnormality_mean"].fillna(0.0).mean()),
        }

        market_vector = []
        for outcome in OUTCOMES:
            next_p = float(group[f"market_next_{outcome}_p"].mean())
            market_vector.append(next_p)

            action = pd.to_numeric(group[f"action_residual_{outcome}"], errors="coerce")
            conditional = pd.to_numeric(group[f"conditional_residual_{outcome}"], errors="coerce")
            record[f"action_residual_{outcome}_mean"] = float(action.mean())
            record[f"action_residual_{outcome}_std"] = safe_std(action)
            record[f"action_residual_{outcome}_sum"] = float(action.sum())
            record[f"action_residual_{outcome}_max_abs"] = float(action.abs().max())
            record[f"action_residual_{outcome}_positive_fraction"] = float((action > 0.0).mean())
            record[f"conditional_residual_{outcome}_mean"] = mean_or_zero(conditional)
            record[f"prior_action_residual_{outcome}_sum_mean"] = float(
                pd.to_numeric(group[f"prior_action_residual_{outcome}_sum"], errors="coerce").fillna(0.0).mean()
            )

        market = np.asarray(market_vector, dtype=np.float64)
        if not np.isfinite(market).all() or np.any(market <= 0.0):
            continue
        market_sum = float(market.sum())
        if market_sum <= 0.0:
            continue
        market /= market_sum
        for index, outcome in enumerate(OUTCOMES):
            record[f"market_next_{outcome}_p"] = float(market[index])

        rows.append(record)

    aggregated = pd.DataFrame.from_records(rows)
    if aggregated.empty:
        raise RuntimeError(f"no eligible aggregated match/cutoff records from {path}")
    if aggregated.duplicated(keys).any():
        raise RuntimeError(f"duplicate aggregated match/cutoff records from {path}")

    numeric = aggregated.select_dtypes(include=[np.number])
    if not np.isfinite(numeric.to_numpy(dtype=np.float64)).all():
        bad = numeric.columns[~np.isfinite(numeric.to_numpy(dtype=np.float64)).all(axis=0)].tolist()
        raise ValueError(f"non-finite aggregated features in {path.name}: {bad}")

    profile = {
        "source_rows": int(len(frame)),
        "source_unique_matches": int(frame["match_id"].nunique()),
        "aggregated_rows": int(len(aggregated)),
        "aggregated_unique_matches": int(aggregated["match_id"].nunique()),
        "rows_by_cutoff": {f"T-{int(k)}h": int(v) for k, v in aggregated["hours_before_kickoff"].value_counts().sort_index(ascending=False).items()},
        "minimum_books": MIN_BOOKS,
        "structurally_absent_conditional_aggregates_filled_with_zero": True,
    }
    return aggregated, profile


def load_outcomes(extracted_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    pieces = []
    for filename in SERIES_FILES:
        path = extracted_root / filename
        if not path.exists():
            raise FileNotFoundError(f"missing extracted source file: {path}")
        piece = pd.read_csv(
            path,
            usecols=["match_id", "score_home", "score_away"],
            compression="gzip",
            low_memory=False,
        )
        pieces.append(piece)

    outcomes = pd.concat(pieces, ignore_index=True)
    outcomes["match_id"] = outcomes["match_id"].astype(str)
    outcomes["score_home"] = pd.to_numeric(outcomes["score_home"], errors="coerce")
    outcomes["score_away"] = pd.to_numeric(outcomes["score_away"], errors="coerce")
    outcomes = outcomes.dropna(subset=["score_home", "score_away"])

    conflict_counts = outcomes.groupby("match_id")[["score_home", "score_away"]].nunique(dropna=False)
    conflicts = conflict_counts[(conflict_counts["score_home"] > 1) | (conflict_counts["score_away"] > 1)]
    if not conflicts.empty:
        raise ValueError(f"conflicting outcomes for {len(conflicts)} match IDs")

    outcomes = outcomes.drop_duplicates("match_id", keep="first").copy()
    home = outcomes["score_home"].to_numpy(dtype=float)
    away = outcomes["score_away"].to_numpy(dtype=float)
    outcomes["outcome_class"] = np.where(home > away, 0, np.where(home == away, 1, 2)).astype(np.int8)
    return outcomes[["match_id", "outcome_class"]], {
        "outcome_rows": int(len(outcomes)),
        "outcome_class_counts": {str(int(k)): int(v) for k, v in outcomes["outcome_class"].value_counts().sort_index().items()},
    }


def add_model_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    output = frame.copy()
    for outcome in OUTCOMES:
        probability = np.clip(output[f"market_next_{outcome}_p"].to_numpy(dtype=float), 1e-8, 1.0)
        output[f"log_market_{outcome}_p"] = np.log(probability)
    cutoff_features = []
    for hours in CUTOFFS:
        name = f"cutoff_T{hours}"
        output[name] = (output["hours_before_kickoff"].to_numpy() == hours).astype(float)
        cutoff_features.append(name)

    baseline = [f"log_market_{outcome}_p" for outcome in OUTCOMES] + cutoff_features
    excluded = {
        "match_id", "hours_before_kickoff", "outcome_class",
        *[f"market_next_{outcome}_p" for outcome in OUTCOMES],
        *baseline,
    }
    residual = [column for column in output.columns if column not in excluded]
    augmented = baseline + residual
    return output, baseline, augmented


def aligned_probabilities(model: Any, features: pd.DataFrame) -> np.ndarray:
    raw = model.predict_proba(features)
    classes = model.named_steps["logisticregression"].classes_.astype(int)
    output = np.full((len(features), 3), 1e-12, dtype=np.float64)
    for column_index, class_value in enumerate(classes):
        output[:, class_value] = raw[:, column_index]
    output /= output.sum(axis=1, keepdims=True)
    return output


def one_hot(y: np.ndarray) -> np.ndarray:
    result = np.zeros((len(y), 3), dtype=np.float64)
    result[np.arange(len(y)), y.astype(int)] = 1.0
    return result


def metric_summary(y: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    p = np.clip(probabilities.astype(np.float64), 1e-12, 1.0)
    p /= p.sum(axis=1, keepdims=True)
    loss = -np.log(p[np.arange(len(y)), y.astype(int)])
    brier_rows = np.sum((one_hot(y) - p) ** 2, axis=1)
    prediction = np.argmax(p, axis=1)
    return {
        "rows": int(len(y)),
        "log_loss": float(loss.mean()),
        "multiclass_brier": float(brier_rows.mean()),
        "accuracy": float((prediction == y).mean()),
        "mean_predicted": {str(index): float(p[:, index].mean()) for index in range(3)},
        "observed_frequency": {str(index): float((y == index).mean()) for index in range(3)},
    }


def per_cutoff_metrics(frame: pd.DataFrame, probabilities: np.ndarray) -> dict[str, Any]:
    output = {}
    y = frame["outcome_class"].to_numpy(dtype=np.int8)
    for hours in CUTOFFS:
        mask = frame["hours_before_kickoff"].to_numpy(dtype=int) == hours
        if not mask.any():
            output[f"T-{hours}h"] = {"rows": 0, "available": False}
            continue
        output[f"T-{hours}h"] = {"available": True, **metric_summary(y[mask], probabilities[mask])}
    return output


def bootstrap_log_loss_improvement(
    frame: pd.DataFrame,
    baseline_probabilities: np.ndarray,
    augmented_probabilities: np.ndarray,
    *,
    replicates: int = 1000,
) -> dict[str, Any]:
    y = frame["outcome_class"].to_numpy(dtype=np.int8)
    base = np.clip(baseline_probabilities, 1e-12, 1.0)
    aug = np.clip(augmented_probabilities, 1e-12, 1.0)
    row_improvement = -np.log(base[np.arange(len(y)), y]) + np.log(aug[np.arange(len(y)), y])
    temp = pd.DataFrame({"match_id": frame["match_id"].astype(str).to_numpy(), "improvement": row_improvement})
    grouped = temp.groupby("match_id", sort=False)["improvement"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(dtype=np.float64)
    counts = grouped["count"].to_numpy(dtype=np.int64)
    rng = np.random.default_rng(RANDOM_SEED)
    draws = np.empty(replicates, dtype=np.float64)
    for index in range(replicates):
        sample = rng.integers(0, len(sums), size=len(sums))
        draws[index] = sums[sample].sum() / counts[sample].sum()
    low, high = np.quantile(draws, [0.025, 0.975])
    return {
        "matches": int(len(sums)),
        "replicates": replicates,
        "mean_improvement": float(sums.sum() / counts.sum()),
        "ci95_low": float(low),
        "ci95_high": float(high),
    }


def coefficient_summary(model: Any, columns: list[str], *, top_n: int = 25) -> list[dict[str, Any]]:
    coefficients = model.named_steps["logisticregression"].coef_
    norms = np.linalg.norm(coefficients, axis=0)
    order = np.argsort(norms)[::-1][:top_n]
    return [
        {
            "feature": columns[int(index)],
            "coefficient_l2_across_classes": float(norms[int(index)]),
            "class_coefficients": [float(value) for value in coefficients[:, int(index)]],
        }
        for index in order
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Test incremental outcome information in frozen abnormal-action residuals.")
    parser.add_argument("--residual-root", default="artifacts/abnormal-action-residuals")
    parser.add_argument("--output-root", default="artifacts/experiment-005")
    args = parser.parse_args()

    residual_root = Path(args.residual_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    validation, validation_profile = aggregate_residual_file(residual_root / "residuals_validation.csv.gz")
    test, test_profile = aggregate_residual_file(residual_root / "residuals_test.csv.gz")
    outcomes, outcome_profile = load_outcomes(residual_root / "extracted")

    validation = validation.merge(outcomes, on="match_id", how="inner", validate="many_to_one")
    test = test.merge(outcomes, on="match_id", how="inner", validate="many_to_one")
    if validation.empty or test.empty:
        raise RuntimeError("outcome join produced an empty validation or test set")

    validation, baseline_columns, augmented_columns = add_model_features(validation)
    test, baseline_columns_test, augmented_columns_test = add_model_features(test)
    if baseline_columns != baseline_columns_test or augmented_columns != augmented_columns_test:
        raise RuntimeError("validation/test feature schemas differ")
    if len(set(augmented_columns)) != len(augmented_columns):
        raise RuntimeError("duplicate augmented feature names")

    for frame_name, frame in (("validation", validation), ("test", test)):
        missing_classes = sorted(set(CLASSES.tolist()) - set(frame["outcome_class"].unique().tolist()))
        if missing_classes:
            raise RuntimeError(f"{frame_name} missing outcome classes: {missing_classes}")
        values = frame[augmented_columns].to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            bad = np.asarray(augmented_columns)[~np.isfinite(values).all(axis=0)].tolist()
            raise ValueError(f"non-finite {frame_name} model features: {bad}")

    baseline_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, random_state=RANDOM_SEED),
    )
    augmented_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, random_state=RANDOM_SEED),
    )
    baseline_model.fit(validation[baseline_columns], validation["outcome_class"])
    augmented_model.fit(validation[augmented_columns], validation["outcome_class"])

    direct_market = test[[f"market_next_{outcome}_p" for outcome in OUTCOMES]].to_numpy(dtype=np.float64, copy=True)
    direct_market /= direct_market.sum(axis=1, keepdims=True)
    fitted_baseline = aligned_probabilities(baseline_model, test[baseline_columns])
    augmented = aligned_probabilities(augmented_model, test[augmented_columns])
    y_test = test["outcome_class"].to_numpy(dtype=np.int8)

    direct_metrics = metric_summary(y_test, direct_market)
    baseline_metrics = metric_summary(y_test, fitted_baseline)
    augmented_metrics = metric_summary(y_test, augmented)
    direct_by_cutoff = per_cutoff_metrics(test, direct_market)
    baseline_by_cutoff = per_cutoff_metrics(test, fitted_baseline)
    augmented_by_cutoff = per_cutoff_metrics(test, augmented)

    cutoff_improvements = {}
    improved_cutoffs = 0
    for hours in CUTOFFS:
        key = f"T-{hours}h"
        if not baseline_by_cutoff[key].get("available"):
            cutoff_improvements[key] = {"available": False}
            continue
        improvement = baseline_by_cutoff[key]["log_loss"] - augmented_by_cutoff[key]["log_loss"]
        cutoff_improvements[key] = {
            "available": True,
            "fitted_baseline_log_loss": baseline_by_cutoff[key]["log_loss"],
            "augmented_log_loss": augmented_by_cutoff[key]["log_loss"],
            "log_loss_improvement": float(improvement),
        }
        if improvement > 0:
            improved_cutoffs += 1

    bootstrap = bootstrap_log_loss_improvement(test, fitted_baseline, augmented, replicates=1000)
    checks = {
        "augmented_beats_fitted_market_log_loss": augmented_metrics["log_loss"] < baseline_metrics["log_loss"],
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "augmented_beats_fitted_market_brier": augmented_metrics["multiclass_brier"] < baseline_metrics["multiclass_brier"],
        "improves_at_least_4_of_6_cutoffs": improved_cutoffs >= 4,
        "augmented_beats_direct_market_log_loss": augmented_metrics["log_loss"] < direct_metrics["log_loss"],
    }

    report = {
        "experiment": "005_frozen_residual_incremental_outcome_information",
        "status": "completed",
        "timing_rule": "Residual T-h is observed after t->t+1; market comparator uses reconstructed t+1 target-book probabilities.",
        "profiles": {
            "validation_residuals": validation_profile,
            "test_residuals": test_profile,
            "outcomes": outcome_profile,
            "joined_validation_rows": int(len(validation)),
            "joined_validation_matches": int(validation["match_id"].nunique()),
            "joined_test_rows": int(len(test)),
            "joined_test_matches": int(test["match_id"].nunique()),
        },
        "feature_schema": {
            "baseline_features": baseline_columns,
            "residual_features": [column for column in augmented_columns if column not in baseline_columns],
            "augmented_feature_count": len(augmented_columns),
        },
        "locked_test": {
            "direct_t_plus_1_market": direct_metrics,
            "fitted_market_only": baseline_metrics,
            "augmented_residual": augmented_metrics,
            "fitted_baseline_minus_augmented_log_loss": float(baseline_metrics["log_loss"] - augmented_metrics["log_loss"]),
            "direct_market_minus_augmented_log_loss": float(direct_metrics["log_loss"] - augmented_metrics["log_loss"]),
            "fitted_baseline_minus_augmented_brier": float(baseline_metrics["multiclass_brier"] - augmented_metrics["multiclass_brier"]),
            "paired_match_bootstrap": bootstrap,
            "cutoff_improvements": cutoff_improvements,
            "improved_cutoffs": improved_cutoffs,
            "direct_market_by_cutoff": direct_by_cutoff,
            "fitted_market_by_cutoff": baseline_by_cutoff,
            "augmented_by_cutoff": augmented_by_cutoff,
        },
        "promotion_checks": checks,
        "residual_outcome_information_promoted": all(checks.values()),
        "augmented_top_coefficient_norms": coefficient_summary(augmented_model, augmented_columns),
    }
    (output_root / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
