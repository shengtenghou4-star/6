from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CAMPAIGN_START = pd.Timestamp("2026-07-19T06:00:00Z")
POLICY_ACTIVATION = pd.Timestamp("2026-07-19T11:00:00Z")
LATEST_ELIGIBLE_OBSERVATION = pd.Timestamp("2026-07-26T03:15:00Z")
CAMPAIGN_END = pd.Timestamp("2026-07-26T06:30:00Z")
FRACTION = 0.05
SIMULATIONS = 20000
SEED = 20260719
# Frozen from Experiment 019's historical event-cluster influence calculation.
HISTORICAL_CLUSTER_SIGMA_EQUIVALENT = 0.015268280246644523
Z_ALPHA_PLUS_POWER = 2.801585


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def kish_effective_size(values: pd.Series) -> float:
    counts = values.value_counts().to_numpy(float)
    if not len(counts):
        return 0.0
    return float(counts.sum() ** 2 / np.square(counts).sum())


def gamma_poisson_final(
    observed: int,
    elapsed_days: float,
    total_days: float,
    rng: np.random.Generator,
    simulations: int,
) -> np.ndarray:
    if elapsed_days <= 0:
        return np.full(simulations, observed, dtype=int)
    remaining = max(total_days - elapsed_days, 0.0)
    rate = rng.gamma(shape=observed + 0.5, scale=1.0 / elapsed_days, size=simulations)
    return observed + rng.poisson(rate * remaining)


def summarize(values: np.ndarray) -> dict[str, float]:
    return {
        "median": float(np.median(values)),
        "q025": float(np.quantile(values, 0.025)),
        "q975": float(np.quantile(values, 0.975)),
        "mean": float(np.mean(values)),
    }


