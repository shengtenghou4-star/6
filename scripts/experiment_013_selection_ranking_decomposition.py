from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_006_independent_residual_outcome as exp6
import experiment_008_named_book_clv as exp8
import experiment_011_closing_line_residual as exp11
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import (
    BOOKMAKER_NAMES,
    DOWNLOAD_URL,
    OUTCOMES,
    SELECTED_BOOKS,
    SERIES_FILES,
    download,
    extract_required,
)

SIGNAL_HOURS = exp11.SIGNAL_HOURS
TRADE_FRACTION = exp11.TRADE_FRACTION


def fit_models(validation: pd.DataFrame, test: pd.DataFrame, columns: list[str]) -> tuple[np.ndarray, np.ndarray]:
    hazard = exp8.fixed_classifier()
    hazard.fit(validation[columns], validation["future_move"])
    probability = hazard.predict_proba(test[columns])[:, 1]
    movers = validation[validation["future_move"] == 1]
    if movers.empty:
        raise RuntimeError("no validation movers")
    delta = np.empty((len(test), 3), dtype=float)
    for outcome_index, target in enumerate(exp8.TARGET_DELTA_COLUMNS):
        model = exp8.fixed_regressor()
        model.fit(movers[columns], movers[target])
        delta[:, outcome_index] = model.predict(test[columns])
    return probability, delta


def choose_candidate_identity(frame: pd.DataFrame, expected_delta: np.ndarray, source: str) -> pd.DataFrame:
    outcome_index = np.argmax(expected_delta, axis=1)
    score = expected_delta[np.arange(len(frame)), outcome_index]
    candidates = pd.DataFrame(
        {
            "source_row": np.arange(len(frame), dtype=np.int64),
            "match_id": frame["match_id"].astype(str).to_numpy(),
            "hours_before_kickoff": frame["hours_before_kickoff"].to_numpy(dtype=int),
            "book_slot": frame["book_slot"].astype(str).to_numpy(),
            "bookmaker_name": frame["bookmaker_name"].astype(str).to_numpy(),
            "selected_outcome_index": outcome_index,
            "selected_outcome": np.asarray(OUTCOMES, dtype=object)[outcome_index],
            "identity_selection_score": score,
            "identity_source": source,
        }
    )
    candidates.sort_values(
        ["match_id", "hours_before_kickoff", "identity_selection_score", "book_slot", "selected_outcome_index"],
        ascending=[True, True, False, True, True],
        kind="mergesort",
        inplace=True,
    )
    return candidates.groupby(["match_id", "hours_before_kickoff"], sort=False, as_index=False).first()


