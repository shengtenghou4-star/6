from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from experiment_023_reconstruct import reconstruct_frozen_execution_state
from marketlab.execution_envelope import MECHANISMS, EnvelopeSpec, evaluate_envelope
from marketlab.json_compat import json_default
from marketlab.outcome_execution_attribution import attribute_outcome_execution

PRACTICAL_DELAY_HOURS = 1
PRACTICAL_FILL_RATE = 0.90
PRACTICAL_SLIPPAGE_BPS = 25.0
SEED = 20260719


def envelope_name(mechanism: str) -> str:
    return f"delay_1h__{mechanism}__fill_90pct__slip_25bps"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Attribute the practical execution bottleneck by selected outcome."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-024")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
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
        state = reconstruct_frozen_execution_state(
            root,
            chunksize=args.chunksize,
            hazard_max_train=args.hazard_max_train,
            movement_max_train=args.movement_max_train,
            progress=progress,
        )
        progress("running_outcome_attribution")
        tables: list[pd.DataFrame] = []
        mechanisms: dict[str, Any] = {}
        for index, mechanism in enumerate(MECHANISMS):
            name = envelope_name(mechanism)
            _result, raw_ledger, residual_ledger = evaluate_envelope(
                state["raw_settled"],
                state["residual_settled"],
                EnvelopeSpec(
                    name=name,
                    latency_hours=PRACTICAL_DELAY_HOURS,
                    fill_rate=PRACTICAL_FILL_RATE,
                    mechanism=mechanism,
                    slippage_bps=PRACTICAL_SLIPPAGE_BPS,
                    seed=SEED,
                ),
                bootstrap_replicates=0,
            )
            table, summary = attribute_outcome_execution(
                raw_ledger,
                residual_ledger,
                replicates=args.bootstrap_replicates,
                seed=SEED + index * 100,
            )
            table.insert(0, "mechanism", mechanism)
            tables.append(table)
            mechanisms[mechanism] = summary

        attribution = pd.concat(tables, ignore_index=True)
        attribution_path = root / "outcome-attribution.csv"
        attribution.to_csv(attribution_path, index=False)

        non_home = attribution[attribution["group"] == "non_home"]
        without_home = attribution[attribution["group"] == "without_home"]
        home = attribution[
            (attribution["group_kind"] == "outcome")
            & (attribution["group"] == "home")
        ]
        draw = attribution[
            (attribution["group_kind"] == "outcome")
            & (attribution["group"] == "draw")
        ]
        away = attribution[
            (attribution["group_kind"] == "outcome")
            & (attribution["group"] == "away")
        ]
        classification = {
            "home_incremental_positive_mechanisms": int(
                (home["incremental_profit_units"] > 0).sum()
            ),
            "draw_incremental_positive_mechanisms": int(
                (draw["incremental_profit_units"] > 0).sum()
            ),
            "away_incremental_positive_mechanisms": int(
                (away["incremental_profit_units"] > 0).sum()
            ),
            "non_home_incremental_positive_mechanisms": int(
                (non_home["incremental_profit_units"] > 0).sum()
            ),
            "without_home_incremental_positive_mechanisms": int(
                (without_home["incremental_profit_units"] > 0).sum()
            ),
            "without_home_ci_above_zero_mechanisms": int(
                (without_home["incremental_ci95_low"] > 0).sum()
            ),
        }
        classification["outcome_execution_broadly_distributed"] = bool(
            classification["non_home_incremental_positive_mechanisms"] == 4
            and classification["without_home_incremental_positive_mechanisms"] == 4
            and classification["without_home_ci_above_zero_mechanisms"] >= 1
        )
        classification["home_dependent_point_attribution"] = bool(
            classification["home_incremental_positive_mechanisms"] == 4
            and classification["without_home_incremental_positive_mechanisms"] <= 1
        )

        report = {
            "experiment": "024_outcome_execution_attribution",
            "status": "completed",
            "evidentiary_status": "post_hoc_historical_diagnostic",
            "archive": state["archive"],
            "training_counts": state["training_counts"],
            "execution_price_profile": state["execution_price_profile"],
            "outcome_profile": state["outcome_profile"],
            "practical_envelope": {
                "latency_hours": PRACTICAL_DELAY_HOURS,
                "fill_rate": PRACTICAL_FILL_RATE,
                "slippage_bps": PRACTICAL_SLIPPAGE_BPS,
                "mechanisms": list(MECHANISMS),
            },
            "bootstrap_replicates": int(args.bootstrap_replicates),
            "mechanisms": mechanisms,
            "classification": classification,
            "evidence_boundary": {
                "historical_test_period_previously_opened": True,
                "post_hoc_after_concentration_warning": True,
                "strategy_change_authorized": False,
                "profit_claim": False,
                "live_execution_authorized": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )
        print(json.dumps(report["classification"], indent=2, sort_keys=True))
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
