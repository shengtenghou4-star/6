from __future__ import annotations

from typing import Any

import pandas as pd

from marketlab.execution_envelope_bootstrap import bootstrap_break_even_frontiers
from marketlab.execution_envelope_concentration import incremental_concentration
from marketlab.execution_envelope_fill import MECHANISMS, EnvelopeSpec, apply_envelope
from marketlab.execution_envelope_pairing import (
    incremental_residual_only_break_even_slippage_bps,
    signed_standalone_break_even_slippage_bps,
)
from marketlab.execution_envelope_returns import ledger_metrics, paired_metrics


def evaluate_envelope(
    raw_settled: pd.DataFrame,
    residual_settled: pd.DataFrame,
    spec: EnvelopeSpec,
    *,
    bootstrap_replicates: int = 0,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    raw = apply_envelope(raw_settled, spec, score_column="baseline_score")
    residual = apply_envelope(residual_settled, spec, score_column="rank_score")
    result: dict[str, Any] = {
        "spec": {
            "name": spec.name,
            "latency_hours": spec.latency_hours,
            "fill_rate": spec.fill_rate,
            "mechanism": spec.mechanism,
            "slippage_bps": spec.slippage_bps,
            "seed": spec.seed,
        },
        "raw": ledger_metrics(raw),
        "residual": ledger_metrics(residual),
        "incremental": paired_metrics(
            raw,
            residual,
            replicates=bootstrap_replicates or None,
            seed=spec.seed,
        ),
        "incremental_residual_only_break_even_slippage": (
            incremental_residual_only_break_even_slippage_bps(raw, residual)
        ),
        "concentration": incremental_concentration(raw, residual),
    }
    if bootstrap_replicates:
        result["break_even_frontier_bootstrap"] = bootstrap_break_even_frontiers(
            raw,
            residual,
            replicates=bootstrap_replicates,
            seed=spec.seed,
        )
    return result, raw, residual


__all__ = [
    "MECHANISMS",
    "EnvelopeSpec",
    "apply_envelope",
    "bootstrap_break_even_frontiers",
    "evaluate_envelope",
    "incremental_residual_only_break_even_slippage_bps",
    "signed_standalone_break_even_slippage_bps",
]
