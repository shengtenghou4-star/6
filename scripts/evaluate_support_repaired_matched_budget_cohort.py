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


EXPECTED_ADAPTER_ID = "support_constrained_coverage_normalized_v1"
SUPPORT_FLAGS = (
    "support_repair_unvalidated_transfer",
    "support_repair_research_only",
    "support_repair_no_execution",
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


def truthy(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "yes"}


def validate_support_repaired_candidates(candidates: pd.DataFrame) -> dict[str, Any]:
    required = ["support_repair_adapter_id", "support_repair_activation_utc", *SUPPORT_FLAGS]
    missing = sorted(set(required) - set(candidates.columns))
    if missing:
        raise ValueError(f"support-repaired candidates missing columns: {missing}")
    if candidates.empty:
        raise RuntimeError("support-repaired candidate file is empty")
    if candidates["support_repair_adapter_id"].nunique(dropna=False) != 1:
        raise ValueError("support-repaired cohort contains multiple adapter IDs")
    adapter_id = str(candidates["support_repair_adapter_id"].iloc[0])
    if adapter_id != EXPECTED_ADAPTER_ID:
        raise ValueError(f"unexpected support-repair adapter ID: {adapter_id}")
    flags = candidates[list(SUPPORT_FLAGS)].apply(lambda column: column.map(truthy))
    if not flags.all().all():
        raise ValueError("support-repair evidence flags are not all true")
    activation = pd.to_datetime(
        candidates["support_repair_activation_utc"], utc=True, errors="coerce"
    )
    if activation.isna().any() or activation.nunique() != 1:
        raise ValueError("support-repair activation boundary is invalid or mixed")
    expected_activation = pd.Timestamp("2026-07-19T12:00:00Z")
    if activation.iloc[0] != expected_activation:
        raise ValueError(
            f"unexpected support-repair activation: {activation.iloc[0].isoformat()}"
        )
    return {
        "adapter_id": adapter_id,
        "activation_utc": activation.iloc[0].isoformat(),
        "rows": int(len(candidates)),
        "events": int(candidates["event_id"].nunique()),
        "snapshots": int(candidates["realized_snapshot_id"].nunique()),
        "support_flags_verified": True,
    }


def repaired_policy() -> CohortEvaluationPolicy:
    return CohortEvaluationPolicy(
        activation_utc="2026-07-19T12:00:00Z",
        campaign_end_utc="2026-07-26T06:30:00Z",
        minimum_collection_lead_hours=3.25,
        fraction=0.05,
        raw_policy_id="raw_positive_top_5pct_support_repaired_cohort_v1",
        residual_policy_id="residual_positive_top_5pct_support_repaired_cohort_v1",
        minimum_candidates=300,
        minimum_unique_events=75,
        minimum_selected_per_policy=15,
        minimum_candidates_per_cutoff=40,
        minimum_supported_cutoffs=3,
        maximum_positive_book_contribution_share=0.50,
        bootstrap_replicates=4000,
        bootstrap_seed=20260727,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze and evaluate the support-repaired matched-budget 5% cohort "
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
    policy = repaired_policy()
    started = datetime.now(UTC)

    try:
        campaign_end = datetime.fromisoformat(
            policy.campaign_end_utc.replace("Z", "+00:00")
        ).astimezone(UTC)
        if started < campaign_end:
            raise RuntimeError(
                "support-repaired campaign-close evaluation cannot run before "
                "the frozen campaign end"
            )

        # The candidate file is read and validated first. Closing targets are not
        # touched until both complete policy ledgers and the freeze manifest exist.
        candidates = pd.read_csv(candidates_path, low_memory=False)
        repair_validation = validate_support_repaired_candidates(candidates)
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
            "status": "support_repaired_policies_frozen_before_closing",
            "frozen_at_utc": datetime.now(UTC).isoformat(),
            "adapter_validation": repair_validation,
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
            "original_v2_evaluation_replaced": False,
        }
        write_json(freeze_manifest_path, freeze_manifest)

        closing = pd.read_csv(closing_path, low_memory=False)
        evaluation_ledger, result = evaluate_frozen_campaign_policies(
            raw, residual, closing, policy
        )
        ledger_path = output_root / "evaluation-ledger.csv.gz"
        result_path = output_root / "result.json"
        evaluation_ledger.to_csv(ledger_path, index=False, compression="gzip")
        result["support_repair"] = repair_validation
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
            "adapter_id": EXPECTED_ADAPTER_ID,
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
            "original_v2_evaluation_replaced": False,
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
                "adapter_id": EXPECTED_ADAPTER_ID,
                "outcome_blind": True,
                "profit_claim": False,
                "live_execution_authorized": False,
            },
        )
        raise


if __name__ == "__main__":
    main()
