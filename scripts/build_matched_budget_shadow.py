from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from marketlab.action_shadow import sha256
from marketlab.matched_budget_shadow import (
    MatchedBudgetPolicy,
    build_matched_budget_shadow,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a timestamped matched-budget raw/residual prospective shadow ledger."
    )
    parser.add_argument("--shadow-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--activation-utc", required=True)
    parser.add_argument("--fraction", type=float, default=0.05)
    args = parser.parse_args()

    shadow_root = Path(args.shadow_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    source_manifest_path = shadow_root / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    policy = MatchedBudgetPolicy(
        activation_utc=args.activation_utc,
        fraction=args.fraction,
    )

    if source_manifest.get("status") != "scored":
        manifest = {
            "schema_version": 1,
            "status": "source_not_ready",
            "source_status": source_manifest.get("status"),
            "source_reason": source_manifest.get("reason"),
            "source_manifest": {
                "path": str(source_manifest_path),
                "sha256": sha256(source_manifest_path),
            },
            "policy": {
                "activation_utc": policy.activation_utc,
                "fraction": policy.fraction,
                "raw_policy_id": policy.raw_policy_id,
                "residual_policy_id": policy.residual_policy_id,
                "research_only": True,
                "no_execution": True,
                "match_outcomes_used": False,
            },
            "outputs": {"matched_budget_ledger": {"rows": 0}},
        }
        (output_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return

    candidate_path = shadow_root / str(
        source_manifest["outputs"]["event_candidates"]["path"]
    )
    candidates = pd.read_csv(candidate_path, low_memory=False)
    ledger, diagnostics = build_matched_budget_shadow(candidates, policy)
    ledger_path = output_root / "matched-budget-shadow.csv.gz"
    ledger.to_csv(ledger_path, index=False, compression="gzip")
    manifest = {
        "schema_version": 1,
        "status": "materialized",
        "source": {
            "shadow_manifest": {
                "path": str(source_manifest_path),
                "sha256": sha256(source_manifest_path),
            },
            "event_candidates": {
                "path": str(candidate_path),
                "sha256": sha256(candidate_path),
                "rows": int(len(candidates)),
            },
        },
        "diagnostics": diagnostics,
        "outputs": {
            "matched_budget_ledger": {
                "path": ledger_path.name,
                "sha256": sha256(ledger_path),
                "rows": int(len(ledger)),
            }
        },
        "policy": {
            "research_only": True,
            "no_execution": True,
            "match_outcomes_used": False,
            "retroactive_rows_excluded": True,
            "adaptive_thresholds": False,
        },
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
