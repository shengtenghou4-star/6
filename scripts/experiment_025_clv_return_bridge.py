from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from experiment_023_reconstruct import reconstruct_frozen_execution_state
from marketlab.clv_return_bridge import OUTCOMES, bridge_by_outcome
from marketlab.execution_envelope import MECHANISMS, EnvelopeSpec, evaluate_envelope
from marketlab.json_compat import json_default

DELAY_HOURS = 1
FILL_RATE = 0.90
SLIPPAGE_BPS = 25.0
SEED = 20260719


def envelope_name(mechanism: str) -> str:
    return f"delay_1h__{mechanism}__fill_90pct__slip_25bps"


def sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare closing-line relative value and realized return by outcome."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-025")
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
        progress("bridging_closing_value_and_realized_return")
        tables: list[pd.DataFrame] = []
        summaries: dict[str, Any] = {}
        for mechanism_index, mechanism in enumerate(MECHANISMS):
            _result, raw_ledger, residual_ledger = evaluate_envelope(
                state["raw_settled"],
                state["residual_settled"],
                EnvelopeSpec(
                    name=envelope_name(mechanism),
                    latency_hours=DELAY_HOURS,
                    fill_rate=FILL_RATE,
                    mechanism=mechanism,
                    slippage_bps=SLIPPAGE_BPS,
                    seed=SEED,
                ),
                bootstrap_replicates=0,
            )
            table, summary = bridge_by_outcome(
                raw_ledger,
                residual_ledger,
                replicates=args.bootstrap_replicates,
                seed=SEED + mechanism_index * 100,
            )
            table.insert(0, "mechanism", mechanism)
            tables.append(table)
            summaries[mechanism] = summary

        bridge = pd.concat(tables, ignore_index=True)
        bridge.to_csv(root / "clv-return-bridge-by-outcome.csv", index=False)

        classification: dict[str, Any] = {}
        for outcome in OUTCOMES:
            group = bridge[bridge["outcome"] == outcome]
            realized = group["incremental_realized_contribution_units"]
            closing = group["incremental_closing_value_contribution_units"]
            residual_closing = group["residual_closing_value_contribution_units"]
            classification[outcome] = {
                "incremental_realized_positive_mechanisms": int((realized > 0).sum()),
                "incremental_closing_value_positive_mechanisms": int(
                    (closing > 0).sum()
                ),
                "residual_closing_value_positive_mechanisms": int(
                    (residual_closing > 0).sum()
                ),
                "realized_vs_closing_sign_divergence_mechanisms": int(
                    sum(sign(a) != sign(b) for a, b in zip(realized, closing, strict=True))
                ),
            }
        away = bridge[bridge["outcome"] == "away"]
        draw = bridge[bridge["outcome"] == "draw"]
        classification["away_closing_positive_realized_negative_count"] = int(
            (
                (away["incremental_closing_value_contribution_units"] > 0)
                & (away["incremental_realized_contribution_units"] < 0)
            ).sum()
        )
        classification["draw_incremental_closing_negative_count"] = int(
            (draw["incremental_closing_value_contribution_units"] < 0).sum()
        )
        classification["home_concentration_fully_explained_by_closing_value"] = bool(
            classification["away_closing_positive_realized_negative_count"] == 0
        )

        report = {
            "experiment": "025_clv_return_bridge_by_outcome",
            "status": "completed",
            "evidentiary_status": "post_hoc_historical_diagnostic",
            "archive": state["archive"],
            "training_counts": state["training_counts"],
            "execution_price_profile": state["execution_price_profile"],
            "outcome_profile": state["outcome_profile"],
            "practical_envelope": {
                "latency_hours": DELAY_HOURS,
                "fill_rate": FILL_RATE,
                "slippage_bps": SLIPPAGE_BPS,
                "mechanisms": list(MECHANISMS),
            },
            "closing_value_definition": (
                "filled * (executed_decimal_odds / closing_decimal_odds - 1)"
            ),
            "bootstrap_replicates": int(args.bootstrap_replicates),
            "mechanisms": summaries,
            "classification": classification,
            "evidence_boundary": {
                "historical_test_period_previously_opened": True,
                "post_hoc_after_outcome_concentration": True,
                "selected_outcome_policy_change_authorized": False,
                "live_execution_authorized": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=json_default),
            encoding="utf-8",
        )
        print(json.dumps(classification, indent=2, sort_keys=True))
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