def strategy_from_identity(
    frame: pd.DataFrame,
    identity: pd.DataFrame,
    ranking_expected_delta: np.ndarray,
    name: str,
) -> pd.DataFrame:
    positions = identity["source_row"].to_numpy(dtype=int)
    outcomes = identity["selected_outcome_index"].to_numpy(dtype=int)
    confidence = ranking_expected_delta[positions, outcomes]

    raw_observation = frame[[f"observation_raw_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    raw_future = frame[[f"future_raw_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    p_observation = frame[[f"observation_p_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)
    p_future = frame[[f"future_p_{outcome}" for outcome in OUTCOMES]].to_numpy(dtype=float)

    strategy = identity[
        [
            "match_id",
            "hours_before_kickoff",
            "book_slot",
            "bookmaker_name",
            "selected_outcome_index",
            "selected_outcome",
            "identity_source",
        ]
    ].copy()
    strategy["confidence"] = confidence
    strategy["log_odds_clv"] = np.log(raw_observation[positions, outcomes] / raw_future[positions, outcomes])
    strategy["fair_probability_clv"] = p_future[positions, outcomes] - p_observation[positions, outcomes]
    strategy["strategy"] = name
    strategy["traded"] = False
    for hours in SIGNAL_HOURS:
        indices = strategy.index[strategy["hours_before_kickoff"] == hours].tolist()
        ordered = strategy.loc[indices].sort_values(
            ["confidence", "match_id", "book_slot", "selected_outcome_index"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        trade_count = max(1, int(np.floor(len(ordered) * TRADE_FRACTION)))
        strategy.loc[ordered.index[:trade_count], "traded"] = True
    strategy["opportunity_log_clv"] = np.where(strategy["traded"], strategy["log_odds_clv"], 0.0)
    strategy["opportunity_probability_clv"] = np.where(
        strategy["traded"], strategy["fair_probability_clv"], 0.0
    )
    return strategy


def compare_by_cutoff(baseline: pd.DataFrame, variant: pd.DataFrame) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    joined = baseline[keys + ["opportunity_log_clv"]].merge(
        variant[keys + ["opportunity_log_clv"]],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_variant"),
    )
    joined["improvement"] = joined["opportunity_log_clv_variant"] - joined["opportunity_log_clv_baseline"]
    output: dict[str, Any] = {}
    for hours in SIGNAL_HOURS:
        group = joined[joined["hours_before_kickoff"] == hours]
        bootstrap = exp6.bootstrap_match_improvement(
            group["match_id"].to_numpy(), group["improvement"].to_numpy(dtype=float), replicates=1000
        )
        output[f"T-{hours}h"] = {
            "opportunities": int(len(group)),
            "mean_incremental_opportunity_log_clv": float(group["improvement"].mean()),
            "paired_match_bootstrap": bootstrap,
        }
    return output


def trade_overlap(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    a = left[keys + ["traded"]].rename(columns={"traded": "left_traded"})
    b = right[keys + ["traded"]].rename(columns={"traded": "right_traded"})
    joined = a.merge(b, on=keys, validate="one_to_one")
    both = joined["left_traded"] & joined["right_traded"]
    either = joined["left_traded"] | joined["right_traded"]
    return {
        "both_traded": int(both.sum()),
        "either_traded": int(either.sum()),
        "jaccard": float(both.sum() / either.sum()) if either.any() else 1.0,
        "left_only": int((joined["left_traded"] & ~joined["right_traded"]).sum()),
        "right_only": int((~joined["left_traded"] & joined["right_traded"]).sum()),
    }


def identity_overlap(baseline: pd.DataFrame, full: pd.DataFrame) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    joined = baseline.merge(full, on=keys, validate="one_to_one", suffixes=("_baseline", "_full"))
    same_book = joined["book_slot_baseline"] == joined["book_slot_full"]
    same_outcome = joined["selected_outcome_index_baseline"] == joined["selected_outcome_index_full"]
    same_identity = same_book & same_outcome
    return {
        "opportunities": int(len(joined)),
        "same_book_fraction": float(same_book.mean()),
        "same_outcome_fraction": float(same_outcome.mean()),
        "same_book_and_outcome_fraction": float(same_identity.mean()),
        "changed_identity_count": int((~same_identity).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Decompose residual closing CLV into selection and ranking effects.")
    parser.add_argument("--output-root", default="artifacts/experiment-013")
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
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("building_normal_state_records")
        datasets = residual_gen.build_all_state_records(source_paths, chunksize=args.chunksize)
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
                split, datasets[split], normal_hazard, normal_movement
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
            residual_frames["validation"], x_frames["validation"], future, raw_x_columns
        )
        test, baseline_test, augmented_test = exp8.model_frame(
            residual_frames["test"], x_frames["test"], future, raw_x_columns
        )
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test schemas differ")

        progress("training_baseline_and_full_models")
        baseline_probability, baseline_delta = fit_models(validation, test, baseline_columns)
        full_probability, full_delta = fit_models(validation, test, augmented_columns)
        baseline_expected = baseline_probability[:, None] * baseline_delta
        full_expected = full_probability[:, None] * full_delta

        progress("constructing_candidate_identities")
        baseline_identity = choose_candidate_identity(test, baseline_expected, "baseline_identity")
        full_identity = choose_candidate_identity(test, full_expected, "full_residual_identity")

        progress("constructing_hybrid_strategies")
        strategies = {
            "raw_baseline": strategy_from_identity(test, baseline_identity, baseline_expected, "raw_baseline"),
            "full_residual": strategy_from_identity(test, full_identity, full_expected, "full_residual"),
            "rank_only_overlay": strategy_from_identity(test, baseline_identity, full_expected, "rank_only_overlay"),
            "selection_only_overlay": strategy_from_identity(test, full_identity, baseline_expected, "selection_only_overlay"),
        }
        for name, strategy in strategies.items():
            strategy.to_csv(root / f"strategy_{name}.csv.gz", index=False, compression="gzip")
        baseline_identity.to_csv(root / "identity_baseline.csv.gz", index=False, compression="gzip")
        full_identity.to_csv(root / "identity_full_residual.csv.gz", index=False, compression="gzip")

        baseline_strategy = strategies["raw_baseline"]
        metrics = {name: exp8.strategy_metrics(strategy) for name, strategy in strategies.items()}
        comparisons = {
            name: exp8.compare_strategies(baseline_strategy, strategy)
            for name, strategy in strategies.items()
            if name != "raw_baseline"
        }
        by_cutoff = {
            name: compare_by_cutoff(baseline_strategy, strategy)
            for name, strategy in strategies.items()
            if name != "raw_baseline"
        }
        full_lift = comparisons["full_residual"]["mean_augmented_minus_baseline_opportunity_log_clv"]
        decomposition_share = {
            name: float(comparison["mean_augmented_minus_baseline_opportunity_log_clv"] / full_lift)
            if abs(full_lift) > 1e-15
            else None
            for name, comparison in comparisons.items()
        }

        report = {
            "experiment": "013_selection_ranking_decomposition",
            "status": "completed",
            "interpretation": "diagnostic_mechanism_decomposition_on_opened_historical_test",
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "validation_rows": int(len(validation)),
            "validation_matches": int(validation["match_id"].nunique()),
            "test_rows": int(len(test)),
            "test_matches": int(test["match_id"].nunique()),
            "frozen_books": {f"b{book}": BOOKMAKER_NAMES[book] for book in SELECTED_BOOKS},
            "identity_overlap": identity_overlap(baseline_identity, full_identity),
            "trade_overlap_vs_baseline": {
                name: trade_overlap(baseline_strategy, strategy)
                for name, strategy in strategies.items()
                if name != "raw_baseline"
            },
            "strategy_metrics": metrics,
            "incremental_clv_vs_baseline": comparisons,
            "incremental_clv_by_cutoff": by_cutoff,
            "decomposition_share_of_full_lift": decomposition_share,
            "dominant_mechanism_by_point_lift": max(
                ("rank_only_overlay", "selection_only_overlay"),
                key=lambda name: comparisons[name]["mean_augmented_minus_baseline_opportunity_log_clv"],
            ),
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
