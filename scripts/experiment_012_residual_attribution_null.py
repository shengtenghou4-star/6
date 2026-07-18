from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_008_named_book_clv as exp8
import experiment_011_closing_line_residual as exp11
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
RANDOM_SEED = exp8.RANDOM_SEED

SURPRISE_COLUMNS = [
    "move_surprise_abs",
    "move_surprise_signed",
    "no_move_surprise",
    "unexpected_move_surprise",
]
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
PERSISTENCE_COLUMNS = [
    "prior_residual_cutoffs",
    "prior_move_surprise_mean",
    "prior_abs_move_surprise_mean",
    "prior_action_residual_l2_mean",
    "prior_abnormality_mean",
    "prior_action_residual_home_sum",
    "prior_action_residual_draw_sum",
    "prior_action_residual_away_sum",
]


def shuffle_joint_residual_vector(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    seed: int,
) -> pd.DataFrame:
    """Preserve within-book/cutoff residual distributions but break match alignment."""
    output = frame.copy()
    rng = np.random.default_rng(seed)
    for _, group in frame.groupby(["book_slot", "hours_before_kickoff"], sort=True):
        indices = group.index.to_numpy()
        if len(indices) <= 1:
            continue
        permuted = rng.permutation(indices)
        output.loc[indices, columns] = frame.loc[permuted, columns].to_numpy()
    return output


