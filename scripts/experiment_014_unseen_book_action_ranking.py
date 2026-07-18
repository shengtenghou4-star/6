from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_008_named_book_clv as exp8
import experiment_011_closing_line_residual as exp11
import experiment_013_selection_ranking_decomposition as exp13
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import (
    BOOKMAKER_NAMES,
    DOWNLOAD_URL,
    SELECTED_BOOKS,
    SERIES_FILES,
    download,
    extract_required,
)


SIGNAL_HOURS = exp11.SIGNAL_HOURS
BOOK_ONEHOT_WIDTH = len(SELECTED_BOOKS)
ACTION_COLUMNS = [
    "conditional_residual_home",
    "conditional_residual_draw",
    "conditional_residual_away",
    "conditional_residual_l2",
    "action_residual_home",
    "action_residual_draw",
    "action_residual_away",
    "action_residual_l2",
]


def generic_data(data: dict[str, Any], mask: np.ndarray | None = None) -> dict[str, Any]:
    if data["X"].shape[1] <= BOOK_ONEHOT_WIDTH:
        raise ValueError("normal-model X does not contain the frozen bookmaker one-hot tail")
    if mask is None:
        mask = np.ones(len(data["X"]), dtype=bool)
    output: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, np.ndarray) and len(value) == len(mask):
            output[key] = value[mask]
        else:
            output[key] = value
    output["X"] = data["X"][mask, :-BOOK_ONEHOT_WIDTH]
    return output


def key_frame(data: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": data["match_id"].astype(str),
            "book_slot": [f"b{int(book)}" for book in data["book"]],
            "hours_before_kickoff": data["hours"].astype(int),
        }
    )


