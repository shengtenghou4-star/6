from __future__ import annotations

import pandas as pd
import pytest

from marketlab.canonical_timing_cohort import (
    EXPECTED_ADAPTER_ID,
    canonical_policy,
    validate_canonical_candidates,
)


def fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "event-1",
                "realized_snapshot_id": "snapshot-1",
                "canonical_timing_adapter_id": EXPECTED_ADAPTER_ID,
                "canonical_timing_activation_utc": "2026-07-19T15:00:00Z",
                "canonical_timing_unvalidated_transfer": True,
                "canonical_timing_research_only": True,
                "canonical_timing_no_execution": True,
            }
        ]
    )


def test_validates_frozen_adapter_identity_and_flags() -> None:
    diagnostics = validate_canonical_candidates(fixture())
    assert diagnostics == {
        "adapter_id": EXPECTED_ADAPTER_ID,
        "activation_utc": "2026-07-19T15:00:00+00:00",
        "rows": 1,
        "events": 1,
        "snapshots": 1,
        "adapter_flags_verified": True,
    }


def test_rejects_mixed_or_wrong_adapter() -> None:
    wrong = fixture().assign(canonical_timing_adapter_id="wrong")
    with pytest.raises(ValueError, match="unexpected canonical-timing adapter"):
        validate_canonical_candidates(wrong)
    mixed = pd.concat(
        [fixture(), fixture().assign(canonical_timing_adapter_id="wrong")]
    )
    with pytest.raises(ValueError, match="multiple adapter"):
        validate_canonical_candidates(mixed)


def test_rejects_wrong_activation_and_false_flags() -> None:
    wrong_activation = fixture().assign(
        canonical_timing_activation_utc="2026-07-19T14:59:00Z"
    )
    with pytest.raises(ValueError, match="unexpected canonical-timing activation"):
        validate_canonical_candidates(wrong_activation)
    false_flag = fixture().assign(canonical_timing_no_execution=False)
    with pytest.raises(ValueError, match="flags are not all true"):
        validate_canonical_candidates(false_flag)


def test_policy_preserves_original_volume_gates() -> None:
    policy = canonical_policy()
    assert policy.activation_utc == "2026-07-19T15:00:00Z"
    assert policy.minimum_candidates == 300
    assert policy.minimum_unique_events == 75
    assert policy.minimum_selected_per_policy == 15
    assert policy.minimum_candidates_per_cutoff == 40
    assert policy.minimum_supported_cutoffs == 3
    assert policy.bootstrap_seed == 20260727
