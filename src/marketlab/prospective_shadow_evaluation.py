from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

OUTCOMES = ("home", "draw", "away")
CUTOFFS = (48, 24, 12, 6)
JOIN_KEYS_LEFT = ["event_id", "bookmaker_key", "market_key", "realized_snapshot_id"]
JOIN_KEYS_RIGHT = ["event_id", "bookmaker_key", "market_key", "snapshot_id"]


@dataclass(frozen=True, slots=True)
class ProspectiveEvaluationPolicy:
    trade_fraction: float = 0.20
    minimum_candidates_per_snapshot_cutoff: int = 20
    minimum_unique_events: int = 1000
    minimum_eligible_snapshot_cutoff_groups: int = 20
    minimum_unique_events_per_cutoff: int = 200
    bootstrap_replicates: int = 4000
    bootstrap_seed: int = 20260719


def _truthy(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "yes"}


def _require(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def attach_closing_clv(candidates: pd.DataFrame, closing: pd.DataFrame) -> pd.DataFrame:
    forbidden = {"result", "winner", "home_score", "away_score", "score_home", "score_away"}
    present_forbidden = sorted((set(candidates.columns) | set(closing.columns)) & forbidden)
    if present_forbidden:
        raise ValueError(f"outcome fields are forbidden: {present_forbidden}")
    candidate_required = JOIN_KEYS_LEFT + [
        "raw_candidate_outcome", "raw_candidate_score", "action_rank_score_for_raw_candidate",
        "supported_closing_cutoff_hours", "realized_snapshot_ingested_at", "research_only", "no_execution",
        "unvalidated_prospective_transfer", "bundle_id", "bundle_manifest_sha256",
    ]
    closing_required = JOIN_KEYS_RIGHT + [
        "closing_snapshot_id", "closing_snapshot_ingested_at", "commence_time",
        *[f"closing_log_odds_clv_{outcome}" for outcome in OUTCOMES],
        *[f"closing_delta_{outcome}_p" for outcome in OUTCOMES],
    ]
    _require(candidates, candidate_required, "shadow candidates")
    _require(closing, closing_required, "closing targets")
    if candidates.duplicated(["event_id", "realized_snapshot_id"]).any():
        raise ValueError("candidate file must contain one event candidate per realized snapshot")
    if closing.duplicated(JOIN_KEYS_RIGHT).any():
        raise ValueError("duplicate closing target observation identity")
    if not candidates["raw_candidate_outcome"].isin(OUTCOMES).all():
        raise ValueError("unknown candidate outcome")
    policy_flags = candidates[
        ["research_only", "no_execution", "unvalidated_prospective_transfer"]
    ].apply(lambda column: column.map(_truthy))
    if not policy_flags.all().all():
        raise ValueError("shadow policy flags are not all true")
    if candidates["bundle_id"].nunique() != 1 or candidates["bundle_manifest_sha256"].nunique() != 1:
        raise ValueError("prospective evaluation must use one frozen bundle")
    if not candidates["supported_closing_cutoff_hours"].isin(CUTOFFS).all():
        raise ValueError("unsupported closing cutoff bucket")

    joined = candidates.merge(
        closing,
        left_on=JOIN_KEYS_LEFT,
        right_on=JOIN_KEYS_RIGHT,
        how="inner",
        validate="one_to_one",
        suffixes=("", "_closing"),
    )
    if joined.empty:
        raise RuntimeError("no shadow candidates have elapsed closing targets")
    observation_time = pd.to_datetime(
        joined["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    closing_time = pd.to_datetime(
        joined["closing_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    commence_time = pd.to_datetime(joined["commence_time"], utc=True, errors="coerce")
    if observation_time.isna().any() or closing_time.isna().any() or commence_time.isna().any():
        raise ValueError("invalid prospective evaluation timestamps")
    if (observation_time >= closing_time).any() or (closing_time >= commence_time).any():
        raise ValueError("prospective closing chronology is invalid")

    outcome_index = joined["raw_candidate_outcome"].map(
        {outcome: index for index, outcome in enumerate(OUTCOMES)}
    ).to_numpy(int)
    rows = np.arange(len(joined))
    log_values = joined[
        [f"closing_log_odds_clv_{outcome}" for outcome in OUTCOMES]
    ].to_numpy(float)
    fair_values = joined[
        [f"closing_delta_{outcome}_p" for outcome in OUTCOMES]
    ].to_numpy(float)
    joined["candidate_closing_log_clv"] = log_values[rows, outcome_index]
    joined["candidate_closing_fair_probability_clv"] = fair_values[rows, outcome_index]
    if not np.isfinite(
        joined[
            ["candidate_closing_log_clv", "candidate_closing_fair_probability_clv"]
        ].to_numpy(float)
    ).all():
        raise ValueError("non-finite candidate closing CLV")
    return joined


def freeze_snapshot_strategies(
    attached: pd.DataFrame,
    policy: ProspectiveEvaluationPolicy,
) -> pd.DataFrame:
    if not 0.0 < policy.trade_fraction < 1.0:
        raise ValueError("trade_fraction must be in (0,1)")
    output = attached.copy()
    output["baseline_traded"] = False
    output["action_traded"] = False
    output["eligible_snapshot_cutoff_group"] = False
    group_keys = ["realized_snapshot_id", "supported_closing_cutoff_hours"]
    for _, group in output.groupby(group_keys, sort=True):
        if len(group) < policy.minimum_candidates_per_snapshot_cutoff:
            continue
        output.loc[group.index, "eligible_snapshot_cutoff_group"] = True
        trade_count = int(np.floor(len(group) * policy.trade_fraction))
        baseline = group.sort_values(
            ["raw_candidate_score", "event_id", "bookmaker_key", "raw_candidate_outcome"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        action = group.sort_values(
            ["action_rank_score_for_raw_candidate", "event_id", "bookmaker_key", "raw_candidate_outcome"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        output.loc[baseline.index[:trade_count], "baseline_traded"] = True
        output.loc[action.index[:trade_count], "action_traded"] = True
    output["baseline_opportunity_log_clv"] = np.where(
        output["baseline_traded"], output["candidate_closing_log_clv"], 0.0
    )
    output["action_opportunity_log_clv"] = np.where(
        output["action_traded"], output["candidate_closing_log_clv"], 0.0
    )
    output["incremental_opportunity_log_clv"] = (
        output["action_opportunity_log_clv"] - output["baseline_opportunity_log_clv"]
    )
    output["baseline_opportunity_fair_clv"] = np.where(
        output["baseline_traded"], output["candidate_closing_fair_probability_clv"], 0.0
    )
    output["action_opportunity_fair_clv"] = np.where(
        output["action_traded"], output["candidate_closing_fair_probability_clv"], 0.0
    )
    return output


def cluster_bootstrap(
    event_ids: np.ndarray,
    values: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> dict[str, float]:
    frame = pd.DataFrame(
        {"event_id": event_ids.astype(str), "value": values.astype(float)}
    )
    grouped = frame.groupby("event_id", sort=False)["value"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(float)
    counts = grouped["count"].to_numpy(float)
    rng = np.random.default_rng(seed)
    estimates = np.empty(replicates, dtype=float)
    clusters = len(grouped)
    for index in range(replicates):
        sample = rng.integers(0, clusters, size=clusters)
        estimates[index] = sums[sample].sum() / counts[sample].sum()
    return {
        "replicates": int(replicates),
        "clusters": int(clusters),
        "mean": float(values.mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
    }


def _strategy_metrics(
    rows: pd.DataFrame,
    prefix: str,
    policy: ProspectiveEvaluationPolicy,
) -> dict[str, Any]:
    traded = rows[rows[f"{prefix}_traded"]]
    return {
        "opportunities": int(len(rows)),
        "trades": int(len(traded)),
        "mean_trade_log_clv": float(traded["candidate_closing_log_clv"].mean())
        if len(traded)
        else None,
        "mean_opportunity_log_clv": float(
            rows[f"{prefix}_opportunity_log_clv"].mean()
        ),
        "mean_trade_fair_probability_clv": float(
            traded["candidate_closing_fair_probability_clv"].mean()
        )
        if len(traded)
        else None,
        "positive_trade_log_clv_bootstrap": cluster_bootstrap(
            traded["event_id"].to_numpy(),
            traded["candidate_closing_log_clv"].to_numpy(float),
            replicates=policy.bootstrap_replicates,
            seed=policy.bootstrap_seed + (1 if prefix == "action" else 0),
        )
        if len(traded)
        else None,
    }


def evaluate_prospective_shadow(
    candidates: pd.DataFrame,
    closing: pd.DataFrame,
    policy: ProspectiveEvaluationPolicy = ProspectiveEvaluationPolicy(),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    attached = attach_closing_clv(candidates, closing)
    rows = freeze_snapshot_strategies(attached, policy)
    eligible = rows[rows["eligible_snapshot_cutoff_group"]].copy()
    if eligible.empty:
        raise RuntimeError("no snapshot/cutoff groups meet the frozen minimum size")
    comparison = cluster_bootstrap(
        eligible["event_id"].to_numpy(),
        eligible["incremental_opportunity_log_clv"].to_numpy(float),
        replicates=policy.bootstrap_replicates,
        seed=policy.bootstrap_seed + 10,
    )
    cutoff_metrics: dict[str, Any] = {}
    positive_cutoffs = 0
    for cutoff in CUTOFFS:
        group = eligible[eligible["supported_closing_cutoff_hours"] == cutoff]
        point = (
            float(group["incremental_opportunity_log_clv"].mean())
            if len(group)
            else None
        )
        cutoff_metrics[f"T-{cutoff}h"] = {
            "opportunities": int(len(group)),
            "unique_events": int(group["event_id"].nunique()),
            "mean_incremental_opportunity_log_clv": point,
        }
        positive_cutoffs += int(point is not None and point > 0.0)
    groups = eligible[
        ["realized_snapshot_id", "supported_closing_cutoff_hours"]
    ].drop_duplicates()
    events_by_cutoff = eligible.groupby("supported_closing_cutoff_hours")[
        "event_id"
    ].nunique().to_dict()
    evidence_checks = {
        "minimum_unique_events": bool(
            eligible["event_id"].nunique() >= policy.minimum_unique_events
        ),
        "minimum_snapshot_cutoff_groups": bool(
            len(groups) >= policy.minimum_eligible_snapshot_cutoff_groups
        ),
        "minimum_events_each_cutoff": bool(
            all(
                events_by_cutoff.get(cutoff, 0)
                >= policy.minimum_unique_events_per_cutoff
                for cutoff in CUTOFFS
            )
        ),
    }
    baseline_metrics = _strategy_metrics(eligible, "baseline", policy)
    action_metrics = _strategy_metrics(eligible, "action", policy)
    promotion_checks = {
        "evidence_volume_passed": all(evidence_checks.values()),
        "incremental_log_clv_ci_above_zero": comparison["ci95_low"] > 0.0,
        "action_trade_log_clv_ci_above_zero": bool(
            action_metrics["positive_trade_log_clv_bootstrap"]
            and action_metrics["positive_trade_log_clv_bootstrap"]["ci95_low"]
            > 0.0
        ),
        "action_fair_probability_clv_positive": bool(
            action_metrics["mean_trade_fair_probability_clv"] is not None
            and action_metrics["mean_trade_fair_probability_clv"] > 0.0
        ),
        "positive_point_lift_at_least_3_of_4_cutoffs": positive_cutoffs >= 3,
    }
    report = {
        "status": "completed",
        "policy": asdict(policy),
        "bundle_id": str(eligible["bundle_id"].iloc[0]),
        "bundle_manifest_sha256": str(
            eligible["bundle_manifest_sha256"].iloc[0]
        ),
        "attached_candidates": int(len(attached)),
        "eligible_opportunities": int(len(eligible)),
        "unique_events": int(eligible["event_id"].nunique()),
        "eligible_snapshot_cutoff_groups": int(len(groups)),
        "baseline_strategy": baseline_metrics,
        "action_rank_strategy": action_metrics,
        "incremental_action_minus_baseline": comparison,
        "incremental_by_cutoff": cutoff_metrics,
        "positive_cutoffs": positive_cutoffs,
        "evidence_checks": evidence_checks,
        "promotion_checks": promotion_checks,
        "prospective_clv_promoted": all(promotion_checks.values()),
        "outcome_blind": True,
        "profit_claim": False,
    }
    return rows, report
