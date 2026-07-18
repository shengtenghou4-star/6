from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

import experiment_006_independent_residual_outcome as exp6
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import (
    BOOKMAKER_NAMES,
    CUTOFFS,
    DOWNLOAD_URL,
    OUTCOMES,
    SELECTED_BOOKS,
    SERIES_FILES,
    download,
    extract_required,
    raw_and_devig,
)


SIGNAL_HOURS = (48, 24, 12, 6)
RANDOM_SEED = 20260718
TRADE_FRACTION = 0.20
RESIDUAL_COLUMNS = [
    "move_surprise_signed", "no_move_surprise", "unexpected_move_surprise",
    "conditional_residual_home", "conditional_residual_draw", "conditional_residual_away",
    "conditional_residual_l2",
    "action_residual_home", "action_residual_draw", "action_residual_away",
    "action_residual_l2",
    "prior_residual_cutoffs", "prior_move_surprise_mean", "prior_abs_move_surprise_mean",
    "prior_action_residual_l2_mean", "prior_abnormality_mean",
    "prior_action_residual_home_sum", "prior_action_residual_draw_sum", "prior_action_residual_away_sum",
]
TARGET_DELTA_COLUMNS = ["future_delta_home", "future_delta_draw", "future_delta_away"]


def x_frame(data: dict[str, Any]) -> tuple[pd.DataFrame, list[str]]:
    columns = [f"raw_x_{index}" for index in range(data["X"].shape[1])]
    frame = pd.DataFrame(data["X"], columns=columns)
    frame.insert(0, "hours_before_kickoff", data["hours"].astype(int))
    frame.insert(0, "book_slot", [f"b{int(book)}" for book in data["book"]])
    frame.insert(0, "match_id", data["match_id"].astype(str))
    if frame.duplicated(["match_id", "book_slot", "hours_before_kickoff"]).any():
        raise RuntimeError("duplicate X keys")
    return frame, columns


def wanted_sets(residual_frames: list[pd.DataFrame]) -> dict[tuple[int, int], set[str]]:
    output: dict[tuple[int, int], set[str]] = {}
    combined = pd.concat(
        [
            frame.loc[frame["hours_before_kickoff"].isin(SIGNAL_HOURS), ["match_id", "book_slot", "hours_before_kickoff"]]
            for frame in residual_frames
        ],
        ignore_index=True,
    )
    combined["match_id"] = combined["match_id"].astype(str)
    combined["book"] = combined["book_slot"].str.removeprefix("b").astype(int)
    for (hours, book), group in combined.groupby(["hours_before_kickoff", "book"], sort=False):
        output[(int(hours), int(book))] = set(group["match_id"].tolist())
    return output


