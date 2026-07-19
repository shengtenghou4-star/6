from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

import experiment_008_named_book_clv as exp8
import experiment_009_frozen_return_audit as exp9
import experiment_011_closing_line_residual as exp11
import experiment_013_selection_ranking_decomposition as exp13
import experiment_015_execution_stress as exp15
import experiment_016_selective_abstention as exp16
import experiment_017_matched_budget_return as exp17
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import DOWNLOAD_URL, SERIES_FILES, download, extract_required


def reconstruct_frozen_execution_state(
    root: Path,
    *,
    chunksize: int,
    hazard_max_train: int,
    movement_max_train: int,
    progress: Callable[..., None],
) -> dict[str, Any]:
    progress("acquiring_source")
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    archive_meta = download(DOWNLOAD_URL, archive)
    paths = extract_required(archive, extracted)
    source_paths = [paths[name] for name in SERIES_FILES]

    progress("rebuilding_frozen_normal_and_residual_state")
    datasets = residual_gen.build_all_state_records(
        source_paths, chunksize=chunksize
    )
    diagnostics = datasets.pop("diagnostics")
    normal_hazard, normal_movement, training_counts = residual_gen.train_frozen_models(
        datasets["train"],
        hazard_max=hazard_max_train,
        movement_max=movement_max_train,
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
    closing, closing_profile = exp11.build_closing_prices(
        source_paths,
        [residual_frames["validation"], residual_frames["test"]],
        chunksize=chunksize,
    )
    validation, baseline_columns, augmented_columns = exp8.model_frame(
        residual_frames["validation"],
        x_frames["validation"],
        closing,
        raw_x_columns,
    )
    test, baseline_test, augmented_test = exp8.model_frame(
        residual_frames["test"], x_frames["test"], closing, raw_x_columns
    )
    if baseline_columns != baseline_test or augmented_columns != augmented_test:
        raise RuntimeError("validation/test schemas differ")

    progress("fitting_models_on_frozen_validation_fit_partition")
    fit_mask = exp16.stable_fit_mask(validation["match_id"])
    fit = validation.loc[fit_mask].reset_index(drop=True)
    baseline_probability, baseline_delta = exp13.fit_models(
        fit, test, baseline_columns
    )
    action_probability, action_delta = exp13.fit_models(
        fit, test, augmented_columns
    )
    baseline_expected = baseline_probability[:, None] * baseline_delta
    action_expected = action_probability[:, None] * action_delta

    progress("freezing_matched_budget_policies_before_outcomes")
    identity = exp13.choose_candidate_identity(
        test, baseline_expected, "raw_identity"
    )
    candidates = exp16.candidate_table(
        test, identity, baseline_expected, action_expected
    )
    candidates = exp17.add_probability_clv(candidates, test, identity)
    raw_policy = exp17.apply_raw_policy(candidates)
    residual_policy = exp16.apply_policy(
        candidates, "positive_rank_score", exp17.FRACTION
    )
    residual_policy["strategy"] = "residual_positive_top_5pct"
    raw_policy.to_csv(
        root / "raw-policy-before-outcomes.csv.gz",
        index=False,
        compression="gzip",
    )
    residual_policy.to_csv(
        root / "residual-policy-before-outcomes.csv.gz",
        index=False,
        compression="gzip",
    )

    progress("extracting_delayed_execution_prices")
    execution_prices, execution_profile = exp15.build_execution_prices(
        source_paths, identity, chunksize=chunksize
    )
    execution_prices.to_csv(
        root / "execution-prices.csv.gz", index=False, compression="gzip"
    )

    progress("loading_outcomes_after_policy_freeze")
    outcomes, outcome_profile = exp9.load_outcomes(source_paths)
    raw_settled = exp15.attach_execution_and_outcomes(
        raw_policy, test, execution_prices, outcomes
    )
    residual_settled = exp15.attach_execution_and_outcomes(
        residual_policy, test, execution_prices, outcomes
    )
    return {
        "archive": archive_meta,
        "training_counts": training_counts,
        "normal_state_diagnostics": diagnostics,
        "closing_price_profile": closing_profile,
        "execution_price_profile": execution_profile,
        "outcome_profile": outcome_profile,
        "raw_policy": raw_policy,
        "residual_policy": residual_policy,
        "raw_settled": raw_settled,
        "residual_settled": residual_settled,
    }
