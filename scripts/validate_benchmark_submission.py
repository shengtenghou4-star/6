from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TIERS = [
    "implemented",
    "executed",
    "replicated_historical",
    "validated_prospective",
    "operational_candidate",
]
CONTROL_FIELDS = (
    "chronology_locked",
    "candidate_identity_fixed",
    "future_targets_loaded_after_selection",
    "same_agent_future_target",
    "post_event_fields_forbidden",
)


def _require(mapping: dict[str, Any], fields: tuple[str, ...], prefix: str) -> list[str]:
    return [f"missing:{prefix}{field}" for field in fields if field not in mapping]


def validate_submission(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []

    required = (
        "schema_version",
        "submission_id",
        "domain_profile",
        "evidence_tier",
        "model",
        "data",
        "controls",
        "task_b",
        "distribution",
        "economic_diagnostic",
        "prospective_status",
        "prohibited_claims_acknowledged",
    )
    failures.extend(_require(payload, required, ""))
    if failures:
        return {"status": "failed", "failures": failures, "warnings": warnings}

    if payload["schema_version"] != 1:
        failures.append("unsupported_schema_version")
    tier = payload["evidence_tier"]
    if tier not in TIERS:
        failures.append(f"invalid_evidence_tier:{tier}")

    model = payload["model"]
    failures.extend(_require(model, ("model_id", "code_ref", "artifact_sha256"), "model."))
    digest = str(model.get("artifact_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        failures.append("invalid_model_artifact_sha256")

    data = payload["data"]
    failures.extend(
        _require(
            data,
            ("opportunities", "entities", "agents", "horizons", "test_start", "test_end"),
            "data.",
        )
    )
    for field in ("opportunities", "entities", "agents", "horizons"):
        if int(data.get(field, 0)) <= 0:
            failures.append(f"nonpositive:data.{field}")
    if str(data.get("test_start", "")) >= str(data.get("test_end", "")):
        failures.append("invalid_test_date_order")

    controls = payload["controls"]
    failures.extend(_require(controls, CONTROL_FIELDS, "controls."))
    for field in CONTROL_FIELDS:
        if controls.get(field) is not True:
            failures.append(f"control_not_true:{field}")

    task = payload["task_b"]
    task_fields = (
        "standardized_uplift_slope",
        "cluster_ci_low",
        "cluster_ci_high",
        "placebo_replicates",
        "placebo_upper_tail_p",
        "top_minus_bottom",
    )
    failures.extend(_require(task, task_fields, "task_b."))
    if float(task.get("cluster_ci_low", 0)) > float(task.get("cluster_ci_high", 0)):
        failures.append("invalid_task_b_interval")
    p_value = float(task.get("placebo_upper_tail_p", -1))
    if not 0 <= p_value <= 1:
        failures.append("invalid_placebo_p")
    if int(task.get("placebo_replicates", 0)) < 1:
        failures.append("invalid_placebo_replicates")

    distribution = payload["distribution"]
    distribution_fields = (
        "positive_agents",
        "total_agents",
        "positive_instruments",
        "total_instruments",
        "positive_horizons",
        "total_horizons",
        "leave_one_agent_out_min_ci_low",
    )
    failures.extend(_require(distribution, distribution_fields, "distribution."))
    for positive, total in (
        ("positive_agents", "total_agents"),
        ("positive_instruments", "total_instruments"),
        ("positive_horizons", "total_horizons"),
    ):
        if int(distribution.get(positive, 0)) > int(distribution.get(total, 0)):
            failures.append(f"distribution_count_exceeds_total:{positive}")

    economic = payload["economic_diagnostic"]
    economic_fields = (
        "raw_roi",
        "residual_roi",
        "paired_ci_low_per_opportunity",
        "paired_ci_high_per_opportunity",
        "positive_execution_cells",
        "total_execution_cells",
        "execution_validated",
    )
    failures.extend(_require(economic, economic_fields, "economic_diagnostic."))
    if float(economic.get("paired_ci_low_per_opportunity", 0)) > float(
        economic.get("paired_ci_high_per_opportunity", 0)
    ):
        failures.append("invalid_economic_interval")
    if int(economic.get("positive_execution_cells", 0)) > int(
        economic.get("total_execution_cells", 0)
    ):
        failures.append("positive_execution_cells_exceed_total")

    prospective = payload["prospective_status"]
    if prospective not in {"not_started", "in_progress", "failed", "inconclusive", "passed"}:
        failures.append(f"invalid_prospective_status:{prospective}")
    if payload["prohibited_claims_acknowledged"] is not True:
        failures.append("prohibited_claims_not_acknowledged")

    tier_index = TIERS.index(tier) if tier in TIERS else -1
    if tier_index >= TIERS.index("replicated_historical"):
        if float(task.get("standardized_uplift_slope", 0)) <= 0:
            failures.append("historical_tier_requires_positive_slope")
        if float(task.get("cluster_ci_low", 0)) <= 0:
            failures.append("historical_tier_requires_positive_cluster_lower_bound")
        if p_value > 0.01:
            failures.append("historical_tier_requires_placebo_p_at_most_0.01")
        if float(distribution.get("leave_one_agent_out_min_ci_low", 0)) <= 0:
            failures.append("historical_tier_requires_leave_one_agent_out_support")

    if tier_index >= TIERS.index("validated_prospective") and prospective != "passed":
        failures.append("prospective_tier_requires_passed_prospective_status")
    if tier == "operational_candidate" and economic.get("execution_validated") is not True:
        failures.append("operational_tier_requires_execution_validation")

    if economic.get("execution_validated") is False:
        warnings.append("economic_execution_not_validated")
    if prospective != "passed":
        warnings.append("prospective_transfer_not_validated")

    return {
        "schema_version": 1,
        "submission_id": payload.get("submission_id"),
        "evidence_tier": tier,
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission")
    parser.add_argument("--output")
    args = parser.parse_args()

    path = Path(args.submission)
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = validate_submission(payload)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
