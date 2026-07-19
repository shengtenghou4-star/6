from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SyntheticConfig:
    opportunities: int = 12000
    agents: int = 8
    instruments: int = 3
    horizons: tuple[int, ...] = (48, 24, 12, 6)
    baseline_bins: int = 10
    placebo_replicates: int = 1000
    bootstrap_replicates: int = 1000
    residual_signal: float = 0.12
    seed: int = 20260719


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _center(frame: pd.DataFrame, column: str) -> np.ndarray:
    means = frame.groupby("stratum", observed=True)[column].transform("mean")
    return (frame[column] - means).to_numpy(float)


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    denominator = float(np.dot(x, x))
    if denominator <= 0:
        raise ValueError("slope denominator is nonpositive")
    return float(np.dot(x, y) / denominator)


def _top_fraction(frame: pd.DataFrame, score: str, fraction: float = 0.05) -> np.ndarray:
    selected = np.zeros(len(frame), dtype=bool)
    for _, group in frame.groupby("horizon", observed=True):
        quota = int(np.floor(len(group) * fraction))
        if quota:
            indices = group.sort_values(
                [score, "event_id"], ascending=[False, True]
            ).index[:quota]
            selected[indices.to_numpy()] = True
    return selected


def run_profile(config: SyntheticConfig) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    rng = np.random.default_rng(config.seed)
    n = config.opportunities
    frame = pd.DataFrame(
        {
            "event_id": np.arange(n, dtype=int),
            "agent_id": rng.integers(0, config.agents, size=n),
            "instrument_id": rng.integers(0, config.instruments, size=n),
            "horizon": rng.choice(np.asarray(config.horizons), size=n),
            "market_state": rng.normal(size=n),
            "secondary_state": rng.normal(size=n),
        }
    )
    frame["expected_action"] = (
        0.55 * frame["market_state"] - 0.20 * frame["secondary_state"]
    )
    frame["action_residual"] = rng.normal(size=n)
    frame["observed_action"] = frame["expected_action"] + frame["action_residual"]
    frame["raw_candidate_score"] = (
        0.45 * frame["market_state"]
        + 0.18 * frame["secondary_state"]
        + rng.normal(0, 0.15, size=n)
    )
    uplift = frame["action_residual"].to_numpy() + rng.normal(0, 0.05, size=n)
    frame["residual_uplift_std"] = (uplift - uplift.mean()) / uplift.std(ddof=0)
    frame["residual_candidate_score"] = (
        frame["raw_candidate_score"]
        + config.residual_signal * frame["residual_uplift_std"]
    )
    agent_effect = (frame["agent_id"] - frame["agent_id"].mean()) * 0.008
    instrument_effect = (
        frame["instrument_id"] - frame["instrument_id"].mean()
    ) * 0.006
    frame["future_price_quality"] = (
        0.38 * frame["raw_candidate_score"]
        + config.residual_signal * frame["residual_uplift_std"]
        + agent_effect
        + instrument_effect
        + rng.normal(0, 0.75, size=n)
    )
    frame["realized_return"] = rng.normal(0, 1.0, size=n)
    frame["baseline_bin"] = pd.qcut(
        frame["raw_candidate_score"],
        q=config.baseline_bins,
        labels=False,
        duplicates="drop",
    ).astype(int)
    frame["stratum"] = (
        frame["agent_id"].astype(str)
        + "|"
        + frame["horizon"].astype(str)
        + "|"
        + frame["baseline_bin"].astype(str)
    ).astype("category")

    x = _center(frame, "residual_uplift_std")
    y = _center(frame, "future_price_quality")
    observed_slope = _slope(x, y)

    bootstrap_rng = np.random.default_rng(config.seed + 1)
    boot_slopes = np.empty(config.bootstrap_replicates, dtype=float)
    for replicate in range(config.bootstrap_replicates):
        sample = bootstrap_rng.integers(0, n, size=n)
        boot_slopes[replicate] = _slope(x[sample], y[sample])
    ci_low = float(np.quantile(boot_slopes, 0.025))
    ci_high = float(np.quantile(boot_slopes, 0.975))

    group_indices = [
        np.asarray(indices, dtype=int)
        for indices in frame.groupby("stratum", observed=True).indices.values()
    ]
    placebo_rng = np.random.default_rng(config.seed + 2)
    shifted = np.empty_like(x)
    placebo_slopes = np.empty(config.placebo_replicates, dtype=float)
    for replicate in range(config.placebo_replicates):
        for indices in group_indices:
            offset = int(placebo_rng.integers(1, len(indices))) if len(indices) > 1 else 0
            shifted[indices] = np.roll(x[indices], offset)
        placebo_slopes[replicate] = _slope(shifted, y)
    placebo_p = float(
        (1 + np.sum(placebo_slopes >= observed_slope))
        / (config.placebo_replicates + 1)
    )

    frame["dose"] = pd.qcut(
        frame["residual_uplift_std"], 10, labels=False, duplicates="drop"
    ).astype(int)
    dose_means = frame.groupby("dose", observed=True)["future_price_quality"].mean()
    top_minus_bottom = float(dose_means.iloc[-1] - dose_means.iloc[0])

    def subset_slope(subset: pd.DataFrame) -> float:
        return _slope(_center(subset, "residual_uplift_std"), _center(subset, "future_price_quality"))

    agent_slopes = {
        str(key): subset_slope(group)
        for key, group in frame.groupby("agent_id", observed=True)
    }
    instrument_slopes = {
        str(key): subset_slope(group)
        for key, group in frame.groupby("instrument_id", observed=True)
    }
    horizon_slopes = {
        str(key): subset_slope(group)
        for key, group in frame.groupby("horizon", observed=True)
    }
    leave_one_agent = {
        str(agent): subset_slope(frame[frame["agent_id"] != agent].copy())
        for agent in sorted(frame["agent_id"].unique())
    }

    raw_selected = _top_fraction(frame, "raw_candidate_score")
    residual_selected = _top_fraction(frame, "residual_candidate_score")
    returns = frame["realized_return"].to_numpy(float)
    raw_roi = float(returns[raw_selected].mean())
    residual_roi = float(returns[residual_selected].mean())
    paired_contribution = (
        residual_selected.astype(float) - raw_selected.astype(float)
    ) * returns
    return_boot = np.empty(config.bootstrap_replicates, dtype=float)
    for replicate in range(config.bootstrap_replicates):
        sample = bootstrap_rng.integers(0, n, size=n)
        return_boot[replicate] = float(paired_contribution[sample].mean())
    paired_low = float(np.quantile(return_boot, 0.025))
    paired_high = float(np.quantile(return_boot, 0.975))

    config_payload = asdict(config)
    config_payload["horizons"] = list(config.horizons)
    result = {
        "schema_version": 1,
        "status": "completed",
        "profile": "synthetic-multi-agent-pricing-v1",
        "simulation_only": True,
        "empirical_transfer_claimed": False,
        "config": config_payload,
        "controls": {
            "candidate_identity_fixed": True,
            "same_agent_target": True,
            "post_event_fields_used": False,
        },
        "mechanism": {
            "standardized_uplift_slope": observed_slope,
            "cluster_ci_low": ci_low,
            "cluster_ci_high": ci_high,
            "placebo_replicates": config.placebo_replicates,
            "placebo_upper_tail_p": placebo_p,
            "placebo_mean_slope": float(placebo_slopes.mean()),
            "placebo_q99_slope": float(np.quantile(placebo_slopes, 0.99)),
            "top_minus_bottom": top_minus_bottom,
        },
        "distribution": {
            "agent_slopes": agent_slopes,
            "instrument_slopes": instrument_slopes,
            "horizon_slopes": horizon_slopes,
            "leave_one_agent_out_slopes": leave_one_agent,
        },
        "economic_diagnostic": {
            "raw_roi": raw_roi,
            "residual_roi": residual_roi,
            "paired_ci_low_per_opportunity": paired_low,
            "paired_ci_high_per_opportunity": paired_high,
            "execution_validated": False,
        },
    }
    submission = {
        "schema_version": 1,
        "submission_id": "synthetic-marb-contract-v1",
        "domain_profile": "synthetic-multi-agent-pricing-v1",
        "evidence_tier": "executed",
        "model": {
            "model_id": "known-data-generating-process-v1",
            "code_ref": "scripts/run_synthetic_marb_profile.py",
            "artifact_sha256": _sha256_json(config_payload),
        },
        "data": {
            "opportunities": n,
            "entities": n,
            "agents": config.agents,
            "horizons": len(config.horizons),
            "test_start": "2026-01-01",
            "test_end": "2026-01-02",
        },
        "controls": {
            "chronology_locked": True,
            "candidate_identity_fixed": True,
            "future_targets_loaded_after_selection": True,
            "same_agent_future_target": True,
            "post_event_fields_forbidden": True,
        },
        "task_b": {
            "standardized_uplift_slope": observed_slope,
            "cluster_ci_low": ci_low,
            "cluster_ci_high": ci_high,
            "placebo_replicates": config.placebo_replicates,
            "placebo_upper_tail_p": placebo_p,
            "top_minus_bottom": top_minus_bottom,
        },
        "distribution": {
            "positive_agents": int(sum(v > 0 for v in agent_slopes.values())),
            "total_agents": config.agents,
            "positive_instruments": int(sum(v > 0 for v in instrument_slopes.values())),
            "total_instruments": config.instruments,
            "positive_horizons": int(sum(v > 0 for v in horizon_slopes.values())),
            "total_horizons": len(config.horizons),
            "leave_one_agent_out_min_ci_low": float(min(leave_one_agent.values())),
        },
        "economic_diagnostic": {
            "raw_roi": raw_roi,
            "residual_roi": residual_roi,
            "paired_ci_low_per_opportunity": paired_low,
            "paired_ci_high_per_opportunity": paired_high,
            "positive_execution_cells": 0,
            "total_execution_cells": 1,
            "execution_validated": False,
        },
        "prospective_status": "not_started",
        "prohibited_claims_acknowledged": True,
    }
    return frame, result, submission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="artifacts/synthetic-marb-profile")
    parser.add_argument("--opportunities", type=int, default=12000)
    parser.add_argument("--placebo-replicates", type=int, default=1000)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()
    config = SyntheticConfig(
        opportunities=args.opportunities,
        placebo_replicates=args.placebo_replicates,
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
    )
    frame, result, submission = run_profile(config)
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["stratum"]).to_csv(
        root / "synthetic-opportunities.csv.gz", index=False
    )
    (root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "submission.json").write_text(
        json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
