from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from marketlab.action_shadow_schema import sha256
from marketlab.canonical_timing_cohort import EXPECTED_ADAPTER_ID as CANONICAL_ID
from marketlab.prospective_adapter_coverage import audit_adapter_coverage

SUPPORT_ID = "support_constrained_coverage_normalized_v1"


def require_single_value(frame: pd.DataFrame, column: str, expected: str) -> None:
    if column not in frame.columns:
        raise ValueError(f"missing adapter column: {column}")
    values = frame[column].astype(str).unique().tolist()
    if values != [expected]:
        raise ValueError(f"unexpected {column}: {values}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit outcome-blind candidate coverage across prospective adapters.")
    parser.add_argument("--original", required=True)
    parser.add_argument("--support-repaired", required=True)
    parser.add_argument("--canonical-timing", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--common-activation-utc", default="2026-07-19T15:00:00Z")
    args = parser.parse_args()

    paths = {
        "original": Path(args.original),
        "support_repaired": Path(args.support_repaired),
        "canonical_timing": Path(args.canonical_timing),
    }
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    failure_path = output_root / "failure.json"
    try:
        frames = {name: pd.read_csv(path, low_memory=False) for name, path in paths.items()}
        require_single_value(
            frames["support_repaired"],
            "support_repair_adapter_id",
            SUPPORT_ID,
        )
        require_single_value(
            frames["canonical_timing"],
            "canonical_timing_adapter_id",
            CANONICAL_ID,
        )
        result, filtered = audit_adapter_coverage(
            frames["original"],
            frames["support_repaired"],
            frames["canonical_timing"],
            args.common_activation_utc,
        )
        result["inputs"] = {
            name: {
                "path": str(path),
                "rows": int(len(frames[name])),
                "sha256": sha256(path),
            }
            for name, path in paths.items()
        }
        result["adapter_ids"] = {
            "support_repaired": SUPPORT_ID,
            "canonical_timing": CANONICAL_ID,
        }
        profile_rows = []
        for name, profile in result["streams"].items():
            profile_rows.append(
                {
                    "stream": name,
                    "rows": profile["rows"],
                    "events": profile["events"],
                    "snapshots": profile["snapshots"],
                }
            )
        profile_path = output_root / "stream-profile.csv"
        pd.DataFrame(profile_rows).to_csv(profile_path, index=False)
        result_path = output_root / "result.json"
        write_json(result_path, result)
        manifest = {
            "schema_version": 1,
            "status": "completed",
            "common_activation_utc": result["common_activation_utc"],
            "inputs": result["inputs"],
            "outputs": {
                "result": {"path": result_path.name, "sha256": sha256(result_path)},
                "stream_profile": {
                    "path": profile_path.name,
                    "rows": len(profile_rows),
                    "sha256": sha256(profile_path),
                },
            },
            "outcome_blind": True,
            "closing_targets_used": False,
            "match_outcomes_used": False,
            "adapter_changes_authorized": False,
        }
        write_json(output_root / "manifest.json", manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
    except Exception as exc:
        write_json(
            failure_path,
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "outcome_blind": True,
            },
        )
        raise


if __name__ == "__main__":
    main()
