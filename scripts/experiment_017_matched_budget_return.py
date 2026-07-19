from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_008_named_book_clv as exp8
import experiment_009_frozen_return_audit as exp9
import experiment_011_closing_line_residual as exp11
import experiment_013_selection_ranking_decomposition as exp13
import experiment_016_selective_abstention as exp16
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import DOWNLOAD_URL, OUTCOMES, SERIES_FILES, download, extract_required
from marketlab.json_compat import json_default


FRACTION = 0.05


def add_probability_clv(
    candidates: pd.DataFrame,
    frame: pd.DataFrame,
    identity: pd.DataFrame,
) -> pd.DataFrame:
    output = candidates.copy()
    positions = identity["source_row"].to_numpy(dtype=int)
    outcomes = identity["selected_outcome_index"].to_numpy(dtype=int)
    observation = frame[[f"observation_p_{outcome}" for outcome in OUTCOMES]].to_numpy(float)
    closing = frame[[f"future_p_{outcome}" for outcome in OUTCOMES]].to_numpy(float)
    output["fair_probability_clv"] = (
        closing[positions, outcomes] - observation[positions, outcomes]
    )
    return output


def apply_raw_policy(frame: pd.DataFrame, fraction: float = FRACTION) -> pd.DataFrame:
    output = frame.copy()
    output["traded"] = False
    for hours in exp11.SIGNAL_HOURS:
        cutoff = output["hours_before_kickoff"] == hours
        count = max(1, int(np.floor(int(cutoff.sum()) * fraction)))
        eligible = output.loc[cutoff & (output["baseline_score"] > 0)].sort_values(
            ["baseline_score", "match_id", "book_slot", "selected_outcome_index"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        output.loc[eligible.index[:count], "traded"] = True
    output["opportunity_log_clv"] = np.where(
        output["traded"], output["log_odds_clv"], 0.0
    )
    output["strategy"] = "raw_positive_top_5pct"
    return output


def positive_profit_concentration(settled: pd.DataFrame) -> dict[str, Any]:
    trades = settled[settled["traded"]].copy()
    by_book = trades.groupby("bookmaker_name")["net_return"].sum().sort_index()
    positive = by_book[by_book > 0]
    return {
        "profit_units_by_bookmaker": {
            str(key): float(value) for key, value in by_book.items()
        },
        "maximum_positive_book_contribution_share": (
            float(positive.max() / positive.sum()) if not positive.empty else None
        ),
    }


def cutoff_positive_count(metrics: dict[str, Any]) -> int:
    return int(
        sum(float(values["roi"]) > 0 for values in metrics["by_cutoff"].values())
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare matched 5% raw and residual historical return policies."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-017")
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
            json.dumps(
                {"stage": stage, **extra},
                indent=2,
                sort_keys=True,
                default=json_default,
            ),
            encoding="utf-8",
        )

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("rebuilding_normal_and_residual_state")
        datasets = residual_gen.build_all_state_records(
            source_paths, chunksize=args.chunksize
        )
        diagnostics = datasets.pop("diagnostics")
        normal_hazard, normal_movement, training_counts = (
            residual_gen.train_frozen_models(
                datasets["train"],
                hazard_max=args.hazard_max_train,
                movement_max=args.movement_max_train,
            )
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
        candidates = add_probability_clv(candidates, test, identity)
        raw_policy = apply_raw_policy(candidates)
        residual_policy = exp16.apply_policy(
            candidates, "positive_rank_score", FRACTION
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

        progress("binding_prices_before_outcomes")
        raw_with_prices = exp9.attach_prices_before_outcomes(raw_policy, test)
        residual_with_prices = exp9.attach_prices_before_outcomes(
            residual_policy, test
        )

        progress("loading_outcomes_after_policy_freeze")
        outcomes, outcome_profile = exp9.load_outcomes(source_paths)
        raw_settled = exp9.settle_after_selection(raw_with_prices, outcomes)
        residual_settled = exp9.settle_after_selection(
            residual_with_prices, outcomes
        )

        progress("computing_matched_budget_return_diagnostic")
        raw_metrics = exp9.strategy_return_metrics(raw_settled)
        residual_metrics = exp9.strategy_return_metrics(residual_settled)
        comparison = exp9.compare_returns(raw_settled, residual_settled)
        raw_concentration = positive_profit_concentration(raw_settled)
        residual_concentration = positive_profit_concentration(residual_settled)
        residual_positive_cutoffs = cutoff_positive_count(residual_metrics)
        residual_roi_bootstrap = residual_metrics["trade_roi_match_bootstrap"]
        paired_bootstrap = comparison["paired_match_bootstrap"]
        checks = {
            "residual_roi_positive": residual_metrics["roi_per_trade"] > 0,
            "residual_roi_ci_above_zero": residual_roi_bootstrap["ci95_low"] > 0,
            "incremental_ci_above_zero": paired_bootstrap["ci95_low"] > 0,
            "residual_positive_at_least_3_of_4_cutoffs": residual_positive_cutoffs >= 3,
            "positive_profit_not_over_50pct_one_book": (
                residual_concentration[
                    "maximum_positive_book_contribution_share"
                ]
                is not None
                and residual_concentration[
                    "maximum_positive_book_contribution_share"
                ]
                <= 0.50
            ),
        }
        report = {
            "experiment": "017_matched_budget_historical_return_diagnostic",
            "status": "completed",
            "evidentiary_status": (
                "historical_diagnostic_test_period_previously_opened"
            ),
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "outcome_profile": outcome_profile,
            "frozen_policy": {
                "fraction": FRACTION,
                "candidate_identity": "raw model fixes bookmaker and outcome",
                "raw_reference": "positive baseline score, top 5% within cutoff",
                "residual_policy": "positive action rank score, top 5% within cutoff",
                "outcomes_used_for_selection": False,
            },
            "raw_reference": {
                "metrics": raw_metrics,
                "positive_profit_concentration": raw_concentration,
            },
            "residual_policy": {
                "metrics": residual_metrics,
                "positive_profit_concentration": residual_concentration,
                "positive_cutoffs": residual_positive_cutoffs,
            },
            "residual_minus_raw": comparison,
            "diagnostic_gate": {
                "checks": checks,
                "economically_encouraging": all(checks.values()),
                "confirmatory": False,
            },
            "execution_assumptions": {
                "stake": "one unit per frozen selection",
                "commission": 0,
                "latency_slippage_rejections_limits": "not modeled",
            },
            "evidence_boundary": {
                "historical_test_period_previously_opened": True,
                "live_execution_authorized": False,
                "guaranteed_return_claim": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )
        raw_settled.to_csv(
            root / "raw-settled.csv.gz", index=False, compression="gzip"
        )
        residual_settled.to_csv(
            root / "residual-settled.csv.gz", index=False, compression="gzip"
        )
        print(
            json.dumps(
                {
                    "raw_roi": raw_metrics["roi_per_trade"],
                    "residual_roi": residual_metrics["roi_per_trade"],
                    "incremental": comparison[
                        "mean_augmented_minus_baseline_return_per_opportunity"
                    ],
                    "gate": report["diagnostic_gate"],
                },
                indent=2,
                default=json_default,
            )
        )
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