def fit_models(
    validation: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    hazard = exp8.fixed_classifier()
    hazard.fit(validation[columns], validation["future_move"])
    probability = hazard.predict_proba(test[columns])[:, 1]

    validation_movers = validation[validation["future_move"] == 1]
    if validation_movers.empty:
        raise RuntimeError("no validation closing movers")
    delta = np.empty((len(test), 3), dtype=float)
    for outcome_index, target in enumerate(exp8.TARGET_DELTA_COLUMNS):
        model = exp8.fixed_regressor()
        model.fit(validation_movers[columns], validation_movers[target])
        delta[:, outcome_index] = model.predict(test[columns])
    return probability, delta


def evaluate_variant(
    name: str,
    test: pd.DataFrame,
    baseline_probability: np.ndarray,
    baseline_delta: np.ndarray,
    baseline_strategy: pd.DataFrame,
    probability: np.ndarray,
    delta: np.ndarray,
) -> tuple[dict[str, Any], pd.DataFrame]:
    hazard, conditional = exp8.repricing_evaluation(
        test,
        baseline_probability,
        probability,
        baseline_delta,
        delta,
    )
    strategy = exp8.strategy_candidates(
        test,
        probability[:, None] * delta,
        name,
    )
    strategy_metrics = exp8.strategy_metrics(strategy)
    comparison = exp8.compare_strategies(baseline_strategy, strategy)
    report = {
        "closing_move_hazard_vs_baseline": hazard,
        "conditional_closing_delta_vs_baseline": conditional,
        "closing_clv_strategy": strategy_metrics,
        "incremental_clv_vs_baseline": comparison,
    }
    return report, strategy


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adversarially audit and attribute the Experiment 011 closing-line residual signal."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-012")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
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

        progress("training_normal_models")
        normal_hazard, normal_movement, training_counts = residual_gen.train_frozen_models(
            datasets["train"],
            hazard_max=args.hazard_max_train,
            movement_max=args.movement_max_train,
        )

        residual_frames: dict[str, pd.DataFrame] = {}
        x_frames: dict[str, pd.DataFrame] = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            residual_frames[split] = residual_gen.build_residual_frame(
                split,
                datasets[split],
                normal_hazard,
                normal_movement,
            )
            x_frames[split], columns = exp8.x_frame(datasets[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif raw_x_columns != columns:
                raise RuntimeError("validation/test raw X schemas differ")
        assert raw_x_columns is not None

        progress("extracting_same_book_closing_prices")
        future, closing_profile = exp11.build_closing_prices(
            source_paths,
            [residual_frames["validation"], residual_frames["test"]],
            chunksize=args.chunksize,
        )
        validation, baseline_columns, augmented_columns = exp8.model_frame(
            residual_frames["validation"],
            x_frames["validation"],
            future,
            raw_x_columns,
        )
        test, baseline_test, augmented_test = exp8.model_frame(
            residual_frames["test"],
            x_frames["test"],
            future,
            raw_x_columns,
        )
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test model schemas differ")

        full_residual_columns = [
            column for column in augmented_columns if column not in baseline_columns
        ]
        family_columns = {
            "move_surprise": SURPRISE_COLUMNS,
            "contemporaneous_action": ACTION_COLUMNS,
            "sequential_persistence": PERSISTENCE_COLUMNS,
            "full_residual": full_residual_columns,
        }
        for family, columns in family_columns.items():
            missing = sorted(set(columns) - set(full_residual_columns))
            if missing:
                raise ValueError(f"{family} columns are not residual features: {missing}")

        progress(
            "training_common_baseline",
            validation_rows=int(len(validation)),
            test_rows=int(len(test)),
        )
        baseline_probability, baseline_delta = fit_models(
            validation,
            test,
            baseline_columns,
        )
        baseline_strategy = exp8.strategy_candidates(
            test,
            baseline_probability[:, None] * baseline_delta,
            "raw_market_baseline",
        )
        baseline_metrics = exp8.strategy_metrics(baseline_strategy)
        baseline_strategy.to_csv(
            root / "strategy_raw_market_baseline.csv.gz",
            index=False,
            compression="gzip",
        )

        variants: dict[str, Any] = {}
        strategies: dict[str, pd.DataFrame] = {}
        for family, residual_columns in family_columns.items():
            progress("training_real_residual_variant", variant=family)
            model_columns = baseline_columns + residual_columns
            probability, delta = fit_models(validation, test, model_columns)
            variants[family], strategies[family] = evaluate_variant(
                family,
                test,
                baseline_probability,
                baseline_delta,
                baseline_strategy,
                probability,
                delta,
            )
            strategies[family].to_csv(
                root / f"strategy_{family}.csv.gz",
                index=False,
                compression="gzip",
            )

        progress("training_shuffled_residual_null")
        shuffled_validation = shuffle_joint_residual_vector(
            validation,
            full_residual_columns,
            seed=RANDOM_SEED + 1201,
        )
        shuffled_test = shuffle_joint_residual_vector(
            test,
            full_residual_columns,
            seed=RANDOM_SEED + 1202,
        )
        shuffled_probability, shuffled_delta = fit_models(
            shuffled_validation,
            shuffled_test,
            augmented_columns,
        )
        variants["shuffled_residual_null"], strategies["shuffled_residual_null"] = evaluate_variant(
            "shuffled_residual_null",
            test,
            baseline_probability,
            baseline_delta,
            baseline_strategy,
            shuffled_probability,
            shuffled_delta,
        )
        strategies["shuffled_residual_null"].to_csv(
            root / "strategy_shuffled_residual_null.csv.gz",
            index=False,
            compression="gzip",
        )

        full = variants["full_residual"]
        shuffled = variants["shuffled_residual_null"]
        full_clv = full["incremental_clv_vs_baseline"]
        shuffled_clv = shuffled["incremental_clv_vs_baseline"]

        family_positive_point_layers: dict[str, bool] = {}
        for family in ("move_surprise", "contemporaneous_action", "sequential_persistence"):
            result = variants[family]
            family_positive_point_layers[family] = bool(
                result["closing_move_hazard_vs_baseline"]["improvement"] > 0.0
                and result["conditional_closing_delta_vs_baseline"]["improvement"] > 0.0
                and result["incremental_clv_vs_baseline"][
                    "mean_augmented_minus_baseline_opportunity_log_clv"
                ]
                > 0.0
            )

        shuffled_ci = shuffled_clv["paired_match_bootstrap"]
        adversarial_checks = {
            "full_hazard_reproduced": bool(
                full["closing_move_hazard_vs_baseline"]["promoted"]
            ),
            "full_conditional_reproduced": bool(
                full["conditional_closing_delta_vs_baseline"]["promoted"]
            ),
            "full_incremental_clv_reproduced": bool(
                full_clv["paired_match_bootstrap"]["ci95_low"] > 0.0
            ),
            "full_hazard_beats_shuffled_point": bool(
                full["closing_move_hazard_vs_baseline"]["improvement"]
                > shuffled["closing_move_hazard_vs_baseline"]["improvement"]
            ),
            "full_conditional_beats_shuffled_point": bool(
                full["conditional_closing_delta_vs_baseline"]["improvement"]
                > shuffled["conditional_closing_delta_vs_baseline"]["improvement"]
            ),
            "full_clv_beats_shuffled_point": bool(
                full_clv["mean_augmented_minus_baseline_opportunity_log_clv"]
                > shuffled_clv[
                    "mean_augmented_minus_baseline_opportunity_log_clv"
                ]
            ),
            "shuffled_incremental_clv_ci_includes_zero": bool(
                shuffled_ci["ci95_low"] <= 0.0 <= shuffled_ci["ci95_high"]
            ),
            "at_least_one_interpretable_family_positive_in_all_layers": bool(
                any(family_positive_point_layers.values())
            ),
        }

        summary_rows = []
        for name, result in variants.items():
            summary_rows.append(
                {
                    "variant": name,
                    "hazard_brier_improvement": result[
                        "closing_move_hazard_vs_baseline"
                    ]["improvement"],
                    "hazard_ci_low": result["closing_move_hazard_vs_baseline"][
                        "paired_match_bootstrap"
                    ]["ci95_low"],
                    "conditional_mae_improvement": result[
                        "conditional_closing_delta_vs_baseline"
                    ]["improvement"],
                    "conditional_ci_low": result[
                        "conditional_closing_delta_vs_baseline"
                    ]["paired_match_bootstrap"]["ci95_low"],
                    "incremental_opportunity_log_clv": result[
                        "incremental_clv_vs_baseline"
                    ]["mean_augmented_minus_baseline_opportunity_log_clv"],
                    "incremental_clv_ci_low": result[
                        "incremental_clv_vs_baseline"
                    ]["paired_match_bootstrap"]["ci95_low"],
                    "incremental_clv_ci_high": result[
                        "incremental_clv_vs_baseline"
                    ]["paired_match_bootstrap"]["ci95_high"],
                }
            )
        pd.DataFrame(summary_rows).to_csv(root / "variant_summary.csv", index=False)

        report = {
            "experiment": "012_residual_attribution_and_shuffled_null",
            "status": "completed",
            "interpretation": "diagnostic_falsification_on_opened_historical_test",
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "validation_rows": int(len(validation)),
            "validation_matches": int(validation["match_id"].nunique()),
            "test_rows": int(len(test)),
            "test_matches": int(test["match_id"].nunique()),
            "frozen_books": {
                f"b{book}": BOOKMAKER_NAMES[book] for book in SELECTED_BOOKS
            },
            "baseline_closing_strategy": baseline_metrics,
            "residual_families": family_columns,
            "variants": variants,
            "family_positive_point_layers": family_positive_point_layers,
            "adversarial_checks": adversarial_checks,
            "adversarial_audit_passed": all(adversarial_checks.values()),
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
