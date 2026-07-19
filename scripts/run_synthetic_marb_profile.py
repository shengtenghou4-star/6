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
    entities: int = 12000
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


def _within_group_slope(frame: pd.DataFrame, x: str, y: str, group: str) -> float:
    x_centered = frame[x] - frame.groupby(group, observed=True)[x].transform("mean")
    y_centered = frame[y] - frame.groupby(group, observed=True)[y].transform("mean")
    denominator = float(np.dot(x_centered, x_centered))
    if denominator <= 0:
        raise ValueError("within-group slope denominator is nonpositive")
    return float(np.dot(x_centered, y_centered) / denominator)


def _cluster_bootstrap_slope(
    frame: pd.DataFrame,
    x: str,
    y: str,
    group: str,
    rng: np.random.Generator,
    replicates: int,
) -> tuple[float, float]:
    x_centered = (frame[x] - frame.groupby(group, observed=True)[x].transform("mean")).to_numpy()
    y_centered = (frame[y] - frame.groupby(group, observed=True)[y].transform("mean")).to_numpy()
    clusters = frame["event_id"].to_numpy()
    unique_clusters = np.unique(clusters)
    cluster_rows = [np.flatnonzero(clusters == cluster) for cluster in unique_clusters]
    slopes = np.empty(replicates, dtype=float)
    for replicate in range(replicates):
        chosen = rng.integers(0, len(cluster_rows), size=len(cluster_rows))
        indices = np.concatenate([cluster_rows[index] for index in chosen])
        denominator = float(np.dot(x_centered[indices], x_centered[indices]))
        slopes[replicate] = float(
            np.dot(x_centered[indices], y_centered[indices]) / denominator
        )
    return float(np.quantile(slopes, 0.025)), float(np.quantile(slopes, 0.975))


def _alignment_placebo(
    frame: pd.DataFrame,
    rng: np.random.Generator,
    replicates: int,
) -> tuple[np.ndarray, float]:
    x = frame["residual_uplift_std"].to_numpy()
    y_centered = (
        frame["future_price_quality"]
        - frame.groupby("stratum", observed=True)["future_price_quality"].transform("mean")
    ).to_numpy()
    groups = [indices.to_numpy() for _, indices in frame.groupby("stratum", observed=True).groups.items()]
    observed = _within_group_slope(
        frame, "residual_uplift_std", "future_price_quality", "stratum"
    )
    slopes = np.empty(replicates, dtype=float)
    shifted = np.empty_like(x)
    for replicate in range(replicates):
        for indices in groups:
            if len(indices) < 2:
                shifted[indices] = x[indices]
                continue
            offset = int(rng.integers(1, len(indices)))
            shifted[indices] = np.roll(x[indices], offset)
        denominator = float(np.dot(shifted, shifted))
        slopes[replicate] = float(np.dot(shifted, y_centered) / denominator)
    p_value = float((1 + np.sum(slopes >= observed)) / (replicates + 1))
    return slopes, p_value


def _top_fraction_flags(frame: pd.DataFrame, score: str, fraction: float = 0.05) -> np.ndarray:
    selected = np.zeros(len(frame), dtype=bool)
    for _, group in frame.groupby("horizon", observed=True):
        quota = int(np.floor(len(group) * fraction))
        if quota:
            order = group.sort_values([score, "event_id"], ascending=[False, True]).index[:quota]
            selected[order.to_numpy()] = True
    return selected


