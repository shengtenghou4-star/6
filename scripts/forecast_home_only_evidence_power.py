from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

import forecast_prospective_evidence_power as base
from marketlab.home_only_power_forecast import (
    HOME_ACTIVATION_UTC,
    filter_home_forecast_candidates,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen outcome-blind evidence forecast on future-only home candidates."
    )
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--simulations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()

    candidate_path = Path(args.candidates)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(candidate_path, low_memory=False)
    filtered, filter_diagnostics = filter_home_forecast_candidates(source)
    filtered_path = output_root / "home-candidates-for-forecast.csv.gz"
    filtered.to_csv(filtered_path, index=False, compression="gzip")

    original_argv = sys.argv
    original_activation = base.POLICY_ACTIVATION
    try:
        base.POLICY_ACTIVATION = pd.Timestamp(HOME_ACTIVATION_UTC)
        sys.argv = [
            "forecast_prospective_evidence_power.py",
            "--candidates",
            str(filtered_path),
            "--output-root",
            str(output_root),
            "--simulations",
            str(args.simulations),
            "--seed",
            str(args.seed),
        ]
        base.main()
    finally:
        sys.argv = original_argv
        base.POLICY_ACTIVATION = original_activation

    result_path = output_root / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["forecast_type"] = "outcome_blind_home_only_evidence_power_forecast"
    result["challenger"] = {
        "id": "home_only_original_v2_candidates",
        "activation_utc": HOME_ACTIVATION_UTC,
        "source_experiment": "experiment_024_post_hoc_diagnostic",
        "confirmatory_status": "future_only_challenger",
    }
    result["home_filter"] = filter_diagnostics
    result["source_input"] = {
        "path": str(candidate_path),
        "rows": int(len(source)),
        "sha256": base.sha256(candidate_path),
    }
    result["evidence_boundary"].update(
        {
            "candidate_outcome_filter": "home",
            "filter_applied_before_forecast": True,
            "existing_volume_gates_changed": False,
            "home_only_policy_changed": False,
        }
    )
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    filtered_path.unlink(missing_ok=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
