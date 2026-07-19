from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import experiment_017_matched_budget_return as exp17
from experiment_023_grid import (
    BOOTSTRAP_FILL_RATE,
    DELAYS,
    FILL_RATES,
    MECHANISMS,
    PRACTICAL_DELAY_HOURS,
    PRACTICAL_FILL_RATE,
    PRACTICAL_SLIPPAGE_BPS,
    run_grid,
    run_practical,
)
from experiment_023_reconstruct import reconstruct_frozen_execution_state
from marketlab.json_compat import json_default

BOOTSTRAP_REPLICATES = 1000


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit exact break-even and adverse-fill execution envelopes."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-023")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    parser.add_argument("--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    ledger_root = root / "practical-ledgers"
    ledger_root.mkdir(parents=True, exist_ok=True)
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
        state = reconstruct_frozen_execution_state(
            root,
            chunksize=args.chunksize,
            hazard_max_train=args.hazard_max_train,
            movement_max_train=args.movement_max_train,
            progress=progress,
        )
        progress("mapping_point_break_even_grid")
        grid_results, grid_summary = run_grid(
            state["raw_settled"],
            state["residual_settled"],
            bootstrap_replicates=args.bootstrap_replicates,
        )
        grid_summary.to_csv(root / "break-even-envelope-summary.csv", index=False)

        progress("running_preregistered_practical_envelopes")
        practical_results, practical_summary, practical_checks = run_practical(
            state["raw_settled"],
            state["residual_settled"],
            ledger_root,
            bootstrap_replicates=args.bootstrap_replicates,
        )
        practical_summary.to_csv(root / "practical-envelope-summary.csv", index=False)
        gate = {
            "checks_by_preregistered_practical_envelope": practical_checks,
            "execution_envelope_validated": any(
                values["pass"] for values in practical_checks.values()
            ),
        }
        report = {
            "experiment": "023_execution_break_even_envelope",
            "status": "completed",
            "evidentiary_status": (
                "historical_execution_diagnostic_on_previously_opened_test_period"
            ),
            **{
                key: state[key]
                for key in (
                    "archive",
                    "training_counts",
                    "normal_state_diagnostics",
                    "closing_price_profile",
                    "execution_price_profile",
                    "outcome_profile",
                )
            },
            "frozen_policy": {
                "fraction": exp17.FRACTION,
                "candidate_identity": "raw model fixes bookmaker and outcome",
                "raw_reference": "positive raw score top 5% within cutoff",
                "residual_policy": "positive action-rank score top 5% within cutoff",
                "attempted_selections_per_policy": int(
                    state["raw_policy"]["traded"].sum()
                ),
                "outcomes_used_for_selection": False,
                "model_refit_or_threshold_tuning_from_result": False,
            },
            "grid": {
                "delays_hours": list(DELAYS),
                "fill_rates": list(FILL_RATES),
                "mechanisms": list(MECHANISMS),
                "point_envelopes": len(grid_results),
                "bootstrap_fill_rate": BOOTSTRAP_FILL_RATE,
                "bootstrap_replicates": args.bootstrap_replicates,
                "bootstrap_scope": "every delay and mechanism at 90% fill",
            },
            "practical_envelope": {
                "delay_hours": PRACTICAL_DELAY_HOURS,
                "fill_rate": PRACTICAL_FILL_RATE,
                "slippage_bps": PRACTICAL_SLIPPAGE_BPS,
                "mechanisms": list(MECHANISMS),
            },
            "gate": gate,
            "grid_results": grid_results,
            "practical_results": practical_results,
            "evidence_boundary": {
                "historical_outcomes_previously_opened": True,
                "actual_account_limits_observed": False,
                "actual_bet_rejections_observed": False,
                "running_prospective_campaign_modified": False,
                "live_execution_authorized": False,
                "profit_claim": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )
        print(json.dumps({"gate": gate}, indent=2, sort_keys=True))
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