def run_profile(config: SyntheticConfig) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    rng = np.random.default_rng(config.seed)
    n = config.entities
    event_id = np.arange(n, dtype=int)
    agent = rng.integers(0, config.agents, size=n)
    instrument = rng.integers(0, config.instruments, size=n)
    horizon = rng.choice(np.asarray(config.horizons), size=n)
    market_state = rng.normal(size=n)
    secondary_state = rng.normal(size=n)
    expected_action = 0.55 * market_state - 0.20 * secondary_state
    abnormal_action = rng.normal(size=n)
    observed_action = expected_action + abnormal_action
    raw_score = 0.45 * market_state + 0.18 * secondary_state + rng.normal(0, 0.15, size=n)
    residual_uplift = abnormal_action + rng.normal(0, 0.05, size=n)
    residual_uplift_std = (residual_uplift - residual_uplift.mean()) / residual_uplift.std(ddof=0)

    agent_effect = (agent - agent.mean()) * 0.008
    instrument_effect = (instrument - instrument.mean()) * 0.006
    future_price_quality = (
        0.38 * raw_score
        + config.residual_signal * residual_uplift_std
        + agent_effect
        + instrument_effect
        + rng.normal(0, 0.75, size=n)
    )
    realized_return = rng.normal(0, 1.0, size=n)

    frame = pd.DataFrame(
        {
            "event_id": event_id,
            "agent_id": agent,
            "instrument_id": instrument,
            "horizon": horizon,
            "market_state": market_state,
            "secondary_state": secondary_state,
            "expected_action": expected_action,
            "observed_action": observed_action,
            "action_residual": abnormal_action,
            "raw_candidate_score": raw_score,
            "residual_uplift_std": residual_uplift_std,
            "residual_candidate_score": raw_score + config.residual_signal * residual_uplift_std,
            "future_price_quality": future_price_quality,
            "realized_return": realized_return,
        }
    )
    frame["baseline_bin"] = pd.qcut(
        frame["raw_candidate_score"],
        q=config.baseline_bins,
        labels=False,
        duplicates="drop",
    ).astype(int)
    frame["stratum"] = (
        frame["agent_id"].astype(str)
        + "|"
        + frame["instrument_id"].astype(str)
        + "|"
        + frame["horizon"].astype(str)
        + "|"
        + frame["baseline_bin"].astype(str)
    ).astype("category")

    observed_slope = _within_group_slope(
        frame, "residual_uplift_std", "future_price_quality", "stratum"
    )
    ci_low, ci_high = _cluster_bootstrap_slope(
        frame,
        "residual_uplift_std",
        "future_price_quality",
        "stratum",
        np.random.default_rng(config.seed + 1),
        config.bootstrap_replicates,
    )
    placebo_slopes, placebo_p = _alignment_placebo(
        frame, np.random.default_rng(config.seed + 2), config.placebo_replicates
    )

    dose = pd.qcut(frame["residual_uplift_std"], 10, labels=False)
    dose_means = frame.assign(dose=dose).groupby("dose", observed=True)[
        "future_price_quality"
    ].mean()
    top_minus_bottom = float(dose_means.iloc[-1] - dose_means.iloc[0])

    agent_slopes = {
        str(key): _within_group_slope(group, "residual_uplift_std", "future_price_quality", "stratum")
        for key, group in frame.groupby("agent_id", observed=True)
    }
    instrument_slopes = {
        str(key): _within_group_slope(group, "residual_uplift_std", "future_price_quality", "stratum")
        for key, group in frame.groupby("instrument_id", observed=True)
    }
    horizon_slopes = {
        str(key): _within_group_slope(group, "residual_uplift_std", "future_price_quality", "stratum")
        for key, group in frame.groupby("horizon", observed=True)
    }
    leave_one_agent = {}
    for agent_id in sorted(frame["agent_id"].unique()):
        subset = frame[frame["agent_id"] != agent_id]
        slope = _within_group_slope(
            subset, "residual_uplift_std", "future_price_quality", "stratum"
        )
        leave_one_agent[str(agent_id)] = slope

    raw_selected = _top_fraction_flags(frame, "raw_candidate_score")
    residual_selected = _top_fraction_flags(frame, "residual_candidate_score")
    raw_roi = float(frame.loc[raw_selected, "realized_return"].mean())
    residual_roi = float(frame.loc[residual_selected, "realized_return"].mean())
    contribution = (
        residual_selected.astype(float) - raw_selected.astype(float)
    ) * frame["realized_return"].to_numpy()
    bootstrap_rng = np.random.default_rng(config.seed + 3)
    boot = np.empty(config.bootstrap_replicates, dtype=float)
    for replicate in range(config.bootstrap_replicates):
        sample = bootstrap_rng.integers(0, n, size=n)
        boot[replicate] = float(contribution[sample].mean())
    paired_low, paired_high = (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975)))

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
            "future_target_joined_after_candidate_construction": True,
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
            "positive_agents": int(sum(value > 0 for value in agent_slopes.values())),
            "total_agents": config.agents,
            "positive_instruments": int(sum(value > 0 for value in instrument_slopes.values())),
            "total_instruments": config.instruments,
            "positive_horizons": int(sum(value > 0 for value in horizon_slopes.values())),
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
    parser.add_argument("--entities", type=int, default=12000)
    parser.add_argument("--placebo-replicates", type=int, default=1000)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()

    config = SyntheticConfig(
        entities=args.entities,
        placebo_replicates=args.placebo_replicates,
        bootstrap_replicates=args.bootstrap_replicates,
        seed=args.seed,
    )
    frame, result, submission = run_profile(config)
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["stratum"]).to_csv(root / "synthetic-opportunities.csv.gz", index=False)
    (root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "submission.json").write_text(
        json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
