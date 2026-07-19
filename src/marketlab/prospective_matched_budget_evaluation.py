from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

OUTCOMES = ("home", "draw", "away")
CUTOFFS = (48, 24, 12, 6)
OPPORTUNITY_KEYS = ("event_id", "realized_snapshot_id")
JOIN_KEYS_LEFT = ("event_id", "bookmaker_key", "market_key", "realized_snapshot_id")
JOIN_KEYS_RIGHT = ("event_id", "bookmaker_key", "market_key", "snapshot_id")
FORBIDDEN_OUTCOME_FIELDS = {
    "result",
    "winner",
    "home_score",
    "away_score",
    "score_home",
    "score_away",
}


@dataclass(frozen=True, slots=True)
class CohortEvaluationPolicy:
    activation_utc: str = "2026-07-19T11:00:00Z"
    campaign_end_utc: str = "2026-07-26T06:30:00Z"
    minimum_collection_lead_hours: float = 3.25
    fraction: float = 0.05
    raw_policy_id: str = "raw_positive_top_5pct_campaign_cohort_v1"
    residual_policy_id: str = "residual_positive_top_5pct_campaign_cohort_v1"
    minimum_candidates: int = 300
    minimum_unique_events: int = 75
    minimum_selected_per_policy: int = 15
    minimum_candidates_per_cutoff: int = 40
    minimum_supported_cutoffs: int = 3
    maximum_positive_book_contribution_share: float = 0.50
    bootstrap_replicates: int = 4000
    bootstrap_seed: int = 20260726

    def validate(self) -> None:
        activation = pd.to_datetime(self.activation_utc, utc=True, errors="coerce")
        campaign_end = pd.to_datetime(
            self.campaign_end_utc, utc=True, errors="coerce"
        )
        if pd.isna(activation) or pd.isna(campaign_end):
            raise ValueError("activation or campaign end is invalid")
        if activation >= campaign_end:
            raise ValueError("activation must precede campaign end")
        if self.minimum_collection_lead_hours <= 0:
            raise ValueError("minimum collection lead must be positive")
        if not 0.0 < self.fraction < 1.0:
            raise ValueError("fraction must be in (0, 1)")
        if self.bootstrap_replicates <= 0:
            raise ValueError("bootstrap replicates must be positive")
        if not 0.0 < self.maximum_positive_book_contribution_share <= 1.0:
            raise ValueError("book concentration limit must be in (0, 1]")