def build_future_prices(
    paths: list[Path],
    residual_frames: list[pd.DataFrame],
    *,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    wanted = wanted_sets(residual_frames)
    needed_indices = sorted({CUTOFFS[hours] + offset for hours in SIGNAL_HOURS for offset in (1, 4)})
    usecols = ["match_id"] + [
        f"{outcome}_b{book}_{index}"
        for book in SELECTED_BOOKS
        for outcome in OUTCOMES
        for index in needed_indices
    ]
    parts: list[pd.DataFrame] = []
    for path in paths:
        for frame in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
            match_ids = frame["match_id"].astype(str).to_numpy()
            cache = {index: raw_and_devig(frame, SELECTED_BOOKS, index) for index in needed_indices}
            for hours in SIGNAL_HOURS:
                observation_index = CUTOFFS[hours] + 1
                future_index = CUTOFFS[hours] + 4
                raw_observation, p_observation, over_observation, complete_observation = cache[observation_index]
                raw_future, p_future, _over_future, complete_future = cache[future_index]
                for book_position, book in enumerate(SELECTED_BOOKS):
                    requested = wanted[(hours, book)]
                    requested_mask = np.fromiter((match_id in requested for match_id in match_ids), dtype=bool, count=len(match_ids))
                    eligible = requested_mask & complete_observation[:, book_position] & complete_future[:, book_position]
                    if not eligible.any():
                        continue
                    observation_p = p_observation[eligible, book_position, :]
                    future_p = p_future[eligible, book_position, :]
                    observation_raw = raw_observation[eligible, book_position, :]
                    future_raw = raw_future[eligible, book_position, :]
                    delta = future_p - observation_p
                    moved = np.any(np.abs(future_raw - observation_raw) > 1e-12, axis=1)
                    part = pd.DataFrame(
                        {
                            "match_id": match_ids[eligible],
                            "book_slot": f"b{book}",
                            "hours_before_kickoff": hours,
                            "future_move": moved.astype(np.int8),
                            "observation_overround": over_observation[eligible, book_position],
                        }
                    )
                    for outcome_index, outcome in enumerate(OUTCOMES):
                        part[f"observation_p_{outcome}"] = observation_p[:, outcome_index]
                        part[f"future_p_{outcome}"] = future_p[:, outcome_index]
                        part[f"future_delta_{outcome}"] = delta[:, outcome_index]
                        part[f"observation_raw_{outcome}"] = observation_raw[:, outcome_index]
                        part[f"future_raw_{outcome}"] = future_raw[:, outcome_index]
                    parts.append(part)
    if not parts:
        raise RuntimeError("no future price records")
    output = pd.concat(parts, ignore_index=True)
    keys = ["match_id", "book_slot", "hours_before_kickoff"]
    if output.duplicated(keys).any():
        raise RuntimeError("duplicate future price keys")
    profile = {
        "rows": int(len(output)),
        "matches": int(output["match_id"].nunique()),
        "move_rate": float(output["future_move"].mean()),
        "rows_by_book": {str(k): int(v) for k, v in output["book_slot"].value_counts().sort_index().items()},
        "rows_by_cutoff": {str(int(k)): int(v) for k, v in output["hours_before_kickoff"].value_counts().sort_index().items()},
    }
    return output, profile


def model_frame(
    residual: pd.DataFrame,
    x: pd.DataFrame,
    future: pd.DataFrame,
    raw_x_columns: list[str],
) -> tuple[pd.DataFrame, list[str], list[str]]:
    keys = ["match_id", "book_slot", "hours_before_kickoff"]
    signal = residual[residual["hours_before_kickoff"].isin(SIGNAL_HOURS)].copy()
    signal["match_id"] = signal["match_id"].astype(str)
    joined = signal.merge(x, on=keys, how="inner", validate="one_to_one")
    joined = joined.merge(future, on=keys, how="inner", validate="one_to_one")
    if joined.empty:
        raise RuntimeError("empty residual/X/future join")
    for outcome in OUTCOMES:
        reconstructed = joined[f"target_current_{outcome}_p"] + joined[f"actual_delta_{outcome}"]
        error = np.max(np.abs(reconstructed.to_numpy(dtype=float) - joined[f"observation_p_{outcome}"].to_numpy(dtype=float)))
        if error > 1e-5:
            raise ValueError(f"observation probability mismatch for {outcome}: {error}")
    joined["move_surprise_abs"] = joined["move_surprise_signed"].abs()
    for column in RESIDUAL_COLUMNS:
        if column not in joined.columns:
            raise ValueError(f"missing residual feature: {column}")
        joined[column] = pd.to_numeric(joined[column], errors="coerce").fillna(0.0)
    baseline_columns = [
        *raw_x_columns,
        "actual_move",
        "actual_delta_home", "actual_delta_draw", "actual_delta_away",
        "observation_p_home", "observation_p_draw", "observation_p_away",
        "observation_overround",
    ]
    augmented_columns = baseline_columns + ["move_surprise_abs", *RESIDUAL_COLUMNS]
    for name, columns in (("baseline", baseline_columns), ("augmented", augmented_columns)):
        values = joined[columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            bad = np.asarray(columns)[~np.isfinite(values).all(axis=0)].tolist()
            raise ValueError(f"non-finite {name} features: {bad}")
    return joined, baseline_columns, augmented_columns


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


def repricing_evaluation(
    test: pd.DataFrame,
    baseline_probability: np.ndarray,
    augmented_probability: np.ndarray,
    baseline_delta: np.ndarray,
    augmented_delta: np.ndarray,
) -> tuple[dict[str, Any], dict[str, Any]]:
    y = test["future_move"].to_numpy(dtype=float)
    baseline_error = (y - baseline_probability) ** 2
    augmented_error = (y - augmented_probability) ** 2
    hazard_bootstrap = exp6.bootstrap_match_improvement(
        test["match_id"].to_numpy(), baseline_error - augmented_error, replicates=1000
    )
    hazard_by_cutoff: dict[str, Any] = {}
    hazard_improved = 0
    for hours in SIGNAL_HOURS:
        mask = test["hours_before_kickoff"].to_numpy(dtype=int) == hours
        baseline_brier = float(baseline_error[mask].mean())
        augmented_brier = float(augmented_error[mask].mean())
        improvement = baseline_brier - augmented_brier
        hazard_by_cutoff[f"T-{hours}h"] = {
            "rows": int(mask.sum()),
            "baseline_brier": baseline_brier,
            "augmented_brier": augmented_brier,
            "improvement": float(improvement),
        }
        hazard_improved += int(improvement > 0)
    baseline_brier = float(baseline_error.mean())
    augmented_brier = float(augmented_error.mean())
    hazard_checks = {
        "augmented_brier_lower": augmented_brier < baseline_brier,
        "bootstrap_ci_above_zero": hazard_bootstrap["ci95_low"] > 0.0,
        "improves_at_least_3_of_4_cutoffs": hazard_improved >= 3,
    }
    hazard = {
        "baseline_brier": baseline_brier,
        "augmented_brier": augmented_brier,
        "improvement": float(baseline_brier - augmented_brier),
        "relative_improvement": float((baseline_brier - augmented_brier) / baseline_brier),
        "paired_match_bootstrap": hazard_bootstrap,
        "by_cutoff": hazard_by_cutoff,
        "improved_cutoffs": hazard_improved,
        "checks": hazard_checks,
        "promoted": all(hazard_checks.values()),
    }

    movers = test["future_move"].to_numpy(dtype=int) == 1
    mover_frame = test.loc[movers].copy()
    actual = mover_frame[TARGET_DELTA_COLUMNS].to_numpy(dtype=float)
    baseline_row_mae = np.mean(np.abs(actual - baseline_delta[movers]), axis=1)
    augmented_row_mae = np.mean(np.abs(actual - augmented_delta[movers]), axis=1)
    conditional_bootstrap = exp6.bootstrap_match_improvement(
        mover_frame["match_id"].to_numpy(), baseline_row_mae - augmented_row_mae, replicates=1000
    )
    conditional_by_cutoff: dict[str, Any] = {}
    conditional_improved = 0
    for hours in SIGNAL_HOURS:
        mask = mover_frame["hours_before_kickoff"].to_numpy(dtype=int) == hours
        baseline_mae = float(baseline_row_mae[mask].mean())
        augmented_mae = float(augmented_row_mae[mask].mean())
        improvement = baseline_mae - augmented_mae
        conditional_by_cutoff[f"T-{hours}h"] = {
            "mover_rows": int(mask.sum()),
            "baseline_mae": baseline_mae,
            "augmented_mae": augmented_mae,
            "improvement": float(improvement),
        }
        conditional_improved += int(improvement > 0)
    baseline_mae = float(baseline_row_mae.mean())
    augmented_mae = float(augmented_row_mae.mean())
    conditional_checks = {
        "augmented_mae_lower": augmented_mae < baseline_mae,
        "bootstrap_ci_above_zero": conditional_bootstrap["ci95_low"] > 0.0,
        "improves_at_least_3_of_4_cutoffs": conditional_improved >= 3,
    }
    conditional = {
        "mover_rows": int(movers.sum()),
        "mover_matches": int(mover_frame["match_id"].nunique()),
        "baseline_mae": baseline_mae,
        "augmented_mae": augmented_mae,
        "improvement": float(baseline_mae - augmented_mae),
        "relative_improvement": float((baseline_mae - augmented_mae) / baseline_mae),
        "paired_match_bootstrap": conditional_bootstrap,
        "by_cutoff": conditional_by_cutoff,
        "improved_cutoffs": conditional_improved,
        "checks": conditional_checks,
        "promoted": all(conditional_checks.values()),
    }
    return hazard, conditional


def strategy_candidates(frame: pd.DataFrame, expected_delta: np.ndarray, name: str) -> pd.DataFrame:
    outcome_index = np.argmax(expected_delta, axis=1)
    confidence = expected_delta[np.arange(len(frame)), outcome_index]
    raw_observation = frame[[f"observation_raw_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    raw_future = frame[[f"future_raw_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    p_observation = frame[[f"observation_p_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    p_future = frame[[f"future_p_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    selected_observation_raw = raw_observation[np.arange(len(frame)), outcome_index]
    selected_future_raw = raw_future[np.arange(len(frame)), outcome_index]
    selected_observation_p = p_observation[np.arange(len(frame)), outcome_index]
    selected_future_p = p_future[np.arange(len(frame)), outcome_index]
    candidates = pd.DataFrame(
        {
            "match_id": frame["match_id"].astype(str).to_numpy(),
            "hours_before_kickoff": frame["hours_before_kickoff"].to_numpy(dtype=int),
            "book_slot": frame["book_slot"].astype(str).to_numpy(),
            "bookmaker_name": frame["bookmaker_name"].astype(str).to_numpy(),
            "selected_outcome_index": outcome_index,
            "selected_outcome": np.asarray(OUTCOMES, dtype=object)[outcome_index],
            "confidence": confidence,
            "log_odds_clv": np.log(selected_observation_raw / selected_future_raw),
            "fair_probability_clv": selected_future_p - selected_observation_p,
        }
    )
    candidates.sort_values(
        ["match_id", "hours_before_kickoff", "confidence", "book_slot", "selected_outcome_index"],
        ascending=[True, True, False, True, True],
        kind="mergesort",
        inplace=True,
    )
    best = candidates.groupby(["match_id", "hours_before_kickoff"], sort=False, as_index=False).first()
    best["strategy"] = name
    best["traded"] = False
    for hours in SIGNAL_HOURS:
        indices = best.index[best["hours_before_kickoff"] == hours].tolist()
        ordered = best.loc[indices].sort_values(
            ["confidence", "match_id", "book_slot", "selected_outcome_index"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        trade_count = max(1, int(np.floor(len(ordered) * TRADE_FRACTION)))
        best.loc[ordered.index[:trade_count], "traded"] = True
    best["opportunity_log_clv"] = np.where(best["traded"], best["log_odds_clv"], 0.0)
    best["opportunity_probability_clv"] = np.where(best["traded"], best["fair_probability_clv"], 0.0)
    return best


def strategy_metrics(strategy: pd.DataFrame) -> dict[str, Any]:
    trades = strategy[strategy["traded"]].copy()
    if trades.empty:
        raise RuntimeError("strategy produced no trades")
    positive_bootstrap = exp6.bootstrap_match_improvement(
        trades["match_id"].to_numpy(), trades["log_odds_clv"].to_numpy(dtype=float), replicates=1000
    )
    by_cutoff: dict[str, Any] = {}
    positive_cutoffs = 0
    for hours in SIGNAL_HOURS:
        group = trades[trades["hours_before_kickoff"] == hours]
        mean_log = float(group["log_odds_clv"].mean())
        by_cutoff[f"T-{hours}h"] = {
            "trades": int(len(group)),
            "mean_log_odds_clv": mean_log,
            "mean_fair_probability_clv": float(group["fair_probability_clv"].mean()),
        }
        positive_cutoffs += int(mean_log > 0)
    return {
        "opportunities": int(len(strategy)),
        "matches": int(strategy["match_id"].nunique()),
        "trades": int(len(trades)),
        "trade_fraction": float(len(trades) / len(strategy)),
        "mean_trade_log_odds_clv": float(trades["log_odds_clv"].mean()),
        "mean_trade_fair_probability_clv": float(trades["fair_probability_clv"].mean()),
        "mean_opportunity_log_clv": float(strategy["opportunity_log_clv"].mean()),
        "mean_opportunity_probability_clv": float(strategy["opportunity_probability_clv"].mean()),
        "positive_trade_log_clv_bootstrap": positive_bootstrap,
        "by_cutoff": by_cutoff,
        "positive_cutoffs": positive_cutoffs,
    }


def compare_strategies(baseline: pd.DataFrame, augmented: pd.DataFrame) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    joined = baseline[keys + ["opportunity_log_clv"]].merge(
        augmented[keys + ["opportunity_log_clv"]],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_augmented"),
    )
    improvement = (
        joined["opportunity_log_clv_augmented"].to_numpy(dtype=float)
        - joined["opportunity_log_clv_baseline"].to_numpy(dtype=float)
    )
    bootstrap = exp6.bootstrap_match_improvement(joined["match_id"].to_numpy(), improvement, replicates=1000)
    return {
        "opportunities": int(len(joined)),
        "mean_augmented_minus_baseline_opportunity_log_clv": float(improvement.mean()),
        "paired_match_bootstrap": bootstrap,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen named-book residual repricing and CLV proxy experiment.")
    parser.add_argument("--output-root", default="artifacts/experiment-008")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress_path = root / "progress.json"
    failure_path = root / "failure.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True), encoding="utf-8")

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)

        progress("building_normal_state_records")
        datasets = residual_gen.build_all_state_records([paths[name] for name in SERIES_FILES], chunksize=args.chunksize)
        diagnostics = datasets.pop("diagnostics")
        progress("training_frozen_normal_models")
        hazard, movement_models, training_counts = residual_gen.train_frozen_models(
            datasets["train"], hazard_max=args.hazard_max_train, movement_max=args.movement_max_train
        )

        residual_frames: dict[str, pd.DataFrame] = {}
        x_frames: dict[str, pd.DataFrame] = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            residual_frames[split] = residual_gen.build_residual_frame(split, datasets[split], hazard, movement_models)
            x_frames[split], columns = x_frame(datasets[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif raw_x_columns != columns:
                raise RuntimeError("validation/test raw X schemas differ")
        assert raw_x_columns is not None

        progress("extracting_future_named_book_prices")
        future, future_profile = build_future_prices(
            [paths[name] for name in SERIES_FILES],
            [residual_frames["validation"], residual_frames["test"]],
            chunksize=args.chunksize,
        )
        validation, baseline_columns, augmented_columns = model_frame(
            residual_frames["validation"], x_frames["validation"], future, raw_x_columns
        )
        test, baseline_test, augmented_test = model_frame(
            residual_frames["test"], x_frames["test"], future, raw_x_columns
        )
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test model schemas differ")

        progress("training_repricing_models", validation_rows=int(len(validation)), test_rows=int(len(test)))
        baseline_hazard = fixed_classifier()
        augmented_hazard = fixed_classifier()
        baseline_hazard.fit(validation[baseline_columns], validation["future_move"])
        augmented_hazard.fit(validation[augmented_columns], validation["future_move"])
        baseline_probability = baseline_hazard.predict_proba(test[baseline_columns])[:, 1]
        augmented_probability = augmented_hazard.predict_proba(test[augmented_columns])[:, 1]

        validation_movers = validation[validation["future_move"] == 1].copy()
        if validation_movers.empty:
            raise RuntimeError("no validation future movers")
        baseline_delta = np.empty((len(test), 3), dtype=float)
        augmented_delta = np.empty((len(test), 3), dtype=float)
        for outcome_index, target in enumerate(TARGET_DELTA_COLUMNS):
            baseline_model = fixed_regressor()
            augmented_model = fixed_regressor()
            baseline_model.fit(validation_movers[baseline_columns], validation_movers[target])
            augmented_model.fit(validation_movers[augmented_columns], validation_movers[target])
            baseline_delta[:, outcome_index] = baseline_model.predict(test[baseline_columns])
            augmented_delta[:, outcome_index] = augmented_model.predict(test[augmented_columns])

        hazard_result, conditional_result = repricing_evaluation(
            test,
            baseline_probability,
            augmented_probability,
            baseline_delta,
            augmented_delta,
        )

        progress("evaluating_frozen_clv_strategy")
        baseline_expected_delta = baseline_probability[:, None] * baseline_delta
        augmented_expected_delta = augmented_probability[:, None] * augmented_delta
        baseline_strategy = strategy_candidates(test, baseline_expected_delta, "baseline")
        augmented_strategy = strategy_candidates(test, augmented_expected_delta, "augmented")
        baseline_strategy_metrics = strategy_metrics(baseline_strategy)
        augmented_strategy_metrics = strategy_metrics(augmented_strategy)
        strategy_comparison = compare_strategies(baseline_strategy, augmented_strategy)

        repricing_pass = bool(hazard_result["promoted"] and conditional_result["promoted"])
        promotion_checks = {
            "repricing_hazard_promoted": hazard_result["promoted"],
            "conditional_repricing_promoted": conditional_result["promoted"],
            "augmented_trade_log_clv_positive_ci": augmented_strategy_metrics["positive_trade_log_clv_bootstrap"]["ci95_low"] > 0.0,
            "augmented_beats_baseline_opportunity_clv_ci": strategy_comparison["paired_match_bootstrap"]["ci95_low"] > 0.0,
            "augmented_fair_probability_clv_positive": augmented_strategy_metrics["mean_trade_fair_probability_clv"] > 0.0,
            "augmented_positive_at_least_3_of_4_cutoffs": augmented_strategy_metrics["positive_cutoffs"] >= 3,
        }
        report = {
            "experiment": "008_named_book_residual_repricing_clv_proxy",
            "status": "completed",
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "future_price_profile": future_profile,
            "validation_rows": int(len(validation)),
            "validation_matches": int(validation["match_id"].nunique()),
            "test_rows": int(len(test)),
            "test_matches": int(test["match_id"].nunique()),
            "frozen_books": {f"b{book}": BOOKMAKER_NAMES[book] for book in SELECTED_BOOKS},
            "trade_fraction": TRADE_FRACTION,
            "repricing_hazard": hazard_result,
            "conditional_repricing": conditional_result,
            "baseline_strategy": baseline_strategy_metrics,
            "augmented_strategy": augmented_strategy_metrics,
            "strategy_comparison": strategy_comparison,
            "promotion_checks": promotion_checks,
            "named_book_clv_proxy_promoted": all(promotion_checks.values()),
            "repricing_pass": repricing_pass,
        }
        (root / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        baseline_strategy.to_csv(root / "baseline_strategy.csv.gz", index=False, compression="gzip")
        augmented_strategy.to_csv(root / "augmented_strategy.csv.gz", index=False, compression="gzip")
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
