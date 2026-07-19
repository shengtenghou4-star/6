from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_synthetic_marb_profile import SyntheticConfig, run_profile
from scripts.validate_benchmark_submission import validate_submission


def test_synthetic_profile_recovers_known_residual_signal() -> None:
    frame, result, submission = run_profile(
        SyntheticConfig(
            opportunities=3000,
            placebo_replicates=99,
            bootstrap_replicates=120,
            seed=20260719,
        )
    )
    mechanism = result["mechanism"]
    assert len(frame) == 3000
    assert result["simulation_only"] is True
    assert result["empirical_transfer_claimed"] is False
    assert mechanism["standardized_uplift_slope"] > 0.08
    assert mechanism["cluster_ci_low"] > 0.05
    assert mechanism["placebo_upper_tail_p"] <= 0.02
    assert mechanism["standardized_uplift_slope"] > mechanism["placebo_q99_slope"]
    assert all(value > 0 for value in result["distribution"]["horizon_slopes"].values())

    validation = validate_submission(submission)
    assert validation["status"] == "passed"
    assert submission["evidence_tier"] == "executed"
    assert submission["prospective_status"] == "not_started"
    assert submission["economic_diagnostic"]["execution_validated"] is False


def test_residual_reranking_preserves_identity_columns() -> None:
    frame, result, _ = run_profile(
        SyntheticConfig(
            opportunities=1200,
            placebo_replicates=19,
            bootstrap_replicates=40,
            seed=123,
        )
    )
    assert frame["agent_id"].notna().all()
    assert frame["instrument_id"].notna().all()
    assert result["controls"]["candidate_identity_fixed"] is True
    assert result["controls"]["same_agent_target"] is True
    assert result["controls"]["post_event_fields_used"] is False
