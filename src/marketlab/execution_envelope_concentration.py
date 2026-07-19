from __future__ import annotations

from typing import Any

import pandas as pd

from marketlab.execution_envelope_pairing import paired_frame


def incremental_concentration(raw: pd.DataFrame, residual: pd.DataFrame) -> dict[str, Any]:
    joined = paired_frame(raw, residual)
    output: dict[str, Any] = {}
    for label, column in {
        "bookmaker": "bookmaker_name_residual",
        "cutoff": "hours_before_kickoff",
        "outcome": "selected_outcome_residual",
    }.items():
        grouped = joined.groupby(column, sort=True)["incremental_return"].sum()
        positive = grouped[grouped > 0]
        output[label] = {
            "incremental_profit_units": {
                str(key): float(value) for key, value in grouped.items()
            },
            "maximum_positive_contribution_share": (
                float(positive.max() / positive.sum()) if not positive.empty else None
            ),
        }
    return output
