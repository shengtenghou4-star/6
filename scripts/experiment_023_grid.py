from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from marketlab.execution_envelope import MECHANISMS, EnvelopeSpec, evaluate_envelope

DELAYS = (0, 1, 2, 3)
FILL_RATES = (1.0, 0.9, 0.75, 0.5)
BOOTSTRAP_FILL_RATE = 0.9
PRACTICAL_DELAY_HOURS = 1
PRACTICAL_FILL_RATE = 0.9
PRACTICAL_SLIPPAGE_BPS = 25.0
SEED = 20260719


def spec_name(delay: int, mechanism: str, fill_rate: float, slippage_bps: float) -> str:
    return (
        f"delay_{delay}h__{mechanism}__fill_{int(round(fill_rate * 100))}pct"
        f"__slip_{int(round(slippage_bps))}bps"
    )


def flatten_result(result: dict[str, Any]) -> dict[str, Any]:
    bootstrap = result.get("break_even_frontier_bootstrap", {})
    standalone = bootstrap.get("standalone_residual", {})
    incremental_bootstrap = bootstrap.get("incremental_residual_only", {})
    incremental_break_even = result["incremental_residual_only_break_even_slippage"]
    return {
        **result["spec"],
        "raw_fills": result["raw"]["fills"],
        "raw_profit_units": result["raw"]["profit_units"],
        "raw_roi_per_fill": result["raw"]["roi_per_fill"],
        "residual_fills": result["residual"]["fills"],
        "residual_profit_units": result["residual"]["profit_units"],
        "residual_roi_per_fill": result["residual"]["roi_per_fill"],
        "incremental_profit_units": result["incremental"]["incremental_profit_units"],
        "incremental_return_per_opportunity": result["incremental"][
            "incremental_return_per_opportunity"
        ],
        "residual_break_even_slippage_bps": result["residual"][
            "signed_additional_break_even_slippage_bps"
        ],
        "incremental_break_even_slippage_bps": incremental_break_even["value_bps"],
        "incremental_break_even_status": incremental_break_even["status"],
        "standalone_break_even_ci95_low": standalone.get("ci95_low"),
        "standalone_break_even_ci95_high": standalone.get("ci95_high"),
        "incremental_break_even_ci95_low": incremental_bootstrap.get("ci95_low"),
        "incremental_break_even_ci95_high": incremental_bootstrap.get("ci95_high"),
        "incremental_ci95_low": result["incremental"]
        .get("paired_event_cluster_bootstrap", {})
        .get("ci95_low"),
        "incremental_ci95_high": result["incremental"]
        .get("paired_event_cluster_bootstrap", {})
        .get("ci95_high"),
        "max_positive_book_share": result["concentration"]["bookmaker"][
            "maximum_positive_contribution_share"
        ],
        "max_positive_cutoff_share": result["concentration"]["cutoff"][
            "maximum_positive_contribution_share"
        ],
        "max_positive_outcome_share": result["concentration"]["outcome"][
            "maximum_positive_contribution_share"
        ],
    }


def run_grid(
    raw_settled: pd.DataFrame,
    residual_settled: pd.DataFrame,
    *,
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    results: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for delay in DELAYS:
        for mechanism in MECHANISMS:
            for fill_rate in FILL_RATES:
                name = spec_name(delay, mechanism, fill_rate, 0.0)
                result, _raw, _residual = evaluate_envelope(
                    raw_settled,
                    residual_settled,
                    EnvelopeSpec(name, delay, fill_rate, mechanism, 0.0, SEED),
                    bootstrap_replicates=(
                        bootstrap_replicates
                        if fill_rate == BOOTSTRAP_FILL_RATE
                        else 0
                    ),
                )
                results[name] = result
                rows.append(flatten_result(result))
    summary = pd.DataFrame(rows).sort_values(
        ["latency_hours", "mechanism", "fill_rate"],
        ascending=[True, True, False],
        kind="mergesort",
    )
    return results, summary


def run_practical(
    raw_settled: pd.DataFrame,
    residual_settled: pd.DataFrame,
    ledger_root: Path,
    *,
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    results: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    for mechanism in MECHANISMS:
        name = spec_name(
            PRACTICAL_DELAY_HOURS,
            mechanism,
            PRACTICAL_FILL_RATE,
            PRACTICAL_SLIPPAGE_BPS,
        )
        result, raw_ledger, residual_ledger = evaluate_envelope(
            raw_settled,
            residual_settled,
            EnvelopeSpec(
                name,
                PRACTICAL_DELAY_HOURS,
                PRACTICAL_FILL_RATE,
                mechanism,
                PRACTICAL_SLIPPAGE_BPS,
                SEED,
            ),
            bootstrap_replicates=bootstrap_replicates,
        )
        results[name] = result
        row = flatten_result(result)
        roi_positive = bool(
            row["residual_roi_per_fill"] is not None
            and row["residual_roi_per_fill"] > 0
        )
        ci_positive = bool(
            row["incremental_ci95_low"] is not None
            and row["incremental_ci95_low"] > 0
        )
        row.update(
            residual_roi_positive=roi_positive,
            incremental_ci_above_zero=ci_positive,
            practical_envelope_pass=roi_positive and ci_positive,
        )
        rows.append(row)
        checks[mechanism] = {
            "residual_roi_positive": roi_positive,
            "incremental_ci_above_zero": ci_positive,
            "pass": roi_positive and ci_positive,
        }
        raw_ledger.to_csv(
            ledger_root / f"{name}__raw.csv.gz", index=False, compression="gzip"
        )
        residual_ledger.to_csv(
            ledger_root / f"{name}__residual.csv.gz",
            index=False,
            compression="gzip",
        )
    return results, pd.DataFrame(rows).sort_values("mechanism"), checks
