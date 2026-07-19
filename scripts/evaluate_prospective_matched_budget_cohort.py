from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from marketlab.prospective_matched_budget_evaluation import (
    CohortEvaluationPolicy,
    evaluate_frozen_campaign_policies,
    freeze_campaign_cohort_policies,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze and evaluate the campaign-close matched-budget 5% cohort "
            "without match outcomes."
        )
    )
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--closing-targets", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--code-revision", default="unknown")
    parser.add_argument("--data-revision", default="unknown")
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    closing_path = Path(args.closing_targets)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    failure_path = output_root / "failure.json"
    policy = CohortEvaluationPolicy()
    started = datetime.now(UTC)

    try:
        campaign_end = datetime.fromisoformat(
            policy.campaign_end_utc.replace("Z", "+00:00")
        ).astimezone(UTC)
        if started < campaign_end:
            raise RuntimeError(
                "campaign-close evaluation cannot run before the frozen campaign end"
            )

        # Selection phase. The closing-target file is intentionally not read or
        # hashed until both policy ledgers and the freeze manifest are durable.
        candidates = pd.read_csv(candidates_path, low_memory=False)
        raw, residual, freeze_diagnostics = freeze_campaign_cohort_policies(
            candidates, policy
        )
        raw_path = output_root / "raw-policy-before-closing.csv.gz"
        residual_path = output_root / "residual-policy-before-closing.csv.gz"
        raw.to_csv(raw_path, index=False, compression="gzip")
        residual.to_csv(residual_path, index=False, compression="gzip")
        freeze_manifest_path = output_root / "freeze-manifest.json"
        freeze_manifest = {
            "schema_version": 1,
            "status": "policies_frozen_before_closing",
            "frozen_at_utc": datetime.now(UTC).isoformat(),
            "candidate_input": {
                "path": str(candidates_path),
                "rows": int(len(candidates)),
                "sha256": sha256(candidates_path),
            },
            "raw_policy_ledger": {
                "path": raw_path.name,
                "rows": int(len(raw)),
                "selected": int(raw["selected"].sum()),
                "sha256": sha256(raw_path),
            },
            "residual_policy_ledger": {
                "path": residual_path.name,
                "rows": int(len(residual)),
                "selected": int(residual["selected"].sum()),
                "sha256": sha256(residual_path),
            },
            "freeze_diagnostics": freeze_diagnostics,
            "closing_targets_read": False,
            "match_outcomes_used": False,
            "research_only": True,
            "no_execution": True,
        }
        write_json(freeze_manifest_path, freeze_manifest)

        # Evaluation phase begins only after the freeze evidence exists.
        closing = pd.read_csv(closing_path, low_memory=False)
        evaluation_ledger, result = evaluate_frozen_campaign_policies(
            raw, residual, closing, policy
        )
        ledger_path = output_root / "evaluation-ledger.csv.gz"
        result_path = output_root / "result.json"
        evaluation_ledger.to_csv(ledger_path, index=False, compression="gzip")
        result["run"] = {
            "started_at_utc": started.isoformat(),
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "campaign_closed_at_run": True,
            "freeze_manifest_sha256": sha256(freeze_manifest_path),
            "raw_policy_ledger_sha256": sha256(raw_path),
            "residual_policy_ledger_sha256": sha256(residual_path),
        }
        write_json(result_path, result)
        manifest = {
            "schema_version": 1,
            "status": "completed",
            "inputs": {
                "candidates": {
                    "path": str(candidates_path),
                    "rows": int(len(candidates)),
                    "sha256": sha256(candidates_path),
                },
                "closing_targets": {
                    "path": str(closing_path),
                    "rows": int(len(closing)),
                    "sha256": sha256(closing_path),
                },
            },
            "freeze_evidence": {
                "manifest": {
                    "path": freeze_manifest_path.name,
                    "sha256": sha256(freeze_manifest_path),
                },
                "raw_policy_ledger": {
                    "path": raw_path.name,
                    "sha256": sha256(raw_path),
                },
                "residual_policy_ledger": {
                    "path": residual_path.name,
                    "sha256": sha256(residual_path),
                },
            },
            "outputs": {
                "evaluation_ledger": {
                    "path": ledger_path.name,
                    "rows": int(len(evaluation_ledger)),
                    "sha256": sha256(ledger_path),
                },
                "result": {
                    "path": result_path.name,
                    "sha256": sha256(result_path),
                },
            },
            "provenance": {
                "code_revision": args.code_revision,
                "data_revision": args.data_revision,
            },
            "runtime": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "pandas": pd.__version__,
            },
            "outcome_blind": True,
            "profit_claim": False,
            "live_execution_authorized": False,
        }
        write_json(output_root / "manifest.json", manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        write_json(
            failure_path,
            {
                "status": "failed",
                "failed_at_utc": datetime.now(UTC).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "outcome_blind": True,
                "profit_claim": False,
                "live_execution_authorized": False,
            },
        )
        raise


if __name__ == "__main__":
    main()
