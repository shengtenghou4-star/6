from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_benchmark_submission import validate_submission


def load_reference() -> dict:
    return json.loads(
        (ROOT / "benchmark" / "reference_submission.json").read_text(encoding="utf-8")
    )


def test_reference_submission_passes_with_expected_warnings() -> None:
    report = validate_submission(load_reference())
    assert report["status"] == "passed"
    assert "economic_execution_not_validated" in report["warnings"]
    assert "prospective_transfer_not_validated" in report["warnings"]


def test_fixed_identity_control_is_mandatory() -> None:
    payload = copy.deepcopy(load_reference())
    payload["controls"]["candidate_identity_fixed"] = False
    report = validate_submission(payload)
    assert report["status"] == "failed"
    assert "control_not_true:candidate_identity_fixed" in report["failures"]


def test_historical_tier_requires_positive_cluster_lower_bound() -> None:
    payload = copy.deepcopy(load_reference())
    payload["task_b"]["cluster_ci_low"] = -0.001
    report = validate_submission(payload)
    assert report["status"] == "failed"
    assert "historical_tier_requires_positive_cluster_lower_bound" in report["failures"]


def test_prospective_promotion_cannot_be_declared_early() -> None:
    payload = copy.deepcopy(load_reference())
    payload["evidence_tier"] = "validated_prospective"
    payload["prospective_status"] = "in_progress"
    report = validate_submission(payload)
    assert report["status"] == "failed"
    assert "prospective_tier_requires_passed_prospective_status" in report["failures"]


def test_operational_candidate_requires_execution_validation() -> None:
    payload = copy.deepcopy(load_reference())
    payload["evidence_tier"] = "operational_candidate"
    payload["prospective_status"] = "passed"
    payload["economic_diagnostic"]["execution_validated"] = False
    report = validate_submission(payload)
    assert report["status"] == "failed"
    assert "operational_tier_requires_execution_validation" in report["failures"]
