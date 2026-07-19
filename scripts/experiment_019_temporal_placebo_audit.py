from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEYS = ["match_id", "hours_before_kickoff"]
FRACTION = 0.05


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def upper_p(values: np.ndarray, observed: float) -> float:
    return float((1 + np.sum(values >= observed)) / (len(values) + 1))


def select_top(score: np.ndarray, indices: np.ndarray, count: int) -> np.ndarray:
    values = score[indices]
    eligible = indices[values > 0]
    eligible_values = values[values > 0]
    if len(eligible) < count:
        raise RuntimeError("placebo lacks positive-score capacity")
    return eligible[np.argpartition(eligible_values, -count)[-count:]]


def clustered_bootstrap(frame: pd.DataFrame, block: str, value: str, reps: int, seed: int) -> dict:
    g = frame.groupby(block)[value].agg(["sum", "count"])
    sums, counts = g["sum"].to_numpy(float), g["count"].to_numpy(int)
    rng = np.random.default_rng(seed)
    draws = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, len(g), len(g))
        draws[i] = sums[idx].sum() / counts[idx].sum()
    return {
        "blocks": int(len(g)),
        "point_mean_per_opportunity": float(frame[value].mean()),
        "ci95_low": float(np.quantile(draws, 0.025)),
        "ci95_high": float(np.quantile(draws, 0.975)),
        "probability_at_or_below_zero": float((1 + np.sum(draws <= 0)) / (reps + 1)),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-root", required=True)
    p.add_argument("--output-root", default="artifacts/experiment-019")
    p.add_argument("--replicates", type=int, default=4000)
    p.add_argument("--seed", type=int, default=20260719)
    args = p.parse_args()
    source, out = Path(args.artifact_root), Path(args.output_root)
    out.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(source / "raw-settled.csv.gz", parse_dates=["match_date"])
    residual = pd.read_csv(source / "residual-settled.csv.gz", parse_dates=["match_date"])
    if raw.duplicated(KEYS).any() or residual.duplicated(KEYS).any():
        raise ValueError("duplicate opportunity keys")
    check = raw[KEYS + ["book_slot", "selected_outcome"]].merge(
        residual[KEYS + ["book_slot", "selected_outcome"]], on=KEYS,
        validate="one_to_one", suffixes=("_raw", "_residual")
    )
    if len(check) != len(raw) or len(raw) != len(residual):
        raise ValueError("opportunity universes differ")
    if not (check.book_slot_raw == check.book_slot_residual).all() or not (
        check.selected_outcome_raw == check.selected_outcome_residual
    ).all():
        raise ValueError("candidate identity changed")

    raw_sel, res_sel = raw.traded.to_numpy(bool), residual.traded.to_numpy(bool)
    if raw_sel.sum() != res_sel.sum():
        raise ValueError("matched budgets differ")
    returns = np.where(residual.won.to_numpy(bool), residual.observation_decimal_odds.to_numpy(float) - 1, -1)
    clv = residual.log_odds_clv.to_numpy(float)
    raw_profit, res_profit = float(returns[raw_sel].sum()), float(returns[res_sel].sum())
    raw_clv, res_clv = float(clv[raw_sel].sum()), float(clv[res_sel].sum())

    paired = residual[KEYS + ["match_date"]].copy()
    delta = res_sel.astype(np.int8) - raw_sel.astype(np.int8)
    paired["incremental_return"] = returns * delta
    paired["incremental_log_clv"] = clv * delta
    paired["day"] = paired.match_date.dt.strftime("%Y-%m-%d")
    paired["week"] = paired.match_date.dt.to_period("W-MON").astype(str)
    weekly = paired.groupby("week").agg(
        opportunities=("match_id", "size"), matches=("match_id", "nunique"),
        incremental_profit_units=("incremental_return", "sum"),
        incremental_log_clv_sum=("incremental_log_clv", "sum"),
    )
    weekly.to_csv(out / "weekly-stability.csv")
    total_profit, total_clv = res_profit - raw_profit, res_clv - raw_clv
    loo = pd.DataFrame({
        "week": weekly.index,
        "incremental_profit_without_week": total_profit - weekly.incremental_profit_units,
        "incremental_log_clv_without_week": total_clv - weekly.incremental_log_clv_sum,
    })
    loo.to_csv(out / "leave-one-week-out.csv", index=False)

    rows = np.arange(len(residual))
    hours = residual.hours_before_kickoff.to_numpy(int)
    baseline = residual.baseline_score.to_numpy(float)
    uplift = residual.residual_uplift.to_numpy(float)
    cutoffs = sorted(np.unique(hours))
    cutoff_rows = {h: rows[hours == h] for h in cutoffs}
    counts = {h: int(np.floor(len(cutoff_rows[h]) * FRACTION)) for h in cutoffs}
    ordered = residual.assign(_row=rows).sort_values(["match_date", "match_id", "book_slot"])
    groups = [g._row.to_numpy(int) for _, g in ordered.groupby(["book_slot", "hours_before_kickoff"])]
    shifted = np.empty_like(uplift)
    rng = np.random.default_rng(args.seed)
    null_profit, null_clv = np.empty(args.replicates), np.empty(args.replicates)
    for r in range(args.replicates):
        for idx in groups:
            shifted[idx] = np.roll(uplift[idx], int(rng.integers(1, len(idx)))) if len(idx) > 1 else uplift[idx]
        placebo = baseline + shifted
        chosen = np.zeros(len(residual), bool)
        for h in cutoffs:
            chosen[select_top(placebo, cutoff_rows[h], counts[h])] = True
        if chosen.sum() != res_sel.sum():
            raise RuntimeError("placebo capacity changed")
        null_profit[r], null_clv[r] = returns[chosen].sum(), clv[chosen].sum()
    pd.DataFrame({"placebo_profit_units": null_profit, "placebo_log_clv_sum": null_clv}).to_csv(
        out / "circular-shift-null.csv.gz", index=False, compression="gzip"
    )

    boot = {
        metric: {
            block: clustered_bootstrap(paired, block, metric, args.replicates, args.seed + offset)
            for block, offset in (("match_id", 100), ("day", 200), ("week", 300))
        }
        for metric in ("incremental_return", "incremental_log_clv")
    }
    placebo = {
        "construction": "circular shift residual_uplift within bookmaker x cutoff; add to unchanged baseline score; reselect exact 5%",
        "replicates": args.replicates,
        "observed_residual_profit_units": res_profit,
        "placebo_profit_mean": float(null_profit.mean()),
        "placebo_profit_q95": float(np.quantile(null_profit, 0.95)),
        "observed_profit_upper_p": upper_p(null_profit, res_profit),
        "observed_incremental_profit_units": total_profit,
        "placebo_incremental_profit_mean": float((null_profit - raw_profit).mean()),
        "observed_incremental_profit_upper_p": upper_p(null_profit - raw_profit, total_profit),
        "observed_residual_log_clv_sum": res_clv,
        "placebo_log_clv_mean": float(null_clv.mean()),
        "placebo_log_clv_q95": float(np.quantile(null_clv, 0.95)),
        "observed_log_clv_upper_p": upper_p(null_clv, res_clv),
        "observed_incremental_log_clv_sum": total_clv,
        "placebo_incremental_log_clv_mean": float((null_clv - raw_clv).mean()),
        "observed_incremental_log_clv_upper_p": upper_p(null_clv - raw_clv, total_clv),
    }
    temporal = {
        "weeks": int(len(weekly)),
        "weeks_positive_incremental_profit": int((weekly.incremental_profit_units > 0).sum()),
        "weeks_positive_incremental_log_clv": int((weekly.incremental_log_clv_sum > 0).sum()),
        "minimum_leave_one_week_incremental_profit": float(loo.incremental_profit_without_week.min()),
        "minimum_leave_one_week_incremental_log_clv": float(loo.incremental_log_clv_without_week.min()),
    }
    mechanism = placebo["observed_incremental_log_clv_upper_p"] <= 0.01 and placebo["observed_log_clv_upper_p"] <= 0.01 and temporal["minimum_leave_one_week_incremental_log_clv"] > 0
    profit_valid = placebo["observed_incremental_profit_upper_p"] <= 0.05 and boot["incremental_return"]["week"]["ci95_low"] > 0
    report = {
        "status": "completed",
        "experiment": "019_temporal_stability_and_residual_uplift_placebo_audit",
        "source_hashes": {"raw": sha256(source / "raw-settled.csv.gz"), "residual": sha256(source / "residual-settled.csv.gz")},
        "evidence_boundary": {"historical_opened_test": True, "confirmatory": False, "profit_claim": False},
        "opportunities": int(len(residual)), "unique_matches": int(residual.match_id.nunique()),
        "date_min": residual.match_date.min().date().isoformat(), "date_max": residual.match_date.max().date().isoformat(),
        "trades_per_policy": int(res_sel.sum()),
        "observed": {"raw_profit_units": raw_profit, "residual_profit_units": res_profit, "incremental_profit_units": total_profit, "raw_log_clv_sum": raw_clv, "residual_log_clv_sum": res_clv, "incremental_log_clv_sum": total_clv},
        "temporal_stability": temporal, "cluster_robustness": boot, "residual_uplift_placebo": placebo,
        "gate": {"mechanism_falsification_passed": bool(mechanism), "profit_validation_passed": bool(profit_valid)},
    }
    (out / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