def _truthy(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().casefold() in {"true", "1", "yes"}


def _require(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _reject_outcomes(*frames: pd.DataFrame) -> None:
    present = sorted(
        {
            str(column)
            for frame in frames
            for column in frame.columns
            if str(column).casefold() in FORBIDDEN_OUTCOME_FIELDS
        }
    )
    if present:
        raise ValueError(f"outcome fields are forbidden: {present}")


def _validate_bundle(candidates: pd.DataFrame) -> tuple[str, str]:
    if candidates["bundle_id"].nunique(dropna=False) != 1:
        raise ValueError("candidate cohort must use one frozen bundle")
    if candidates["bundle_manifest_sha256"].nunique(dropna=False) != 1:
        raise ValueError("candidate cohort must use one frozen bundle manifest")
    bundle_id = str(candidates["bundle_id"].iloc[0])
    manifest_sha = str(candidates["bundle_manifest_sha256"].iloc[0]).casefold()
    if len(manifest_sha) != 64 or any(
        character not in "0123456789abcdef" for character in manifest_sha
    ):
        raise ValueError("invalid bundle manifest SHA-256")
    return bundle_id, manifest_sha


def _rank_policy(
    cohort: pd.DataFrame,
    *,
    score_column: str,
    policy_id: str,
    fraction: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ledger = cohort.copy()
    ledger["selected"] = False
    cutoff_diagnostics: dict[str, Any] = {}
    capacity_complete = True
    for cutoff in CUTOFFS:
        mask = ledger["supported_closing_cutoff_hours"] == cutoff
        group = ledger.loc[mask]
        quota = int(np.floor(len(group) * fraction))
        eligible = group[group[score_column] > 0].sort_values(
            [score_column, "event_id", "realized_snapshot_id", "bookmaker_key"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        capacity = len(eligible) >= quota
        capacity_complete &= capacity
        if quota:
            ledger.loc[eligible.index[:quota], "selected"] = True
        cutoff_diagnostics[f"T-{cutoff}h"] = {
            "candidates": int(len(group)),
            "quota": quota,
            "positive_score_candidates": int(len(eligible)),
            "selected": int(min(quota, len(eligible))),
            "positive_score_capacity_complete": bool(capacity),
        }
    ledger["policy_id"] = policy_id
    ledger["policy_score"] = ledger[score_column].astype(float)
    ledger["policy_fraction"] = fraction
    ledger["policy_grouping"] = "full_matured_campaign_cohort_within_cutoff"
    ledger["closing_data_read_before_selection"] = False
    diagnostics = {
        "policy_id": policy_id,
        "score_column": score_column,
        "cutoffs": cutoff_diagnostics,
        "selected_rows": int(ledger["selected"].sum()),
        "positive_score_capacity_complete": bool(capacity_complete),
    }
    return ledger, diagnostics


def freeze_campaign_cohort_policies(
    candidates: pd.DataFrame,
    policy: CohortEvaluationPolicy = CohortEvaluationPolicy(),
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    policy.validate()
    _reject_outcomes(candidates)
    required = [
        *OPPORTUNITY_KEYS,
        "realized_snapshot_ingested_at",
        "commence_time",
        "supported_closing_cutoff_hours",
        "bookmaker_key",
        "market_key",
        "raw_candidate_outcome",
        "raw_candidate_score",
        "action_rank_score_for_raw_candidate",
        "bundle_id",
        "bundle_manifest_sha256",
        "research_only",
        "no_execution",
        "unvalidated_prospective_transfer",
    ]
    _require(candidates, required, "prospective candidates")
    if candidates.empty:
        raise RuntimeError("prospective candidate file is empty")
    if candidates.duplicated(list(OPPORTUNITY_KEYS)).any():
        raise ValueError("duplicate event/snapshot candidate opportunity")
    if not candidates["raw_candidate_outcome"].isin(OUTCOMES).all():
        raise ValueError("unknown candidate outcome")
    if not candidates["supported_closing_cutoff_hours"].isin(CUTOFFS).all():
        raise ValueError("unsupported closing cutoff")
    flags = candidates[
        ["research_only", "no_execution", "unvalidated_prospective_transfer"]
    ].apply(lambda column: column.map(_truthy))
    if not flags.all().all():
        raise ValueError("candidate policy flags are not all true")
    score_values = candidates[
        ["raw_candidate_score", "action_rank_score_for_raw_candidate"]
    ].to_numpy(float)
    if not np.isfinite(score_values).all():
        raise ValueError("candidate scores contain non-finite values")
    bundle_id, manifest_sha = _validate_bundle(candidates)

    frame = candidates.copy()
    observation = pd.to_datetime(
        frame["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    commence = pd.to_datetime(frame["commence_time"], utc=True, errors="coerce")
    if observation.isna().any() or commence.isna().any():
        raise ValueError("candidate timestamps are invalid")
    if (observation >= commence).any():
        raise ValueError("candidate observation must precede commence time")
    activation = pd.to_datetime(policy.activation_utc, utc=True)
    campaign_end = pd.to_datetime(policy.campaign_end_utc, utc=True)
    latest_observation = campaign_end - pd.Timedelta(
        hours=policy.minimum_collection_lead_hours
    )
    masks = {
        "before_activation": observation < activation,
        "after_latest_observation": observation > latest_observation,
        "commences_after_campaign": commence > campaign_end,
    }
    eligible = ~(masks["before_activation"] | masks["after_latest_observation"] | masks["commences_after_campaign"])
    cohort = frame.loc[eligible].copy()
    cohort["realized_snapshot_ingested_at"] = observation.loc[eligible]
    cohort["commence_time"] = commence.loc[eligible]
    cohort.sort_values(
        [
            "supported_closing_cutoff_hours",
            "realized_snapshot_ingested_at",
            "event_id",
            "realized_snapshot_id",
        ],
        ascending=[False, True, True, True],
        kind="mergesort",
        inplace=True,
    )
    cohort.reset_index(drop=True, inplace=True)
    if cohort.empty:
        raise RuntimeError("no matured candidate opportunities remain after frozen cohort rules")

    raw, raw_diagnostics = _rank_policy(
        cohort,
        score_column="raw_candidate_score",
        policy_id=policy.raw_policy_id,
        fraction=policy.fraction,
    )
    residual, residual_diagnostics = _rank_policy(
        cohort,
        score_column="action_rank_score_for_raw_candidate",
        policy_id=policy.residual_policy_id,
        fraction=policy.fraction,
    )
    cutoff_counts = {
        f"T-{cutoff}h": int(
            (cohort["supported_closing_cutoff_hours"] == cutoff).sum()
        )
        for cutoff in CUTOFFS
    }
    diagnostics = {
        "policy": asdict(policy),
        "bundle_id": bundle_id,
        "bundle_manifest_sha256": manifest_sha,
        "input_candidates": int(len(candidates)),
        "matured_cohort_candidates": int(len(cohort)),
        "matured_unique_events": int(cohort["event_id"].nunique()),
        "latest_eligible_observation_utc": latest_observation.isoformat(),
        "excluded": {key: int(mask.sum()) for key, mask in masks.items()},
        "candidates_by_cutoff": cutoff_counts,
        "raw_policy": raw_diagnostics,
        "residual_policy": residual_diagnostics,
        "same_candidate_identity_by_construction": True,
        "closing_data_used_for_selection": False,
        "match_outcomes_used": False,
    }
    return raw, residual, diagnostics


def cluster_bootstrap(
    event_ids: np.ndarray,
    values: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> dict[str, float]:
    if len(values) == 0:
        raise ValueError("cannot bootstrap an empty value array")
    frame = pd.DataFrame(
        {"event_id": event_ids.astype(str), "value": values.astype(float)}
    )
    grouped = frame.groupby("event_id", sort=False)["value"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(float)
    counts = grouped["count"].to_numpy(float)
    clusters = len(grouped)
    rng = np.random.default_rng(seed)
    estimates = np.empty(replicates, dtype=float)
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


def _attach_exact_closing(
    ledger: pd.DataFrame,
    closing: pd.DataFrame,
) -> pd.DataFrame:
    _reject_outcomes(ledger, closing)
    closing_required = [
        *JOIN_KEYS_RIGHT,
        "closing_snapshot_id",
        "closing_snapshot_ingested_at",
        "commence_time",
        *[f"closing_log_odds_clv_{outcome}" for outcome in OUTCOMES],
        *[f"closing_delta_{outcome}_p" for outcome in OUTCOMES],
    ]
    _require(closing, closing_required, "closing targets")
    if closing.duplicated(list(JOIN_KEYS_RIGHT)).any():
        raise ValueError("duplicate exact closing target identity")
    availability = ledger[list(JOIN_KEYS_LEFT)].merge(
        closing[list(JOIN_KEYS_RIGHT)],
        left_on=list(JOIN_KEYS_LEFT),
        right_on=list(JOIN_KEYS_RIGHT),
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing = int((availability["_merge"] != "both").sum())
    if missing:
        raise ValueError(f"missing exact closing targets for {missing} cohort rows")
    joined = ledger.merge(
        closing,
        left_on=list(JOIN_KEYS_LEFT),
        right_on=list(JOIN_KEYS_RIGHT),
        how="inner",
        validate="one_to_one",
        suffixes=("", "_closing"),
    )
    observation = pd.to_datetime(
        joined["realized_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    closing_time = pd.to_datetime(
        joined["closing_snapshot_ingested_at"], utc=True, errors="coerce"
    )
    commence = pd.to_datetime(joined["commence_time"], utc=True, errors="coerce")
    closing_commence = pd.to_datetime(
        joined["commence_time_closing"], utc=True, errors="coerce"
    )
    if (
        observation.isna().any()
        or closing_time.isna().any()
        or commence.isna().any()
        or closing_commence.isna().any()
    ):
        raise ValueError("closing chronology contains invalid timestamps")
    if not commence.equals(closing_commence):
        raise ValueError("candidate and closing target commence times differ")
    if (observation >= closing_time).any() or (closing_time >= commence).any():
        raise ValueError("closing chronology is invalid")
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
    joined["candidate_closing_fair_probability_clv"] = fair_values[
        rows, outcome_index
    ]
    if not np.isfinite(
        joined[
            [
                "candidate_closing_log_clv",
                "candidate_closing_fair_probability_clv",
            ]
        ].to_numpy(float)
    ).all():
        raise ValueError("non-finite closing CLV")
    return joined


def _strategy_metrics(
    ledger: pd.DataFrame,
    policy: CohortEvaluationPolicy,
    *,
    seed_offset: int,
) -> dict[str, Any]:
    selected = ledger[ledger["selected"]].copy()
    bootstrap = (
        cluster_bootstrap(
            selected["event_id"].to_numpy(),
            selected["candidate_closing_log_clv"].to_numpy(float),
            replicates=policy.bootstrap_replicates,
            seed=policy.bootstrap_seed + seed_offset,
        )
        if len(selected)
        else None
    )
    return {
        "opportunities": int(len(ledger)),
        "selected": int(len(selected)),
        "unique_selected_events": int(selected["event_id"].nunique()),
        "mean_selected_log_clv": (
            float(selected["candidate_closing_log_clv"].mean())
            if len(selected)
            else None
        ),
        "mean_selected_fair_probability_clv": (
            float(selected["candidate_closing_fair_probability_clv"].mean())
            if len(selected)
            else None
        ),
        "selected_log_clv_bootstrap": bootstrap,
    }


def _positive_book_concentration(residual: pd.DataFrame) -> dict[str, Any]:
    selected = residual[residual["selected"]]
    contribution = selected.groupby("bookmaker_key")["candidate_closing_log_clv"].sum()
    positive = contribution[contribution > 0]
    share = float(positive.max() / positive.sum()) if len(positive) else None
    return {
        "log_clv_by_bookmaker": {
            str(key): float(value) for key, value in contribution.sort_index().items()
        },
        "maximum_positive_book_contribution_share": share,
    }



def _validate_frozen_ledger(
    ledger: pd.DataFrame,
    *,
    expected_policy_id: str,
    expected_score_column: str,
    fraction: float,
    label: str,
) -> pd.DataFrame:
    if ledger.duplicated(list(OPPORTUNITY_KEYS)).any():
        raise ValueError(f"{label} contains duplicate opportunities")
    policy_ids = set(ledger["policy_id"].astype(str))
    if policy_ids != {expected_policy_id}:
        raise ValueError(f"{label} policy ID does not match frozen protocol")
    scores = ledger["policy_score"].to_numpy(float)
    source_scores = ledger[expected_score_column].to_numpy(float)
    if not np.isfinite(scores).all() or not np.isfinite(source_scores).all():
        raise ValueError(f"{label} contains non-finite policy scores")
    if not np.allclose(scores, source_scores, rtol=0.0, atol=0.0):
        raise ValueError(f"{label} policy scores do not match frozen source scores")
    fractions = ledger["policy_fraction"].to_numpy(float)
    if not np.allclose(fractions, fraction, rtol=0.0, atol=0.0):
        raise ValueError(f"{label} policy fraction does not match frozen protocol")
    if set(ledger["policy_grouping"].astype(str)) != {
        "full_matured_campaign_cohort_within_cutoff"
    }:
        raise ValueError(f"{label} grouping does not match frozen protocol")
    output = ledger.copy()
    output["selected"] = output["selected"].map(_truthy)
    for cutoff in CUTOFFS:
        group = output[output["supported_closing_cutoff_hours"] == cutoff]
        quota = int(np.floor(len(group) * fraction))
        ordered = group[group["policy_score"] > 0].sort_values(
            ["policy_score", "event_id", "realized_snapshot_id", "bookmaker_key"],
            ascending=[False, True, True, True],
            kind="mergesort",
        )
        expected = set(
            map(tuple, ordered.loc[:, list(OPPORTUNITY_KEYS)].head(quota).to_numpy())
        )
        actual = set(
            map(
                tuple,
                group.loc[group["selected"], list(OPPORTUNITY_KEYS)].to_numpy(),
            )
        )
        if actual != expected:
            raise ValueError(f"{label} selection flags do not match frozen ranking")
    return output

def evaluate_frozen_campaign_policies(
    raw_ledger: pd.DataFrame,
    residual_ledger: pd.DataFrame,
    closing: pd.DataFrame,
    policy: CohortEvaluationPolicy = CohortEvaluationPolicy(),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    policy.validate()
    required = [
        *OPPORTUNITY_KEYS,
        *JOIN_KEYS_LEFT[1:],
        "realized_snapshot_ingested_at",
        "commence_time",
        "raw_candidate_outcome",
        "supported_closing_cutoff_hours",
        "selected",
        "policy_id",
        "policy_score",
        "policy_fraction",
        "policy_grouping",
        "raw_candidate_score",
        "action_rank_score_for_raw_candidate",
        "bundle_id",
        "bundle_manifest_sha256",
        "research_only",
        "no_execution",
        "unvalidated_prospective_transfer",
        "closing_data_read_before_selection",
    ]
    _require(raw_ledger, required, "raw frozen ledger")
    _require(residual_ledger, required, "residual frozen ledger")
    if raw_ledger["closing_data_read_before_selection"].map(_truthy).any():
        raise ValueError("raw policy was not frozen before closing data")
    if residual_ledger["closing_data_read_before_selection"].map(_truthy).any():
        raise ValueError("residual policy was not frozen before closing data")
    raw_frozen = _validate_frozen_ledger(
        raw_ledger,
        expected_policy_id=policy.raw_policy_id,
        expected_score_column="raw_candidate_score",
        fraction=policy.fraction,
        label="raw frozen ledger",
    )
    residual_frozen = _validate_frozen_ledger(
        residual_ledger,
        expected_policy_id=policy.residual_policy_id,
        expected_score_column="action_rank_score_for_raw_candidate",
        fraction=policy.fraction,
        label="residual frozen ledger",
    )
    identity_columns = [
        *OPPORTUNITY_KEYS,
        "bookmaker_key",
        "market_key",
        "raw_candidate_outcome",
        "realized_snapshot_ingested_at",
        "commence_time",
        "supported_closing_cutoff_hours",
        "raw_candidate_score",
        "action_rank_score_for_raw_candidate",
        "bundle_id",
        "bundle_manifest_sha256",
        "research_only",
        "no_execution",
        "unvalidated_prospective_transfer",
    ]
    raw_identity = raw_frozen[identity_columns].sort_values(
        list(OPPORTUNITY_KEYS)
    ).reset_index(drop=True)
    residual_identity = residual_frozen[identity_columns].sort_values(
        list(OPPORTUNITY_KEYS)
    ).reset_index(drop=True)
    if not raw_identity.equals(residual_identity):
        raise ValueError("raw and residual candidate identities differ")
    raw = _attach_exact_closing(raw_frozen, closing)
    residual = _attach_exact_closing(residual_frozen, closing)
    values = raw[
        [*OPPORTUNITY_KEYS, "candidate_closing_log_clv", "candidate_closing_fair_probability_clv"]
    ].merge(
        residual[[*OPPORTUNITY_KEYS, "candidate_closing_log_clv", "candidate_closing_fair_probability_clv"]],
        on=list(OPPORTUNITY_KEYS),
        validate="one_to_one",
        suffixes=("_raw", "_residual"),
    )
    if not np.allclose(
        values["candidate_closing_log_clv_raw"],
        values["candidate_closing_log_clv_residual"],
    ) or not np.allclose(
        values["candidate_closing_fair_probability_clv_raw"],
        values["candidate_closing_fair_probability_clv_residual"],
    ):
        raise RuntimeError("same candidate identity produced different closing CLV")

    raw_eval = raw.copy()
    residual_eval = residual.copy()
    raw_eval["opportunity_log_clv"] = np.where(
        raw_eval["selected"], raw_eval["candidate_closing_log_clv"], 0.0
    )
    residual_eval["opportunity_log_clv"] = np.where(
        residual_eval["selected"],
        residual_eval["candidate_closing_log_clv"],
        0.0,
    )
    comparison = raw_eval[
        [
            *OPPORTUNITY_KEYS,
            "supported_closing_cutoff_hours",
            "bookmaker_key",
            "opportunity_log_clv",
            "selected",
        ]
    ].merge(
        residual_eval[
            [*OPPORTUNITY_KEYS, "opportunity_log_clv", "selected"]
        ],
        on=list(OPPORTUNITY_KEYS),
        validate="one_to_one",
        suffixes=("_raw", "_residual"),
    )
    comparison["incremental_opportunity_log_clv"] = (
        comparison["opportunity_log_clv_residual"]
        - comparison["opportunity_log_clv_raw"]
    )
    paired = cluster_bootstrap(
        comparison["event_id"].to_numpy(),
        comparison["incremental_opportunity_log_clv"].to_numpy(float),
        replicates=policy.bootstrap_replicates,
        seed=policy.bootstrap_seed + 10,
    )
    cutoff_metrics: dict[str, Any] = {}
    positive_cutoffs = 0
    for cutoff in CUTOFFS:
        group = comparison[
            comparison["supported_closing_cutoff_hours"] == cutoff
        ]
        point = (
            float(group["incremental_opportunity_log_clv"].mean())
            if len(group)
            else None
        )
        positive_cutoffs += int(point is not None and point > 0)
        cutoff_metrics[f"T-{cutoff}h"] = {
            "opportunities": int(len(group)),
            "raw_selected": int(group["selected_raw"].sum()),
            "residual_selected": int(group["selected_residual"].sum()),
            "mean_incremental_opportunity_log_clv": point,
        }
    raw_metrics = _strategy_metrics(raw_eval, policy, seed_offset=1)
    residual_metrics = _strategy_metrics(residual_eval, policy, seed_offset=2)
    concentration = _positive_book_concentration(residual_eval)
    selected_raw = comparison["selected_raw"].to_numpy(bool)
    selected_residual = comparison["selected_residual"].to_numpy(bool)
    either = selected_raw | selected_residual
    both = selected_raw & selected_residual
    candidates_by_cutoff = {
        cutoff: int(
            (comparison["supported_closing_cutoff_hours"] == cutoff).sum()
        )
        for cutoff in CUTOFFS
    }
    cutoffs_with_volume = sum(
        count >= policy.minimum_candidates_per_cutoff
        for count in candidates_by_cutoff.values()
    )
    capacity_complete = all(
        int(raw_eval.loc[raw_eval["supported_closing_cutoff_hours"] == cutoff, "selected"].sum())
        == int(np.floor(candidates_by_cutoff[cutoff] * policy.fraction))
        and int(
            residual_eval.loc[
                residual_eval["supported_closing_cutoff_hours"] == cutoff,
                "selected",
            ].sum()
        )
        == int(np.floor(candidates_by_cutoff[cutoff] * policy.fraction))
        for cutoff in CUTOFFS
    )
    evidence_checks = {
        "minimum_candidates": len(comparison) >= policy.minimum_candidates,
        "minimum_unique_events": (
            comparison["event_id"].nunique() >= policy.minimum_unique_events
        ),
        "minimum_raw_selected": (
            raw_metrics["selected"] >= policy.minimum_selected_per_policy
        ),
        "minimum_residual_selected": (
            residual_metrics["selected"] >= policy.minimum_selected_per_policy
        ),
        "minimum_supported_cutoffs": (
            cutoffs_with_volume >= policy.minimum_supported_cutoffs
        ),
        "exact_quota_capacity_complete": bool(capacity_complete),
    }
    residual_bootstrap = residual_metrics["selected_log_clv_bootstrap"]
    maximum_share = concentration["maximum_positive_book_contribution_share"]
    promotion_checks = {
        "evidence_volume_passed": all(evidence_checks.values()),
        "residual_selected_log_clv_ci_above_zero": bool(
            residual_bootstrap and residual_bootstrap["ci95_low"] > 0
        ),
        "incremental_log_clv_ci_above_zero": paired["ci95_low"] > 0,
        "residual_fair_probability_clv_positive": bool(
            residual_metrics["mean_selected_fair_probability_clv"] is not None
            and residual_metrics["mean_selected_fair_probability_clv"] > 0
        ),
        "positive_point_lift_at_least_3_of_4_cutoffs": positive_cutoffs >= 3,
        "positive_book_concentration_within_limit": bool(
            maximum_share is not None
            and maximum_share
            <= policy.maximum_positive_book_contribution_share
        ),
    }
    comparison["raw_policy_id"] = str(raw_eval["policy_id"].iloc[0])
    comparison["residual_policy_id"] = str(residual_eval["policy_id"].iloc[0])
    report = {
        "status": "completed",
        "policy": asdict(policy),
        "opportunities": int(len(comparison)),
        "unique_events": int(comparison["event_id"].nunique()),
        "raw_strategy": raw_metrics,
        "residual_strategy": residual_metrics,
        "incremental_residual_minus_raw": paired,
        "incremental_by_cutoff": cutoff_metrics,
        "positive_cutoffs": int(positive_cutoffs),
        "selection_overlap": {
            "selected_by_both": int(both.sum()),
            "selected_by_either": int(either.sum()),
            "jaccard": float(both.sum() / either.sum()) if either.any() else 1.0,
        },
        "residual_bookmaker_concentration": concentration,
        "evidence_checks": evidence_checks,
        "promotion_checks": promotion_checks,
        "prospective_matched_budget_promoted": all(promotion_checks.values()),
        "outcome_blind": True,
        "profit_claim": False,
        "live_execution_authorized": False,
    }
    return comparison, report
