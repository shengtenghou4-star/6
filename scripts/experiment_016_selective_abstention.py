from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_006_independent_residual_outcome as exp6
import experiment_008_named_book_clv as exp8
import experiment_011_closing_line_residual as exp11
import experiment_013_selection_ranking_decomposition as exp13
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import DOWNLOAD_URL, OUTCOMES, SERIES_FILES, download, extract_required
from marketlab.json_compat import json_default


FRACTIONS = (0.01, 0.02, 0.05, 0.10, 0.20)
FAMILIES = (
    "positive_rank_score",
    "positive_rank_and_uplift_rank_score",
    "positive_rank_and_uplift_rank_margin",
)
RANDOM_SEED = 20260719


def stable_fit_mask(match_ids: pd.Series) -> np.ndarray:
    unique = sorted(set(match_ids.astype(str)))
    fit_matches = {
        match_id
        for match_id in unique
        if int.from_bytes(hashlib.sha256(match_id.encode("utf-8")).digest()[:8], "big") % 10 < 7
    }
    mask = match_ids.astype(str).isin(fit_matches).to_numpy(dtype=bool)
    if not mask.any() or mask.all():
        raise RuntimeError("deterministic validation split produced an empty partition")
    return mask


def candidate_table(
    frame: pd.DataFrame,
    identity: pd.DataFrame,
    baseline_expected: np.ndarray,
    action_expected: np.ndarray,
) -> pd.DataFrame:
    positions = identity["source_row"].to_numpy(dtype=int)
    outcomes = identity["selected_outcome_index"].to_numpy(dtype=int)
    rows = np.arange(len(identity))
    selected_baseline = baseline_expected[positions, outcomes]
    selected_action = action_expected[positions, outcomes]
    competing = action_expected[positions].copy()
    competing[rows, outcomes] = -np.inf
    rank_margin = selected_action - np.max(competing, axis=1)

    raw_observation = frame[[f"observation_raw_{outcome}" for outcome in OUTCOMES]].to_numpy(float)
    raw_close = frame[[f"future_raw_{outcome}" for outcome in OUTCOMES]].to_numpy(float)
    selected_observation = raw_observation[positions, outcomes]
    selected_close = raw_close[positions, outcomes]
    if not np.isfinite(selected_observation).all() or not np.isfinite(selected_close).all():
        raise ValueError("candidate prices contain non-finite values")
    if np.any(selected_observation <= 1.0) or np.any(selected_close <= 1.0):
        raise ValueError("candidate prices are not valid decimal odds")

    output = identity[
        [
            "match_id",
            "hours_before_kickoff",
            "book_slot",
            "bookmaker_name",
            "selected_outcome_index",
            "selected_outcome",
        ]
    ].copy()
    output["baseline_score"] = selected_baseline
    output["rank_score"] = selected_action
    output["residual_uplift"] = selected_action - selected_baseline
    output["rank_margin"] = rank_margin
    output["positive_direction_agreement"] = (selected_baseline > 0) & (selected_action > 0)
    output["observation_decimal_odds"] = selected_observation
    output["closing_decimal_odds"] = selected_close
    output["log_odds_clv"] = np.log(selected_observation / selected_close)
    if output.duplicated(["match_id", "hours_before_kickoff"]).any():
        raise RuntimeError("candidate table has duplicate match/cutoff rows")
    return output