def concentration(frame: pd.DataFrame, column: str) -> dict[str, Any] | None:
    if column not in frame.columns or frame.empty:
        return None
    counts = frame[column].astype(str).value_counts()
    return {
        "categories": int(len(counts)),
        "largest_category": str(counts.index[0]),
        "largest_share": float(counts.iloc[0] / counts.sum()),
        "top5_share": float(counts.iloc[:5].sum() / counts.sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-root", default="artifacts/evidence-power-forecast")
    parser.add_argument("--simulations", type=int, default=SIMULATIONS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    candidate_path = Path(args.candidates)
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(candidate_path, low_memory=False)
    required = {
        "event_id",
        "realized_snapshot_id",
        "realized_snapshot_ingested_at",
        "supported_closing_cutoff_hours",
        "bookmaker_key",
        "raw_candidate_score",
        "action_rank_score_for_raw_candidate",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"candidate ledger missing columns: {missing}")
    frame["realized_snapshot_ingested_at"] = pd.to_datetime(
        frame["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    if frame["realized_snapshot_ingested_at"].isna().any():
        raise ValueError("candidate ledger has invalid ingestion timestamps")
    frame = frame[
        (frame["realized_snapshot_ingested_at"] >= POLICY_ACTIVATION)
        & (frame["realized_snapshot_ingested_at"] <= LATEST_ELIGIBLE_OBSERVATION)
    ].copy()
    if frame.empty:
        raise RuntimeError("no post-activation candidates are available")
    frame["supported_closing_cutoff_hours"] = frame[
        "supported_closing_cutoff_hours"
    ].astype(int)
    frame["utc_day"] = frame["realized_snapshot_ingested_at"].dt.strftime("%Y-%m-%d")
    frame["raw_positive"] = frame["raw_candidate_score"] > 0
    frame["residual_positive"] = frame["action_rank_score_for_raw_candidate"] > 0

    latest = min(frame["realized_snapshot_ingested_at"].max(), LATEST_ELIGIBLE_OBSERVATION)
    elapsed_days = max((latest - POLICY_ACTIVATION).total_seconds() / 86400.0, 1.0 / 24.0)
    total_days = (LATEST_ELIGIBLE_OBSERVATION - POLICY_ACTIVATION).total_seconds() / 86400.0
    rng = np.random.default_rng(args.seed)
    simulations = args.simulations

    candidate_final = gamma_poisson_final(
        len(frame), elapsed_days, total_days, rng, simulations
    )
    event_first = frame.groupby("event_id", as_index=False)[
        "realized_snapshot_ingested_at"
    ].min()
    event_final = gamma_poisson_final(
        int(frame["event_id"].nunique()), elapsed_days, total_days, rng, simulations
    )

    cutoffs = (48, 24, 12, 6)
    cutoff_final: dict[int, np.ndarray] = {}
    raw_capacity: dict[int, np.ndarray] = {}
    residual_capacity: dict[int, np.ndarray] = {}
    cutoff_rows: list[dict[str, Any]] = []
    for cutoff in cutoffs:
        group = frame[frame["supported_closing_cutoff_hours"] == cutoff]
        final_n = gamma_poisson_final(len(group), elapsed_days, total_days, rng, simulations)
        cutoff_final[cutoff] = final_n
        additional = np.maximum(final_n - len(group), 0)
        raw_probability = rng.beta(
            int(group["raw_positive"].sum()) + 0.5,
            int((~group["raw_positive"]).sum()) + 0.5,
            size=simulations,
        )
        residual_probability = rng.beta(
            int(group["residual_positive"].sum()) + 0.5,
            int((~group["residual_positive"]).sum()) + 0.5,
            size=simulations,
        )
        raw_positive_final = int(group["raw_positive"].sum()) + rng.binomial(
            additional, raw_probability
        )
        residual_positive_final = int(group["residual_positive"].sum()) + rng.binomial(
            additional, residual_probability
        )
        quota = np.floor(final_n * FRACTION).astype(int)
        raw_capacity[cutoff] = raw_positive_final >= quota
        residual_capacity[cutoff] = residual_positive_final >= quota
        cutoff_rows.append(
            {
                "cutoff_hours": cutoff,
                "current_candidates": int(len(group)),
                "current_unique_events": int(group["event_id"].nunique()),
                "current_raw_positive": int(group["raw_positive"].sum()),
                "current_residual_positive": int(group["residual_positive"].sum()),
                "forecast_median_candidates": float(np.median(final_n)),
                "forecast_q025_candidates": float(np.quantile(final_n, 0.025)),
                "forecast_q975_candidates": float(np.quantile(final_n, 0.975)),
                "probability_at_least_40": float(np.mean(final_n >= 40)),
                "probability_raw_capacity": float(np.mean(raw_capacity[cutoff])),
                "probability_residual_capacity": float(
                    np.mean(residual_capacity[cutoff])
                ),
            }
        )
    cutoff_table = pd.DataFrame(cutoff_rows)
    cutoff_table.to_csv(root / "cutoff-forecast.csv", index=False)

    daily = (
        frame.groupby("utc_day")
        .agg(
            candidate_rows=("event_id", "size"),
            unique_events=("event_id", "nunique"),
            snapshots=("realized_snapshot_id", "nunique"),
            bookmakers=("bookmaker_key", "nunique"),
        )
        .reset_index()
    )
    daily.to_csv(root / "daily-accrual.csv", index=False)

    quota_total = sum(
        np.floor(cutoff_final[cutoff] * FRACTION).astype(int) for cutoff in cutoffs
    )
    cutoff_volume_gate = sum(cutoff_final[c] >= 40 for c in cutoffs) >= 3
    raw_capacity_gate = np.logical_and.reduce([raw_capacity[c] for c in cutoffs])
    residual_capacity_gate = np.logical_and.reduce(
        [residual_capacity[c] for c in cutoffs]
    )
    candidate_gate = candidate_final >= 300
    event_gate = event_final >= 75
    selection_gate = quota_total >= 15
    all_volume_gates = (
        candidate_gate
        & event_gate
        & selection_gate
        & cutoff_volume_gate
        & raw_capacity_gate
        & residual_capacity_gate
    )

    event_effective_current = kish_effective_size(frame["event_id"])
    event_efficiency = min(
        event_effective_current / max(frame["event_id"].nunique(), 1), 1.0
    )
    projected_effective_events = np.maximum(event_final * event_efficiency, 1.0)
    mde = Z_ALPHA_PLUS_POWER * HISTORICAL_CLUSTER_SIGMA_EQUIVALENT / np.sqrt(
        projected_effective_events
    )

    warnings: list[str] = []
    if float(np.mean(candidate_gate)) < 0.80:
        warnings.append("candidate_300_gate_at_risk")
    if float(np.mean(event_gate)) < 0.80:
        warnings.append("unique_event_75_gate_at_risk")
    if float(np.mean(selection_gate)) < 0.80:
        warnings.append("selection_15_gate_at_risk")
    if float(np.mean(cutoff_volume_gate)) < 0.80:
        warnings.append("three_cutoffs_with_40_gate_at_risk")
    for row in cutoff_rows:
        if row["probability_at_least_40"] < 0.50:
            warnings.append(f"T{row['cutoff_hours']}_volume_structurally_weak")
        if min(
            row["probability_raw_capacity"],
            row["probability_residual_capacity"],
        ) < 0.80:
            warnings.append(f"T{row['cutoff_hours']}_positive_score_capacity_at_risk")

    report = {
        "status": "completed",
        "forecast_type": "outcome_blind_interim_operational_forecast",
        "generated_at_utc": pd.Timestamp.now(tz=UTC).isoformat(),
        "input": {
            "path": str(candidate_path),
            "sha256": sha256(candidate_path),
            "post_activation_rows": int(len(frame)),
            "post_activation_unique_events": int(frame["event_id"].nunique()),
            "post_activation_snapshots": int(frame["realized_snapshot_id"].nunique()),
            "latest_ingestion_utc": latest.isoformat(),
        },
        "frozen_window": {
            "campaign_start_utc": CAMPAIGN_START.isoformat(),
            "policy_activation_utc": POLICY_ACTIVATION.isoformat(),
            "latest_eligible_observation_utc": LATEST_ELIGIBLE_OBSERVATION.isoformat(),
            "campaign_end_utc": CAMPAIGN_END.isoformat(),
            "elapsed_fraction_of_eligible_window": float(
                min(elapsed_days / total_days, 1.0)
            ),
        },
        "current_effective_sample": {
            "candidate_rows": int(len(frame)),
            "unique_events": int(frame["event_id"].nunique()),
            "event_kish_effective_size": event_effective_current,
            "event_efficiency": event_efficiency,
            "snapshot_kish_effective_size": kish_effective_size(
                frame["realized_snapshot_id"]
            ),
        },
        "forecast": {
            "final_candidates": summarize(candidate_final),
            "final_unique_events": summarize(event_final),
            "final_total_exact_5pct_quota": summarize(quota_total),
            "minimum_detectable_incremental_log_clv_per_opportunity": summarize(
                mde
            ),
        },
        "gate_probabilities": {
            "at_least_300_candidates": float(np.mean(candidate_gate)),
            "at_least_75_unique_events": float(np.mean(event_gate)),
            "at_least_15_selections_per_policy": float(np.mean(selection_gate)),
            "at_least_three_cutoffs_with_40_candidates": float(
                np.mean(cutoff_volume_gate)
            ),
            "raw_positive_capacity_all_cutoffs": float(
                np.mean(raw_capacity_gate)
            ),
            "residual_positive_capacity_all_cutoffs": float(
                np.mean(residual_capacity_gate)
            ),
            "all_phase43_volume_gates": float(np.mean(all_volume_gates)),
        },
        "concentration": {
            "bookmaker": concentration(frame, "bookmaker_key"),
            "snapshot": concentration(frame, "realized_snapshot_id"),
            "sport": concentration(frame, "sport_key"),
        },
        "planning_assumption": {
            "historical_cluster_sigma_equivalent": HISTORICAL_CLUSTER_SIGMA_EQUIVALENT,
            "two_sided_alpha": 0.05,
            "power": 0.80,
            "z_alpha_plus_power": Z_ALPHA_PLUS_POWER,
            "forecast_model": "Jeffreys-prior gamma-Poisson homogeneous accrual with beta-binomial positive-score capacity",
        },
        "warnings": sorted(set(warnings)),
        "evidence_boundary": {
            "closing_targets_read": False,
            "match_results_read": False,
            "policy_scores_used_as_performance_labels": False,
            "running_policy_changed": False,
        },
    }
    (root / "result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
