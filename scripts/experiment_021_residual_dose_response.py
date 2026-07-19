from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


KEYS = ["match_id", "hours_before_kickoff"]
CUTOFFS = (48, 24, 12, 6)
BASELINE_BINS = 20
DOSE_BINS = 10
REPLICATES = 4000
SEED = 20260719


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upper_tail_p(null: np.ndarray, observed: float) -> float:
    return float((1 + np.sum(null >= observed)) / (len(null) + 1))


def deterministic_bins(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    score_column: str,
    bins: int,
) -> pd.Series:
    output = pd.Series(-1, index=frame.index, dtype=np.int16)
    tie_columns = ["match_id", "book_slot", "selected_outcome_index"]
    for _, group in frame.groupby(group_columns, sort=True):
        ordered = group.sort_values(
            [score_column, *tie_columns],
            kind="mergesort",
        ).index.to_numpy()
        count = len(ordered)
        assigned = np.minimum(np.arange(count) * bins // count, bins - 1)
        output.loc[ordered] = assigned.astype(np.int16)
    if (output < 0).any():
        raise RuntimeError(f"failed to assign {score_column} bins")
    return output


def prepare(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[np.ndarray]]:
    required = {
        "match_id",
        "match_date",
        "hours_before_kickoff",
        "book_slot",
        "selected_outcome_index",
        "baseline_score",
        "rank_score",
        "residual_uplift",
        "observation_decimal_odds",
        "log_odds_clv",
        "fair_probability_clv",
        "won",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"settled residual ledger missing columns: {missing}")
    output = frame.copy()
    output["match_id"] = output["match_id"].astype(str)
    output["match_date"] = pd.to_datetime(output["match_date"], errors="raise")
    output["hours_before_kickoff"] = output["hours_before_kickoff"].astype(int)
    if output.duplicated(KEYS).any():
        raise ValueError("duplicate opportunity keys")
    if set(output["hours_before_kickoff"].unique()) != set(CUTOFFS):
        raise ValueError("unexpected cutoff set")
    numeric = [
        "baseline_score",
        "rank_score",
        "residual_uplift",
        "observation_decimal_odds",
        "log_odds_clv",
        "fair_probability_clv",
    ]
    for column in numeric:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    if not np.isfinite(output[numeric].to_numpy(float)).all():
        raise ValueError("non-finite dose-response inputs")
    if (output["observation_decimal_odds"] <= 1.0).any():
        raise ValueError("invalid observation odds")
    reconstructed = output["rank_score"] - output["baseline_score"]
    if float(np.max(np.abs(reconstructed - output["residual_uplift"]))) > 1e-12:
        raise ValueError("residual uplift does not reconstruct rank score")

    output["baseline_ventile"] = deterministic_bins(
        output,
        group_columns=["hours_before_kickoff"],
        score_column="baseline_score",
        bins=BASELINE_BINS,
    )
    strata = ["book_slot", "hours_before_kickoff", "baseline_ventile"]
    minimum_stratum = int(output.groupby(strata).size().min())
    if minimum_stratum < DOSE_BINS:
        raise RuntimeError(f"dose stratum smaller than {DOSE_BINS}: {minimum_stratum}")
    output["dose_bin"] = deterministic_bins(
        output,
        group_columns=strata,
        score_column="residual_uplift",
        bins=DOSE_BINS,
    )
    output["uplift_z"] = np.nan
    chronological_groups: list[np.ndarray] = []
    for _, group in output.groupby(strata, sort=True):
        indices = group.index.to_numpy()
        values = output.loc[indices, "residual_uplift"].to_numpy(float)
        scale = float(values.std(ddof=0))
        if scale <= 1e-15:
            raise RuntimeError("constant residual uplift within a frozen stratum")
        output.loc[indices, "uplift_z"] = (values - values.mean()) / scale
        chronological_groups.append(
            group.sort_values(
                ["match_date", "match_id", "selected_outcome_index"],
                kind="mergesort",
            ).index.to_numpy()
        )
    output["unit_return"] = np.where(
        output["won"].astype(bool),
        output["observation_decimal_odds"] - 1.0,
        -1.0,
    )
    if not np.isfinite(output[["uplift_z", "unit_return"]].to_numpy(float)).all():
        raise RuntimeError("non-finite derived dose-response values")
    return output, chronological_groups


def statistic(frame: pd.DataFrame, value_column: str) -> dict[str, float]:
    z = frame["uplift_z"].to_numpy(float)
    dose = frame["dose_bin"].to_numpy(int)
    value = frame[value_column].to_numpy(float)
    return {
        "within_stratum_slope": float(np.dot(z, value) / np.dot(z, z)),
        "top_minus_bottom": float(value[dose == 9].mean() - value[dose == 0].mean()),
    }


def circular_shift_null(
    frame: pd.DataFrame,
    chronological_groups: list[np.ndarray],
    *,
    replicates: int,
    seed: int,
    batch_size: int = 100,
) -> pd.DataFrame:
    z = frame["uplift_z"].to_numpy(float)
    dose = frame["dose_bin"].to_numpy(np.int8)
    clv = frame["log_odds_clv"].to_numpy(float)
    returns = frame["unit_return"].to_numpy(float)
    denominator = float(np.dot(z, z))
    rng = np.random.default_rng(seed)
    result = np.empty((replicates, 4), dtype=float)

    for start in range(0, replicates, batch_size):
        width = min(batch_size, replicates - start)
        clv_numerator = np.zeros(width)
        return_numerator = np.zeros(width)
        top_clv_sum = np.zeros(width)
        bottom_clv_sum = np.zeros(width)
        top_return_sum = np.zeros(width)
        bottom_return_sum = np.zeros(width)
        top_count = np.zeros(width, dtype=np.int64)
        bottom_count = np.zeros(width, dtype=np.int64)

        for indices in chronological_groups:
            count = len(indices)
            local_z = z[indices]
            local_dose = dose[indices]
            local_clv = clv[indices]
            local_return = returns[indices]
            offsets = rng.integers(1, count, size=width)
            shifted_indices = (
                np.arange(count)[None, :] - offsets[:, None]
            ) % count
            shifted_z = local_z[shifted_indices]
            shifted_dose = local_dose[shifted_indices]
            clv_numerator += shifted_z @ local_clv
            return_numerator += shifted_z @ local_return
            top = shifted_dose == 9
            bottom = shifted_dose == 0
            top_clv_sum += top @ local_clv
            bottom_clv_sum += bottom @ local_clv
            top_return_sum += top @ local_return
            bottom_return_sum += bottom @ local_return
            top_count += top.sum(axis=1)
            bottom_count += bottom.sum(axis=1)

        result[start : start + width, 0] = clv_numerator / denominator
        result[start : start + width, 1] = (
            top_clv_sum / top_count - bottom_clv_sum / bottom_count
        )
        result[start : start + width, 2] = return_numerator / denominator
        result[start : start + width, 3] = (
            top_return_sum / top_count - bottom_return_sum / bottom_count
        )

    return pd.DataFrame(
        result,
        columns=[
            "clv_slope",
            "clv_top_minus_bottom",
            "return_slope",
            "return_top_minus_bottom",
        ],
    )


def event_cluster_bootstrap(
    frame: pd.DataFrame,
    value_column: str,
    *,
    replicates: int,
    seed: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    z = frame["uplift_z"].to_numpy(float)
    dose = frame["dose_bin"].to_numpy(int)
    value = frame[value_column].to_numpy(float)
    working = pd.DataFrame(
        {
            "match_id": frame["match_id"].astype(str),
            "slope_numerator": z * value,
            "slope_denominator": z * z,
            "top_sum": np.where(dose == 9, value, 0.0),
            "top_count": (dose == 9).astype(np.int8),
            "bottom_sum": np.where(dose == 0, value, 0.0),
            "bottom_count": (dose == 0).astype(np.int8),
        }
    )
    clusters = working.groupby("match_id", sort=True).sum().to_numpy(float)
    cluster_count = len(clusters)
    rng = np.random.default_rng(seed)
    draws = np.empty((replicates, 2), dtype=float)
    for start in range(0, replicates, batch_size):
        width = min(batch_size, replicates - start)
        indices = rng.integers(0, cluster_count, size=(width, cluster_count))
        totals = clusters[indices].sum(axis=1)
        draws[start : start + width, 0] = totals[:, 0] / totals[:, 1]
        draws[start : start + width, 1] = (
            totals[:, 2] / totals[:, 3] - totals[:, 4] / totals[:, 5]
        )
    observed = statistic(frame, value_column)
    return {
        "clusters": int(cluster_count),
        "replicates": int(replicates),
        "slope": {
            "point": observed["within_stratum_slope"],
            "ci95_low": float(np.quantile(draws[:, 0], 0.025)),
            "ci95_high": float(np.quantile(draws[:, 0], 0.975)),
            "probability_at_or_below_zero": float(
                (1 + np.sum(draws[:, 0] <= 0.0)) / (replicates + 1)
            ),
        },
        "top_minus_bottom": {
            "point": observed["top_minus_bottom"],
            "ci95_low": float(np.quantile(draws[:, 1], 0.025)),
            "ci95_high": float(np.quantile(draws[:, 1], 0.975)),
            "probability_at_or_below_zero": float(
                (1 + np.sum(draws[:, 1] <= 0.0)) / (replicates + 1)
            ),
        },
    }


def dose_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby("dose_bin", sort=True)
        .agg(
            opportunities=("match_id", "size"),
            unique_matches=("match_id", "nunique"),
            mean_residual_uplift=("residual_uplift", "mean"),
            mean_log_odds_clv=("log_odds_clv", "mean"),
            mean_fair_probability_clv=("fair_probability_clv", "mean"),
            mean_unit_return=("unit_return", "mean"),
        )
        .reset_index()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--output-root", default="artifacts/experiment-021")
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    source = Path(args.artifact_root) / "residual-settled.csv.gz"
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    frame, groups = prepare(pd.read_csv(source, low_memory=False))

    dose = dose_summary(frame)
    dose.to_csv(root / "dose-summary.csv", index=False)
    cutoff_rows: list[dict[str, Any]] = []
    for cutoff in CUTOFFS:
        group = frame[frame["hours_before_kickoff"] == cutoff]
        clv = statistic(group, "log_odds_clv")
        returns = statistic(group, "unit_return")
        cutoff_rows.append(
            {
                "cutoff_hours": cutoff,
                "opportunities": int(len(group)),
                "matches": int(group["match_id"].nunique()),
                "clv_slope": clv["within_stratum_slope"],
                "clv_top_minus_bottom": clv["top_minus_bottom"],
                "return_slope": returns["within_stratum_slope"],
                "return_top_minus_bottom": returns["top_minus_bottom"],
            }
        )
    cutoff = pd.DataFrame(cutoff_rows)
    cutoff.to_csv(root / "cutoff-dose-response.csv", index=False)

    null = circular_shift_null(
        frame,
        groups,
        replicates=args.replicates,
        seed=args.seed,
    )
    null.to_csv(root / "circular-shift-null.csv.gz", index=False, compression="gzip")
    clv_observed = statistic(frame, "log_odds_clv")
    return_observed = statistic(frame, "unit_return")
    fair_observed = statistic(frame, "fair_probability_clv")
    placebo = {
        "replicates": int(args.replicates),
        "construction": "circular shift uplift z-score and dose labels chronologically within bookmaker x cutoff x baseline-score ventile",
        "clv_slope_upper_p": upper_tail_p(
            null["clv_slope"].to_numpy(float),
            clv_observed["within_stratum_slope"],
        ),
        "clv_top_minus_bottom_upper_p": upper_tail_p(
            null["clv_top_minus_bottom"].to_numpy(float),
            clv_observed["top_minus_bottom"],
        ),
        "return_slope_upper_p": upper_tail_p(
            null["return_slope"].to_numpy(float),
            return_observed["within_stratum_slope"],
        ),
        "return_top_minus_bottom_upper_p": upper_tail_p(
            null["return_top_minus_bottom"].to_numpy(float),
            return_observed["top_minus_bottom"],
        ),
    }
    bootstrap = {
        "closing_log_clv": event_cluster_bootstrap(
            frame,
            "log_odds_clv",
            replicates=args.replicates,
            seed=args.seed + 101,
        ),
        "unit_return": event_cluster_bootstrap(
            frame,
            "unit_return",
            replicates=args.replicates,
            seed=args.seed + 202,
        ),
    }
    positive_cutoffs = int((cutoff["clv_top_minus_bottom"] > 0.0).sum())
    mechanism_passed = bool(
        placebo["clv_slope_upper_p"] <= 0.01
        and placebo["clv_top_minus_bottom_upper_p"] <= 0.01
        and bootstrap["closing_log_clv"]["slope"]["ci95_low"] > 0.0
        and bootstrap["closing_log_clv"]["top_minus_bottom"]["ci95_low"] > 0.0
        and positive_cutoffs >= 3
    )
    profit_passed = bool(
        placebo["return_slope_upper_p"] <= 0.05
        and bootstrap["unit_return"]["slope"]["ci95_low"] > 0.0
    )
    report = {
        "status": "completed",
        "experiment": "021_threshold_free_residual_dose_response",
        "source": {
            "path": str(source),
            "sha256": sha256(source),
            "opportunities": int(len(frame)),
            "matches": int(frame["match_id"].nunique()),
            "date_min": str(frame["match_date"].min().date()),
            "date_max": str(frame["match_date"].max().date()),
        },
        "frozen_construction": {
            "baseline_bins_within_cutoff": BASELINE_BINS,
            "dose_bins_within_stratum": DOSE_BINS,
            "strata": ["book_slot", "hours_before_kickoff", "baseline_ventile"],
            "candidate_identity_changed": False,
            "model_refit": False,
        },
        "observed": {
            "closing_log_clv": clv_observed,
            "fair_probability_clv": fair_observed,
            "unit_return": return_observed,
            "positive_clv_top_minus_bottom_cutoffs": positive_cutoffs,
        },
        "placebo": placebo,
        "event_cluster_bootstrap": bootstrap,
        "gate": {
            "dose_response_mechanism_passed": mechanism_passed,
            "realized_profit_validation_passed": profit_passed,
        },
        "evidence_boundary": {
            "historical_test_already_opened": True,
            "confirmatory": False,
            "live_execution_authorized": False,
            "profit_claim_authorized": False,
        },
    }
    (root / "result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