def apply_policy(frame: pd.DataFrame, family: str, fraction: float) -> pd.DataFrame:
    if family not in FAMILIES:
        raise ValueError(f"unknown family: {family}")
    if fraction not in FRACTIONS:
        raise ValueError(f"unsupported fraction: {fraction}")
    output = frame.copy()
    output["traded"] = False
    if family == "positive_rank_score":
        eligible = output["rank_score"] > 0
        score = "rank_score"
    elif family == "positive_rank_and_uplift_rank_score":
        eligible = (output["rank_score"] > 0) & (output["residual_uplift"] > 0)
        score = "rank_score"
    else:
        eligible = (output["rank_score"] > 0) & (output["residual_uplift"] > 0)
        score = "rank_margin"

    for hours in exp11.SIGNAL_HOURS:
        cutoff = output["hours_before_kickoff"] == hours
        trade_count = max(1, int(np.floor(int(cutoff.sum()) * fraction)))
        ordered = output.loc[cutoff & eligible].sort_values(
            [score, "match_id", "book_slot", "selected_outcome_index"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        output.loc[ordered.index[:trade_count], "traded"] = True
    output["opportunity_log_clv"] = np.where(output["traded"], output["log_odds_clv"], 0.0)
    output["policy_family"] = family
    output["policy_fraction"] = fraction
    return output


def policy_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    trades = frame[frame["traded"]].copy()
    if trades.empty:
        return {
            "opportunities": int(len(frame)),
            "trades": 0,
            "mean_trade_log_clv": None,
            "mean_opportunity_log_clv": 0.0,
            "positive_cutoffs": 0,
            "match_bootstrap": None,
            "by_cutoff": {},
            "maximum_positive_book_contribution_share": None,
        }
    bootstrap = exp6.bootstrap_match_improvement(
        trades["match_id"].to_numpy(),
        trades["log_odds_clv"].to_numpy(float),
        replicates=1000,
    )
    by_cutoff: dict[str, Any] = {}
    positive_cutoffs = 0
    for hours in exp11.SIGNAL_HOURS:
        group = trades[trades["hours_before_kickoff"] == hours]
        mean = float(group["log_odds_clv"].mean()) if not group.empty else None
        positive_cutoffs += int(mean is not None and mean > 0)
        by_cutoff[f"T-{hours}h"] = {
            "trades": int(len(group)),
            "mean_log_odds_clv": mean,
        }
    contribution = trades.groupby("bookmaker_name")["log_odds_clv"].sum()
    positive = contribution[contribution > 0]
    concentration = float(positive.max() / positive.sum()) if not positive.empty else None
    return {
        "opportunities": int(len(frame)),
        "matches": int(frame["match_id"].nunique()),
        "trades": int(len(trades)),
        "trade_fraction": float(len(trades) / len(frame)),
        "mean_trade_log_clv": float(trades["log_odds_clv"].mean()),
        "mean_opportunity_log_clv": float(frame["opportunity_log_clv"].mean()),
        "positive_cutoffs": int(positive_cutoffs),
        "match_bootstrap": bootstrap,
        "by_cutoff": by_cutoff,
        "maximum_positive_book_contribution_share": concentration,
    }


def calibration_grid(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    rows: list[dict[str, Any]] = []
    for family in FAMILIES:
        for fraction in FRACTIONS:
            strategy = apply_policy(frame, family, fraction)
            metrics = policy_metrics(strategy)
            bootstrap = metrics["match_bootstrap"] or {"ci95_low": float("-inf"), "ci95_high": float("inf")}
            eligible = bool(
                metrics["trades"] >= 300
                and metrics["mean_trade_log_clv"] is not None
                and metrics["mean_trade_log_clv"] > 0
                and bootstrap["ci95_low"] > 0
                and metrics["positive_cutoffs"] >= 3
            )
            rows.append(
                {
                    "family": family,
                    "fraction": fraction,
                    "trades": metrics["trades"],
                    "mean_trade_log_clv": metrics["mean_trade_log_clv"],
                    "mean_opportunity_log_clv": metrics["mean_opportunity_log_clv"],
                    "ci95_low": bootstrap["ci95_low"],
                    "ci95_high": bootstrap["ci95_high"],
                    "positive_cutoffs": metrics["positive_cutoffs"],
                    "eligible": eligible,
                }
            )
    grid = pd.DataFrame(rows)
    eligible = grid[grid["eligible"]].copy()
    if eligible.empty:
        return grid, None
    family_order = {family: index for index, family in enumerate(FAMILIES)}
    eligible["family_order"] = eligible["family"].map(family_order)
    chosen = eligible.sort_values(
        ["ci95_low", "mean_trade_log_clv", "trades", "family_order", "fraction"],
        ascending=[False, False, False, True, False],
        kind="mergesort",
    ).iloc[0]
    return grid, {
        "family": str(chosen["family"]),
        "fraction": float(chosen["fraction"]),
        "calibration_trades": int(chosen["trades"]),
        "calibration_mean_trade_log_clv": float(chosen["mean_trade_log_clv"]),
        "calibration_ci95_low": float(chosen["ci95_low"]),
        "calibration_ci95_high": float(chosen["ci95_high"]),
        "calibration_positive_cutoffs": int(chosen["positive_cutoffs"]),
    }


def incremental_vs_baseline(
    baseline: pd.DataFrame, policy: pd.DataFrame
) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    joined = baseline[keys + ["opportunity_log_clv"]].merge(
        policy[keys + ["opportunity_log_clv"]],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_policy"),
    )
    if len(joined) != len(baseline) or len(joined) != len(policy):
        raise RuntimeError("policy and baseline opportunity universes differ")
    improvement = (
        joined["opportunity_log_clv_policy"].to_numpy(float)
        - joined["opportunity_log_clv_baseline"].to_numpy(float)
    )
    return {
        "mean_incremental_opportunity_log_clv": float(improvement.mean()),
        "paired_match_bootstrap": exp6.bootstrap_match_improvement(
            joined["match_id"].to_numpy(), improvement, replicates=1000
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate a selective rank-only residual policy without outcomes.")
    parser.add_argument("--output-root", default="artifacts/experiment-016")
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
            json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("building_frozen_normal_state")
        datasets = residual_gen.build_all_state_records(source_paths, chunksize=args.chunksize)
        diagnostics = datasets.pop("diagnostics")
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
        closing, closing_profile = exp11.build_closing_prices(
            source_paths,
            [residual_frames["validation"], residual_frames["test"]],
            chunksize=args.chunksize,
        )
        validation, baseline_columns, augmented_columns = exp8.model_frame(
            residual_frames["validation"], x_frames["validation"], closing, raw_x_columns
        )
        test, baseline_test, augmented_test = exp8.model_frame(
            residual_frames["test"], x_frames["test"], closing, raw_x_columns
        )
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test schemas differ")

        progress("splitting_validation_fit_and_calibration")
        fit_mask = stable_fit_mask(validation["match_id"])
        fit = validation.loc[fit_mask].reset_index(drop=True)
        calibration = validation.loc[~fit_mask].reset_index(drop=True)

        progress("fitting_repricing_models_on_validation_fit_partition")
        baseline_cal_probability, baseline_cal_delta = exp13.fit_models(
            fit, calibration, baseline_columns
        )
        action_cal_probability, action_cal_delta = exp13.fit_models(
            fit, calibration, augmented_columns
        )
        baseline_test_probability, baseline_test_delta = exp13.fit_models(
            fit, test, baseline_columns
        )
        action_test_probability, action_test_delta = exp13.fit_models(
            fit, test, augmented_columns
        )
        baseline_cal_expected = baseline_cal_probability[:, None] * baseline_cal_delta
        action_cal_expected = action_cal_probability[:, None] * action_cal_delta
        baseline_test_expected = baseline_test_probability[:, None] * baseline_test_delta
        action_test_expected = action_test_probability[:, None] * action_test_delta

        progress("calibrating_frozen_policy")
        calibration_identity = exp13.choose_candidate_identity(
            calibration, baseline_cal_expected, "raw_identity"
        )
        calibration_candidates = candidate_table(
            calibration,
            calibration_identity,
            baseline_cal_expected,
            action_cal_expected,
        )
        grid, selected = calibration_grid(calibration_candidates)
        grid.to_csv(root / "calibration-grid.csv", index=False)

        test_identity = exp13.choose_candidate_identity(test, baseline_test_expected, "raw_identity")
        test_candidates = candidate_table(
            test, test_identity, baseline_test_expected, action_test_expected
        )
        raw_baseline = exp13.strategy_from_identity(
            test, test_identity, baseline_test_expected, "raw_baseline_20pct"
        )

        if selected is None:
            test_policy = test_candidates.copy()
            test_policy["traded"] = False
            test_policy["opportunity_log_clv"] = 0.0
            test_policy["policy_family"] = "NO_TRADE_POLICY"
            test_policy["policy_fraction"] = 0.0
            test_metrics = policy_metrics(test_policy)
            incremental = incremental_vs_baseline(raw_baseline, test_policy)
            gate_checks = {"calibration_policy_exists": False}
            promoted = False
        else:
            test_policy = apply_policy(
                test_candidates, selected["family"], selected["fraction"]
            )
            test_metrics = policy_metrics(test_policy)
            incremental = incremental_vs_baseline(raw_baseline, test_policy)
            test_bootstrap = test_metrics["match_bootstrap"]
            gate_checks = {
                "calibration_policy_exists": True,
                "test_mean_trade_log_clv_positive": bool(
                    test_metrics["mean_trade_log_clv"] is not None
                    and test_metrics["mean_trade_log_clv"] > 0
                ),
                "test_bootstrap_ci_above_zero": bool(
                    test_bootstrap is not None and test_bootstrap["ci95_low"] > 0
                ),
                "positive_at_least_3_of_4_cutoffs": bool(
                    test_metrics["positive_cutoffs"] >= 3
                ),
                "incremental_opportunity_clv_positive": bool(
                    incremental["mean_incremental_opportunity_log_clv"] > 0
                ),
                "positive_book_contribution_not_over_50pct": bool(
                    test_metrics["maximum_positive_book_contribution_share"] is not None
                    and test_metrics["maximum_positive_book_contribution_share"] <= 0.50
                ),
            }
            promoted = all(gate_checks.values())

        test_policy.to_csv(root / "frozen-test-policy.csv.gz", index=False, compression="gzip")
        report = {
            "experiment": "016_validation_only_selective_abstention",
            "status": "completed",
            "evidentiary_status": "historical_diagnostic_test_period_previously_opened",
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "validation_partition": {
                "fit_rows": int(len(fit)),
                "fit_matches": int(fit["match_id"].nunique()),
                "calibration_rows": int(len(calibration)),
                "calibration_matches": int(calibration["match_id"].nunique()),
                "split": "SHA-256 match-level 70/30",
            },
            "selected_policy": selected or {"family": "NO_TRADE_POLICY", "fraction": 0.0},
            "test_policy_metrics": test_metrics,
            "incremental_vs_raw_baseline_20pct": incremental,
            "gate": {
                "checks": gate_checks,
                "promoted_to_prospective_shadow": promoted,
                "decision": (
                    "selective policy promoted to prospective shadow"
                    if promoted
                    else "selective policy not promoted"
                ),
            },
            "evidence_boundary": {
                "match_outcomes_used_for_calibration": False,
                "test_period_previously_opened": True,
                "profit_claim": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )
        print(json.dumps({"selected_policy": report["selected_policy"], "gate": report["gate"]}, indent=2, default=json_default))
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
                default=json_default,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
