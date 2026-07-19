from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_021_residual_dose_response as exp21


REPLICATES = 4000
SEED = 20260719
BOOK_ORDER = ("b30", "b3", "b9", "b7", "b26", "b16", "b6", "b23")
OUTCOME_ORDER = ("home", "draw", "away")
CUTOFF_ORDER = (48, 24, 12, 6)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def group_points(frame: pd.DataFrame, column: str, order: tuple[Any, ...]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key in order:
        group = frame[frame[column] == key]
        if group.empty:
            raise RuntimeError(f"empty frozen heterogeneity group {column}={key}")
        clv = exp21.statistic(group, "log_odds_clv")
        returns = exp21.statistic(group, "unit_return")
        z = group["uplift_z"].to_numpy(float)
        clv_values = group["log_odds_clv"].to_numpy(float)
        rows.append(
            {
                "dimension": column,
                "group": str(key),
                "opportunities": int(len(group)),
                "matches": int(group["match_id"].nunique()),
                "clv_slope": clv["within_stratum_slope"],
                "clv_top_minus_bottom": clv["top_minus_bottom"],
                "return_slope": returns["within_stratum_slope"],
                "return_top_minus_bottom": returns["top_minus_bottom"],
                "clv_slope_numerator": float(np.dot(z, clv_values)),
                "slope_denominator": float(np.dot(z, z)),
            }
        )
    return pd.DataFrame(rows)


def cluster_book_matrices(
    frame: pd.DataFrame,
    value_column: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if set(frame["book_slot"].unique()) != set(BOOK_ORDER):
        raise ValueError("unexpected bookmaker set")
    z = frame["uplift_z"].to_numpy(float)
    value = frame[value_column].to_numpy(float)
    working = pd.DataFrame(
        {
            "match_id": frame["match_id"].astype(str),
            "book_slot": pd.Categorical(frame["book_slot"], categories=BOOK_ORDER),
            "numerator": z * value,
            "denominator": z * z,
        }
    )
    grouped = working.groupby(["match_id", "book_slot"], observed=False)[
        ["numerator", "denominator"]
    ].sum()
    numerator = grouped["numerator"].unstack(fill_value=0.0).reindex(columns=BOOK_ORDER)
    denominator = grouped["denominator"].unstack(fill_value=0.0).reindex(columns=BOOK_ORDER)
    if not numerator.index.equals(denominator.index):
        raise RuntimeError("cluster matrices have different match index")
    return (
        numerator.index.to_numpy(dtype=str),
        numerator.to_numpy(float),
        denominator.to_numpy(float),
    )


def leave_one_book_bootstrap(
    frame: pd.DataFrame,
    value_column: str,
    *,
    replicates: int,
    seed: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    matches, numerator, denominator = cluster_book_matrices(frame, value_column)
    clusters = len(matches)
    total_num = numerator.sum(axis=0)
    total_den = denominator.sum(axis=0)
    observed = (total_num.sum() - total_num) / (total_den.sum() - total_den)
    draws = np.empty((replicates, len(BOOK_ORDER)), dtype=float)
    rng = np.random.default_rng(seed)
    probabilities = np.full(clusters, 1.0 / clusters)
    for start in range(0, replicates, batch_size):
        width = min(batch_size, replicates - start)
        weights = rng.multinomial(clusters, probabilities, size=width)
        sampled_num = weights @ numerator
        sampled_den = weights @ denominator
        draws[start : start + width] = (
            sampled_num.sum(axis=1, keepdims=True) - sampled_num
        ) / (
            sampled_den.sum(axis=1, keepdims=True) - sampled_den
        )
    return {
        "clusters": int(clusters),
        "replicates": int(replicates),
        "by_heldout_book": {
            book: {
                "point": float(observed[index]),
                "ci95_low": float(np.quantile(draws[:, index], 0.025)),
                "ci95_high": float(np.quantile(draws[:, index], 0.975)),
                "probability_at_or_below_zero": float(
                    (1 + np.sum(draws[:, index] <= 0.0)) / (replicates + 1)
                ),
            }
            for index, book in enumerate(BOOK_ORDER)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--output-root", default="artifacts/experiment-022")
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    source = Path(args.artifact_root) / "residual-settled.csv.gz"
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    frame, _ = exp21.prepare(pd.read_csv(source, low_memory=False))

    by_book = group_points(frame, "book_slot", BOOK_ORDER)
    by_outcome = group_points(frame, "selected_outcome", OUTCOME_ORDER)
    by_cutoff = group_points(frame, "hours_before_kickoff", CUTOFF_ORDER)
    by_book.to_csv(root / "by-book.csv", index=False)
    by_outcome.to_csv(root / "by-outcome.csv", index=False)
    by_cutoff.to_csv(root / "by-cutoff.csv", index=False)

    positive_numerator = by_book["clv_slope_numerator"].clip(lower=0.0)
    positive_total = float(positive_numerator.sum())
    contribution = {
        str(row["group"]): {
            "clv_slope_numerator": float(row["clv_slope_numerator"]),
            "positive_contribution_share": float(
                positive_numerator.iloc[index] / positive_total
            )
            if positive_total > 0
            else 0.0,
        }
        for index, (_, row) in enumerate(by_book.iterrows())
    }
    largest_positive_share = (
        float(positive_numerator.max() / positive_total) if positive_total > 0 else 1.0
    )

    leave_one_out = {
        "closing_log_clv": leave_one_book_bootstrap(
            frame,
            "log_odds_clv",
            replicates=args.replicates,
            seed=args.seed + 100,
        ),
        "unit_return": leave_one_book_bootstrap(
            frame,
            "unit_return",
            replicates=args.replicates,
            seed=args.seed + 200,
        ),
    }
    positive_books = int((by_book["clv_slope"] > 0.0).sum())
    positive_outcomes = int((by_outcome["clv_slope"] > 0.0).sum())
    positive_cutoffs = int((by_cutoff["clv_slope"] > 0.0).sum())
    all_clv_loo_lower_positive = all(
        values["ci95_low"] > 0.0
        for values in leave_one_out["closing_log_clv"]["by_heldout_book"].values()
    )
    all_return_loo_lower_positive = all(
        values["ci95_low"] > 0.0
        for values in leave_one_out["unit_return"]["by_heldout_book"].values()
    )
    mechanism_passed = bool(
        positive_books >= 6
        and positive_outcomes == len(OUTCOME_ORDER)
        and positive_cutoffs == len(CUTOFF_ORDER)
        and all_clv_loo_lower_positive
        and largest_positive_share <= 0.50
    )
    profit_passed = bool(all_return_loo_lower_positive)

    report = {
        "status": "completed",
        "experiment": "022_residual_dose_response_heterogeneity",
        "source": {
            "path": str(source),
            "sha256": sha256(source),
            "opportunities": int(len(frame)),
            "matches": int(frame["match_id"].nunique()),
        },
        "frozen_construction": {
            "reused_experiment_021": True,
            "baseline_bins_within_cutoff": exp21.BASELINE_BINS,
            "dose_bins_within_stratum": exp21.DOSE_BINS,
            "bookmakers": list(BOOK_ORDER),
            "selected_outcomes": list(OUTCOME_ORDER),
            "cutoffs": list(CUTOFF_ORDER),
            "segment_specific_retuning": False,
        },
        "point_signs": {
            "positive_book_slopes": positive_books,
            "book_count": len(BOOK_ORDER),
            "positive_outcome_slopes": positive_outcomes,
            "outcome_count": len(OUTCOME_ORDER),
            "positive_cutoff_slopes": positive_cutoffs,
            "cutoff_count": len(CUTOFF_ORDER),
        },
        "book_concentration": {
            "by_book": contribution,
            "largest_positive_contribution_share": largest_positive_share,
        },
        "leave_one_book_out": leave_one_out,
        "gate": {
            "mechanism_heterogeneity_passed": mechanism_passed,
            "profit_heterogeneity_passed": profit_passed,
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
