from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_006_independent_residual_outcome as exp6
import experiment_008_named_book_clv as exp8
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
CLOSING_INDEX = 71
TRADE_FRACTION = 0.20


def wanted_sets(residual_frames: list[pd.DataFrame]) -> dict[tuple[int, int], set[str]]:
    combined = pd.concat(
        [
            frame.loc[
                frame["hours_before_kickoff"].isin(SIGNAL_HOURS),
                ["match_id", "book_slot", "hours_before_kickoff"],
            ]
            for frame in residual_frames
        ],
        ignore_index=True,
    )
    combined["match_id"] = combined["match_id"].astype(str)
    combined["book"] = combined["book_slot"].str.removeprefix("b").astype(int)
    return {
        (int(hours), int(book)): set(group["match_id"].tolist())
        for (hours, book), group in combined.groupby(
            ["hours_before_kickoff", "book"], sort=False
        )
    }


def build_closing_prices(
    paths: list[Path],
    residual_frames: list[pd.DataFrame],
    *,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    wanted = wanted_sets(residual_frames)
    observation_indices = {hours: CUTOFFS[hours] + 1 for hours in SIGNAL_HOURS}
    needed_indices = sorted({*observation_indices.values(), CLOSING_INDEX})
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
            cache = {
                index: raw_and_devig(frame, SELECTED_BOOKS, index)
                for index in needed_indices
            }
            raw_close, p_close, _over_close, complete_close = cache[CLOSING_INDEX]
            for hours in SIGNAL_HOURS:
                observation_index = observation_indices[hours]
                raw_observation, p_observation, over_observation, complete_observation = cache[
                    observation_index
                ]
                for book_position, book in enumerate(SELECTED_BOOKS):
                    requested = wanted[(hours, book)]
                    requested_mask = np.fromiter(
                        (match_id in requested for match_id in match_ids),
                        dtype=bool,
                        count=len(match_ids),
                    )
                    eligible = (
                        requested_mask
                        & complete_observation[:, book_position]
                        & complete_close[:, book_position]
                    )
                    if not eligible.any():
                        continue
                    observation_p = p_observation[eligible, book_position, :]
                    future_p = p_close[eligible, book_position, :]
                    observation_raw = raw_observation[eligible, book_position, :]
                    future_raw = raw_close[eligible, book_position, :]
                    delta = future_p - observation_p
                    moved = np.any(
                        np.abs(future_raw - observation_raw) > 1e-12,
                        axis=1,
                    )
                    part = pd.DataFrame(
                        {
                            "match_id": match_ids[eligible],
                            "book_slot": f"b{book}",
                            "hours_before_kickoff": hours,
                            "future_move": moved.astype(np.int8),
                            "observation_overround": over_observation[
                                eligible, book_position
                            ],
                        }
                    )
                    for outcome_index, outcome in enumerate(OUTCOMES):
                        part[f"observation_p_{outcome}"] = observation_p[
                            :, outcome_index
                        ]
                        part[f"future_p_{outcome}"] = future_p[:, outcome_index]
                        part[f"future_delta_{outcome}"] = delta[:, outcome_index]
                        part[f"observation_raw_{outcome}"] = observation_raw[
                            :, outcome_index
                        ]
                        part[f"future_raw_{outcome}"] = future_raw[:, outcome_index]
                    parts.append(part)
    if not parts:
        raise RuntimeError("no closing-price records")
    output = pd.concat(parts, ignore_index=True)
    keys = ["match_id", "book_slot", "hours_before_kickoff"]
    if output.duplicated(keys).any():
        raise RuntimeError("duplicate closing-price keys")
    return output, {
        "rows": int(len(output)),
        "matches": int(output["match_id"].nunique()),
        "close_move_rate": float(output["future_move"].mean()),
        "closing_index": CLOSING_INDEX,
        "rows_by_book": {
            str(key): int(value)
            for key, value in output["book_slot"].value_counts().sort_index().items()
        },
        "rows_by_cutoff": {
            str(int(key)): int(value)
            for key, value in output["hours_before_kickoff"]
            .value_counts()
            .sort_index()
            .items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test abnormal residuals against same-book closing-line movement."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-011")
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
            source_paths, chunksize=args.chunksize
        )
        diagnostics = datasets.pop("diagnostics")
        progress("training_normal_models")
        hazard, movement_models, training_counts = residual_gen.train_frozen_models(
            datasets["train"],
            hazard_max=args.hazard_max_train,
            movement_max=args.movement_max_train,
        )

        residual_frames: dict[str, pd.DataFrame] = {}
        x_frames: dict[str, pd.DataFrame] = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            residual_frames[split] = residual_gen.build_residual_frame(
                split, datasets[split], hazard, movement_models
            )
            x_frames[split], columns = exp8.x_frame(datasets[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif raw_x_columns != columns:
                raise RuntimeError("validation/test raw X schemas differ")
        assert raw_x_columns is not None

        progress("extracting_same_book_closing_prices")
        future, closing_profile = build_closing_prices(
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

        progress("training_closing_repricing_models")
        baseline_hazard = exp8.fixed_classifier()
        augmented_hazard = exp8.fixed_classifier()
        baseline_hazard.fit(validation[baseline_columns], validation["future_move"])
        augmented_hazard.fit(validation[augmented_columns], validation["future_move"])
        baseline_probability = baseline_hazard.predict_proba(test[baseline_columns])[:, 1]
        augmented_probability = augmented_hazard.predict_proba(test[augmented_columns])[:, 1]

        validation_movers = validation[validation["future_move"] == 1].copy()
        if validation_movers.empty:
            raise RuntimeError("no validation close movers")
        baseline_delta = np.empty((len(test), 3), dtype=float)
        augmented_delta = np.empty((len(test), 3), dtype=float)
        for outcome_index, target in enumerate(exp8.TARGET_DELTA_COLUMNS):
            baseline_model = exp8.fixed_regressor()
            augmented_model = exp8.fixed_regressor()
            baseline_model.fit(validation_movers[baseline_columns], validation_movers[target])
            augmented_model.fit(validation_movers[augmented_columns], validation_movers[target])
            baseline_delta[:, outcome_index] = baseline_model.predict(
                test[baseline_columns]
            )
            augmented_delta[:, outcome_index] = augmented_model.predict(
                test[augmented_columns]
            )

        hazard_result, conditional_result = exp8.repricing_evaluation(
            test,
            baseline_probability,
            augmented_probability,
            baseline_delta,
            augmented_delta,
        )

        progress("evaluating_closing_clv_strategies")
        baseline_strategy = exp8.strategy_candidates(
            test,
            baseline_probability[:, None] * baseline_delta,
            "baseline_closing",
        )
        augmented_strategy = exp8.strategy_candidates(
            test,
            augmented_probability[:, None] * augmented_delta,
            "augmented_closing",
        )
        baseline_metrics = exp8.strategy_metrics(baseline_strategy)
        augmented_metrics = exp8.strategy_metrics(augmented_strategy)
        strategy_comparison = exp8.compare_strategies(
            baseline_strategy, augmented_strategy
        )

        promotion_checks = {
            "closing_move_hazard_promoted": hazard_result["promoted"],
            "conditional_closing_delta_promoted": conditional_result["promoted"],
            "augmented_closing_log_clv_positive_ci": augmented_metrics[
                "positive_trade_log_clv_bootstrap"
            ]["ci95_low"]
            > 0.0,
            "augmented_beats_baseline_opportunity_clv_ci": strategy_comparison[
                "paired_match_bootstrap"
            ]["ci95_low"]
            > 0.0,
            "augmented_fair_probability_clv_positive": augmented_metrics[
                "mean_trade_fair_probability_clv"
            ]
            > 0.0,
            "augmented_positive_at_least_3_of_4_cutoffs": augmented_metrics[
                "positive_cutoffs"
            ]
            >= 3,
        }
        report = {
            "experiment": "011_same_book_closing_line_residual",
            "status": "completed",
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
            "closing_move_hazard": hazard_result,
            "conditional_closing_delta": conditional_result,
            "baseline_closing_strategy": baseline_metrics,
            "augmented_closing_strategy": augmented_metrics,
            "strategy_comparison": strategy_comparison,
            "promotion_checks": promotion_checks,
            "same_book_closing_residual_promoted": all(promotion_checks.values()),
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        baseline_strategy.to_csv(
            root / "baseline_closing_strategy.csv.gz",
            index=False,
            compression="gzip",
        )
        augmented_strategy.to_csv(
            root / "augmented_closing_strategy.csv.gz",
            index=False,
            compression="gzip",
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
                    "progress": json.loads(
                        progress_path.read_text(encoding="utf-8")
                    )
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