def fit_closing_models(
    validation: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    hazard = exp8.fixed_classifier()
    hazard.fit(validation[columns], validation["future_move"])
    probability = hazard.predict_proba(test[columns])[:, 1]
    validation_movers = validation[validation["future_move"] == 1]
    if validation_movers.empty:
        raise RuntimeError("no validation closing movers in leave-one-book-out fold")
    delta = np.empty((len(test), 3), dtype=float)
    for outcome_index, target in enumerate(exp8.TARGET_DELTA_COLUMNS):
        model = exp8.fixed_regressor()
        model.fit(validation_movers[columns], validation_movers[target])
        delta[:, outcome_index] = model.predict(test[columns])
    return probability, delta


def cutoff_incremental_clv(
    baseline: pd.DataFrame,
    variant: pd.DataFrame,
) -> tuple[dict[str, Any], int]:
    keys = ["match_id", "hours_before_kickoff"]
    joined = baseline[keys + ["opportunity_log_clv"]].merge(
        variant[keys + ["opportunity_log_clv"]],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_variant"),
    )
    joined["improvement"] = (
        joined["opportunity_log_clv_variant"]
        - joined["opportunity_log_clv_baseline"]
    )
    output: dict[str, Any] = {}
    positive = 0
    for hours in SIGNAL_HOURS:
        group = joined[joined["hours_before_kickoff"] == hours]
        value = float(group["improvement"].mean())
        output[f"T-{hours}h"] = {
            "opportunities": int(len(group)),
            "mean_incremental_opportunity_log_clv": value,
        }
        positive += int(value > 0.0)
    return output, positive


def bookmaker_concentration(
    baseline: pd.DataFrame,
    ranker: pd.DataFrame,
) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    joined = baseline[keys + ["book_slot", "opportunity_log_clv"]].merge(
        ranker[keys + ["book_slot", "opportunity_log_clv"]],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_ranker"),
    )
    if not (joined["book_slot_baseline"] == joined["book_slot_ranker"]).all():
        raise RuntimeError("rank-only strategy changed candidate bookmaker identity")
    joined["incremental_opportunity_log_clv"] = (
        joined["opportunity_log_clv_ranker"]
        - joined["opportunity_log_clv_baseline"]
    )
    grouped = joined.groupby("book_slot_baseline", sort=True)[
        "incremental_opportunity_log_clv"
    ].agg(["sum", "mean", "count"])
    positive_mass = grouped["sum"].clip(lower=0.0)
    total_positive = float(positive_mass.sum())
    max_share = float(positive_mass.max() / total_positive) if total_positive > 0 else 1.0
    return {
        "by_book": {
            str(book): {
                "opportunities": int(row["count"]),
                "sum_incremental_opportunity_log_clv": float(row["sum"]),
                "mean_incremental_opportunity_log_clv": float(row["mean"]),
                "positive_contribution_share": float(positive_mass.loc[book] / total_positive)
                if total_positive > 0
                else 0.0,
            }
            for book, row in grouped.iterrows()
        },
        "total_positive_contribution": total_positive,
        "largest_positive_contribution_share": max_share,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run leave-one-book-out action-residual closing-line transfer audit."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-014")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=250000)
    parser.add_argument("--movement-max-train", type=int, default=180000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress_path = root / "progress.json"
    failure_path = root / "failure.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(
            json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("building_normal_state_records")
        datasets = residual_gen.build_all_state_records(
            source_paths,
            chunksize=args.chunksize,
        )
        diagnostics = datasets.pop("diagnostics")
        generic = {
            split: generic_data(datasets[split])
            for split in ("train", "validation", "test")
        }
        x_frames: dict[str, pd.DataFrame] = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            x_frames[split], columns = exp8.x_frame(generic[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif columns != raw_x_columns:
                raise RuntimeError("generic validation/test X schemas differ")
        assert raw_x_columns is not None

        progress("extracting_same_book_closing_prices")
        closing_prices, closing_profile = exp11.build_closing_prices(
            source_paths,
            [key_frame(generic["validation"]), key_frame(generic["test"])],
            chunksize=args.chunksize,
        )

        fold_predictions: list[pd.DataFrame] = []
        fold_profiles: dict[str, Any] = {}
        for fold_index, heldout in enumerate(SELECTED_BOOKS, start=1):
            heldout_slot = f"b{heldout}"
            progress(
                "leave_one_book_out_fold",
                fold=fold_index,
                folds=len(SELECTED_BOOKS),
                heldout_book=heldout_slot,
            )
            train_mask = datasets["train"]["book"] != heldout
            normal_train = generic_data(datasets["train"], train_mask)
            normal_hazard, normal_movement, training_counts = residual_gen.train_frozen_models(
                normal_train,
                hazard_max=args.hazard_max_train,
                movement_max=args.movement_max_train,
            )
            residual_frames = {
                split: residual_gen.build_residual_frame(
                    split,
                    generic[split],
                    normal_hazard,
                    normal_movement,
                )
                for split in ("validation", "test")
            }
            validation, baseline_columns, _ = exp8.model_frame(
                residual_frames["validation"],
                x_frames["validation"],
                closing_prices,
                raw_x_columns,
            )
            test, baseline_test, _ = exp8.model_frame(
                residual_frames["test"],
                x_frames["test"],
                closing_prices,
                raw_x_columns,
            )
            if baseline_columns != baseline_test:
                raise RuntimeError("generic validation/test closing schemas differ")
            action_columns = baseline_columns + ACTION_COLUMNS
            for column in ACTION_COLUMNS:
                if column not in validation.columns or column not in test.columns:
                    raise ValueError(f"missing action residual column: {column}")
            training = validation[validation["book_slot"] != heldout_slot].copy()
            heldout_test = test[test["book_slot"] == heldout_slot].copy()
            if training.empty or heldout_test.empty:
                raise RuntimeError(f"empty transfer fold for {heldout_slot}")

            baseline_probability, baseline_delta = fit_closing_models(
                training,
                heldout_test,
                baseline_columns,
            )
            action_probability, action_delta = fit_closing_models(
                training,
                heldout_test,
                action_columns,
            )
            heldout_test["fold_heldout_book"] = heldout_slot
            heldout_test["baseline_probability"] = baseline_probability
            heldout_test["action_probability"] = action_probability
            for outcome_index, outcome in enumerate(("home", "draw", "away")):
                heldout_test[f"baseline_delta_{outcome}"] = baseline_delta[:, outcome_index]
                heldout_test[f"action_delta_{outcome}"] = action_delta[:, outcome_index]
            fold_predictions.append(heldout_test)
            fold_profiles[heldout_slot] = {
                "bookmaker_name": BOOKMAKER_NAMES[heldout],
                "normal_training": training_counts,
                "closing_training_rows": int(len(training)),
                "closing_training_books": int(training["book_slot"].nunique()),
                "heldout_test_rows": int(len(heldout_test)),
                "heldout_test_matches": int(heldout_test["match_id"].nunique()),
            }

        combined = pd.concat(fold_predictions, ignore_index=True)
        keys = ["match_id", "book_slot", "hours_before_kickoff"]
        if combined.duplicated(keys).any():
            raise RuntimeError("duplicate out-of-book test predictions")
        expected_rows = sum(
            int((datasets["test"]["book"] == book).sum())
            for book in SELECTED_BOOKS
        )
        if len(combined) > expected_rows:
            raise RuntimeError("out-of-book prediction count exceeds eligible test states")

        baseline_probability = combined["baseline_probability"].to_numpy(dtype=float)
        action_probability = combined["action_probability"].to_numpy(dtype=float)
        baseline_delta = combined[
            ["baseline_delta_home", "baseline_delta_draw", "baseline_delta_away"]
        ].to_numpy(dtype=float)
        action_delta = combined[
            ["action_delta_home", "action_delta_draw", "action_delta_away"]
        ].to_numpy(dtype=float)
        hazard, conditional = exp8.repricing_evaluation(
            combined,
            baseline_probability,
            action_probability,
            baseline_delta,
            action_delta,
        )

        baseline_expected = baseline_probability[:, None] * baseline_delta
        action_expected = action_probability[:, None] * action_delta
        baseline_identity = exp13.choose_candidate_identity(
            combined,
            baseline_expected,
            "generic_raw_identity",
        )
        action_identity = exp13.choose_candidate_identity(
            combined,
            action_expected,
            "unseen_book_action_identity",
        )
        baseline_strategy = exp13.strategy_from_identity(
            combined,
            baseline_identity,
            baseline_expected,
            "generic_raw_baseline",
        )
        ranker_strategy = exp13.strategy_from_identity(
            combined,
            baseline_identity,
            action_expected,
            "unseen_book_action_ranker",
        )
        selector_strategy = exp13.strategy_from_identity(
            combined,
            action_identity,
            action_expected,
            "unseen_book_action_selector",
        )

        strategies = {
            "generic_raw_baseline": baseline_strategy,
            "unseen_book_action_ranker": ranker_strategy,
            "unseen_book_action_selector": selector_strategy,
        }
        for name, strategy in strategies.items():
            strategy.to_csv(
                root / f"strategy_{name}.csv.gz",
                index=False,
                compression="gzip",
            )
        combined.to_csv(
            root / "out_of_book_predictions.csv.gz",
            index=False,
            compression="gzip",
        )

        strategy_metrics = {
            name: exp8.strategy_metrics(strategy)
            for name, strategy in strategies.items()
        }
        comparisons = {
            "ranker_vs_baseline": exp8.compare_strategies(
                baseline_strategy,
                ranker_strategy,
            ),
            "selector_vs_baseline": exp8.compare_strategies(
                baseline_strategy,
                selector_strategy,
            ),
        }
        ranker_by_cutoff, ranker_positive_cutoffs = cutoff_incremental_clv(
            baseline_strategy,
            ranker_strategy,
        )
        selector_by_cutoff, selector_positive_cutoffs = cutoff_incremental_clv(
            baseline_strategy,
            selector_strategy,
        )
        concentration = bookmaker_concentration(
            baseline_strategy,
            ranker_strategy,
        )
        ranker_comparison = comparisons["ranker_vs_baseline"]
        primary_checks = {
            "ranker_incremental_clv_ci_above_zero": bool(
                ranker_comparison["paired_match_bootstrap"]["ci95_low"] > 0.0
            ),
            "ranker_positive_at_least_3_of_4_cutoffs": bool(
                ranker_positive_cutoffs >= 3
            ),
            "largest_book_positive_contribution_at_most_40_percent": bool(
                concentration["largest_positive_contribution_share"] <= 0.40
            ),
        }
        structural_checks = {
            "conditional_mae_ci_above_zero": bool(
                conditional["paired_match_bootstrap"]["ci95_low"] > 0.0
            ),
            "conditional_improves_at_least_3_of_4_cutoffs": bool(
                conditional["improved_cutoffs"] >= 3
            ),
        }

        report = {
            "experiment": "014_unseen_book_action_ranking",
            "status": "completed",
            "interpretation": "diagnostic_transfer_on_opened_historical_test",
            "archive": archive_meta,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "generic_raw_feature_count": int(len(raw_x_columns)),
            "action_residual_columns": ACTION_COLUMNS,
            "fold_profiles": fold_profiles,
            "out_of_book_test_rows": int(len(combined)),
            "out_of_book_test_matches": int(combined["match_id"].nunique()),
            "closing_move_hazard": hazard,
            "conditional_closing_delta": conditional,
            "strategy_metrics": strategy_metrics,
            "incremental_clv": comparisons,
            "ranker_incremental_clv_by_cutoff": ranker_by_cutoff,
            "ranker_positive_cutoffs": ranker_positive_cutoffs,
            "selector_incremental_clv_by_cutoff": selector_by_cutoff,
            "selector_positive_cutoffs": selector_positive_cutoffs,
            "ranker_bookmaker_concentration": concentration,
            "primary_checks": primary_checks,
            "structural_checks": structural_checks,
            "primary_transfer_promoted": all(primary_checks.values()),
            "structural_transfer_supported": all(structural_checks.values()),
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        failure_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "progress": json.loads(progress_path.read_text(encoding="utf-8"))
                    if progress_path.exists()
                    else None,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
