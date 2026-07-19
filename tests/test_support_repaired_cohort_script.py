from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "evaluate_support_repaired_matched_budget_cohort.py"
SPEC = importlib.util.spec_from_file_location("support_repaired_eval_script", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "event-1",
                "realized_snapshot_id": "snapshot-1",
                "support_repair_adapter_id": MODULE.EXPECTED_ADAPTER_ID,
                "support_repair_activation_utc": "2026-07-19T12:00:00Z",
                "support_repair_unvalidated_transfer": True,
                "support_repair_research_only": True,
                "support_repair_no_execution": True,
            }
        ]
    )


def test_validates_frozen_adapter_identity_and_flags() -> None:
    diagnostics = MODULE.validate_support_repaired_candidates(fixture())
    assert diagnostics == {
        "adapter_id": MODULE.EXPECTED_ADAPTER_ID,
        "activation_utc": "2026-07-19T12:00:00+00:00",
        "rows": 1,
        "events": 1,
        "snapshots": 1,
        "support_flags_verified": True,
    }


def test_rejects_mixed_or_wrong_adapter() -> None:
    wrong = fixture().assign(support_repair_adapter_id="wrong")
    with pytest.raises(ValueError, match="unexpected support-repair adapter"):
        MODULE.validate_support_repaired_candidates(wrong)
    mixed = pd.concat([fixture(), fixture().assign(support_repair_adapter_id="wrong")])
    with pytest.raises(ValueError, match="multiple adapter"):
        MODULE.validate_support_repaired_candidates(mixed)


def test_rejects_wrong_activation_and_false_flags() -> None:
    wrong_activation = fixture().assign(
        support_repair_activation_utc="2026-07-19T11:00:00Z"
    )
    with pytest.raises(ValueError, match="unexpected support-repair activation"):
        MODULE.validate_support_repaired_candidates(wrong_activation)
    false_flag = fixture().assign(support_repair_no_execution=False)
    with pytest.raises(ValueError, match="flags are not all true"):
        MODULE.validate_support_repaired_candidates(false_flag)


def test_repaired_policy_preserves_original_volume_gates() -> None:
    policy = MODULE.repaired_policy()
    assert policy.activation_utc == "2026-07-19T12:00:00Z"
    assert policy.minimum_candidates == 300
    assert policy.minimum_unique_events == 75
    assert policy.minimum_selected_per_policy == 15
    assert policy.minimum_candidates_per_cutoff == 40
    assert policy.minimum_supported_cutoffs == 3
    assert policy.bootstrap_seed == 20260727
