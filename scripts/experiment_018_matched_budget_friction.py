from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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
from marketlab.execution_stress import default_scenarios
from marketlab.json_compat import json_default


CORE_SCENARIOS = (
    "delay_0h__slip_0bps__fill_100pct",
    "delay_1h__slip_25bps__fill_90pct",
    "delay_2h__slip_50bps__fill_75pct",
    "delay_3h__slip_100bps__fill_50pct",
)


def frozen_gate(results: dict[str, Any]) -> dict[str, Any]:
    zero = results[CORE_SCENARIOS[0]]
    practical = results[CORE_SCENARIOS[1]]
    core_incremental = {
        name: float(
            results[name]["incremental_overlay_minus_baseline"][
                "incremental_return_per_opportunity"
            ]
        )
        for name in CORE_SCENARIOS
    }
    concentration = practical["bookmaker_stability"][
        "maximum_positive_book_contribution_share"
    ]
    checks = {
        "residual_zero_friction_roi_positive": (
            zero["rank_only_overlay"]["roi_per_fill"] > 0
        ),
        "residual_practical_roi_positive": (
            practical["rank_only_overlay"]["roi_per_fill"] > 0
        ),
        "zero_friction_incremental_ci_above_zero": (
            zero["incremental_overlay_minus_baseline"][
                "paired_match_bootstrap"
            ]["ci95_low"]
            > 0
        ),
        "practical_incremental_ci_above_zero": (
            practical["incremental_overlay_minus_baseline"][
                "paired_match_bootstrap"
            ]["ci95_low"]
            > 0
        ),
        "incremental_point_positive_all_core_scenarios": all(
            value > 0 for value in core_incremental.values()
        ),
        "practical_positive_book_contribution_not_over_50pct": (
            concentration is not None and concentration <= 0.50
        ),
    }
    return {
        "checks": checks,
        "friction_robust": all(checks.values()),
        "core_incremental_return_per_opportunity": core_incremental,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stress-test matched 5% raw and residual policies under execution frictions."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-018")
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

        progress("rebuilding_frozen_normal_and_residual_state")
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
            source_paths, identity, chunksize=args.chunksize
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

        progress("running_frozen_execution_scenarios")
        scenarios = default_scenarios()
        scenario_results, summary = exp15.run_scenarios(
            raw_settled, residual_settled, scenarios, root
        )
        summary.to_csv(root / "scenario-summary.csv", index=False)
        gate = frozen_gate(scenario_results)

        report = {
            "experiment": "018_matched_budget_execution_friction",
            "status": "completed",
            "evidentiary_status": (
                "historical_diagnostic_test_period_previously_opened"
            ),
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "execution_price_profile": execution_profile,
            "outcome_profile": outcome_profile,
            "frozen_policy": {
                "fraction": exp17.FRACTION,
                "candidate_identity": "raw model fixes bookmaker and outcome",
                "raw_reference": "positive raw score top 5% within cutoff",
                "residual_policy": "positive action-rank score top 5% within cutoff",
                "outcomes_used_for_selection": False,
            },
            "scenarios": scenario_results,
            "frozen_gate": gate,
            "evidence_boundary": {
                "historical_test_period_previously_opened": True,
                "live_fill_evidence": False,
                "account_limit_evidence": False,
                "live_execution_authorized": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "gate": gate,
                    "core": {
                        name: {
                            "raw_roi": scenario_results[name]["baseline"][
                                "roi_per_fill"
                            ],
                            "residual_roi": scenario_results[name][
                                "rank_only_overlay"
                            ]["roi_per_fill"],
                            "incremental": scenario_results[name][
                                "incremental_overlay_minus_baseline"
                            ]["incremental_return_per_opportunity"],
                        }
                        for name in CORE_SCENARIOS
                    },
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
