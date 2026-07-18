from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


DATASET_SLUG = "eladsil/football-games-odds"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
CUTOFFS = (48, 24, 12, 6, 3, 1)
RANDOM_SEED = 20260718


def download(url: str, path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256(); total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk: continue
                digest.update(chunk); total += len(chunk); fh.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "final_url": str(response.url)}


def devig(odds: np.ndarray) -> tuple[np.ndarray, float]:
    implied = 1.0 / odds
    total = float(implied.sum())
    return implied / total, total - 1.0


def reconstruct_states(odds_path: Path) -> pd.DataFrame:
    df = pd.read_csv(odds_path)
    df["date_start"] = pd.to_datetime(df["date_start"], format="%m/%d/%Y %H:%M", errors="coerce")
    df["date_created"] = pd.to_datetime(df["date_created"], format="%m/%d/%Y %H:%M", errors="coerce")
    for col in ("home_team_odd", "tie_odd", "away_team_odd"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["match_id", "date_start", "date_created", "home_team_odd", "tie_odd", "away_team_odd"])
    df = df[(df["date_created"] <= df["date_start"]) & (df[["home_team_odd", "tie_odd", "away_team_odd"]] > 1.0).all(axis=1)]
    df.sort_values(["match_id", "date_created"], inplace=True)

    records: list[dict[str, Any]] = []
    for match_id, group in df.groupby("match_id", sort=False):
        start = group["date_start"].iloc[0]
        times_ns = group["date_created"].astype("int64").to_numpy()
        odds = group[["home_team_odd", "tie_odd", "away_team_odd"]].to_numpy(dtype=float)
        if len(times_ns) == 0: continue

        def state_at(ts: pd.Timestamp) -> tuple[int, np.ndarray] | None:
            idx = int(np.searchsorted(times_ns, ts.value, side="right") - 1)
            return None if idx < 0 else (idx, odds[idx])

        for hours in CUTOFFS:
            prior_t = start - pd.Timedelta(hours=hours + 1)
            current_t = start - pd.Timedelta(hours=hours)
            next_t = start - pd.Timedelta(hours=max(hours - 1, 0))
            prior = state_at(prior_t); current = state_at(current_t); nxt = state_at(next_t)
            if prior is None or current is None or nxt is None: continue
            prior_idx, prior_odds = prior; current_idx, current_odds = current; next_idx, next_odds = nxt
            prior_p, prior_over = devig(prior_odds); current_p, current_over = devig(current_odds)
            y_move = int(np.any(np.abs(next_odds - current_odds) > 1e-12))

            def count_since(window_hours: int) -> int:
                left = np.searchsorted(times_ns, (current_t - pd.Timedelta(hours=window_hours)).value, side="right")
                right = np.searchsorted(times_ns, current_t.value, side="right")
                return int(max(0, right - left))

            last_update_hours = max(0.0, (current_t - pd.Timestamp(times_ns[current_idx])).total_seconds() / 3600.0)
            rec = {
                "match_id": str(match_id), "kickoff": start, "hours": hours, "y": y_move,
                "cur_h": current_p[0], "cur_d": current_p[1], "cur_a": current_p[2],
                "prev_h": prior_p[0], "prev_d": prior_p[1], "prev_a": prior_p[2],
                "delta_h": current_p[0] - prior_p[0], "delta_d": current_p[1] - prior_p[1], "delta_a": current_p[2] - prior_p[2],
                "overround": current_over, "prev_overround": prior_over, "overround_delta": current_over - prior_over,
                "hours_since_last_update": last_update_hours,
                "updates_1h": count_since(1), "updates_6h": count_since(6), "updates_24h": count_since(24),
                "hours_scaled": hours / 48.0,
            }
            records.append(rec)
    return pd.DataFrame.from_records(records)


def split_label(kickoff: pd.Series) -> np.ndarray:
    dates = pd.to_datetime(kickoff)
    out = np.full(len(dates), "test", dtype=object)
    out[dates <= pd.Timestamp("2017-10-31 23:59:59")] = "train"
    out[(dates >= pd.Timestamp("2017-11-01")) & (dates <= pd.Timestamp("2017-12-31 23:59:59"))] = "validation"
    return out


def baseline_rates(train: pd.DataFrame) -> dict[int, float]:
    rates = {}
    for hours in CUTOFFS:
        sub = train[train["hours"] == hours]
        rates[hours] = (float(sub["y"].sum()) + 1.0) / (len(sub) + 2.0)
    return rates


def predict_baseline(frame: pd.DataFrame, rates: dict[int, float]) -> np.ndarray:
    return frame["hours"].map(rates).to_numpy(dtype=float)


def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    p = np.clip(p, 1e-8, 1 - 1e-8)
    return {
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan"),
        "move_rate": float(y.mean()), "mean_prediction": float(p.mean()),
    }


def bootstrap_match(frame: pd.DataFrame, base_p: np.ndarray, model_p: np.ndarray, reps: int = 500) -> dict[str, Any]:
    y = frame["y"].to_numpy(dtype=float)
    improvement = (y - base_p) ** 2 - (y - model_p) ** 2
    temp = pd.DataFrame({"match_id": frame["match_id"].to_numpy(), "improvement": improvement})
    values = temp.groupby("match_id", sort=False)["improvement"].mean().to_numpy()
    rng = np.random.default_rng(RANDOM_SEED); draws = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, len(values), size=len(values)); draws[i] = values[idx].mean()
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {"matches": int(len(values)), "mean_improvement": float(values.mean()), "ci95_low": float(lo), "ci95_high": float(hi), "replicates": reps}


def evaluate(frame: pd.DataFrame, p: np.ndarray, base: np.ndarray) -> dict[str, Any]:
    y = frame["y"].to_numpy(dtype=int)
    bm, mm = metrics(y, base), metrics(y, p)
    by_cutoff = {}
    for hours in CUTOFFS:
        mask = frame["hours"].to_numpy() == hours
        b, m = metrics(y[mask], base[mask]), metrics(y[mask], p[mask])
        by_cutoff[f"T-{hours}h"] = {"states": int(mask.sum()), "baseline_brier": b["brier"], "model_brier": m["brier"], "brier_improvement": b["brier"] - m["brier"]}
    boot = bootstrap_match(frame, base, p)
    improved = sum(1 for item in by_cutoff.values() if item["brier_improvement"] > 0)
    checks = {"overall_brier_better": bm["brier"] > mm["brier"], "bootstrap_ci_above_zero": boot["ci95_low"] > 0, "improved_at_least_4_of_6_cutoffs": improved >= 4}
    return {"states": int(len(frame)), "baseline": bm, "model": mm, "brier_improvement": bm["brier"] - mm["brier"], "relative_brier_improvement": (bm["brier"] - mm["brier"]) / bm["brier"], "by_cutoff": by_cutoff, "match_bootstrap": boot, "replication_supported": all(checks.values()), "checks": checks, "improved_cutoffs": improved}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run independent exact-timestamp move-hazard replication.")
    parser.add_argument("--output-root", default="artifacts/experiment-004")
    args = parser.parse_args()
    root = Path(args.output_root); root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"; extracted = root / "extracted"
    archive_meta = download(DOWNLOAD_URL, archive)
    if extracted.exists(): shutil.rmtree(extracted)
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf: zf.extractall(extracted)
    states = reconstruct_states(extracted / "Matches_Odds.csv")
    states["split"] = split_label(states["kickoff"])
    train, val, test = (states[states["split"] == label].copy() for label in ("train", "validation", "test"))
    feature_cols = ["cur_h","cur_d","cur_a","prev_h","prev_d","prev_a","delta_h","delta_d","delta_a","overround","prev_overround","overround_delta","hours_since_last_update","updates_1h","updates_6h","updates_24h","hours_scaled"]
    rates = baseline_rates(train)
    logistic = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=250, solver="lbfgs"))
    logistic.fit(train[feature_cols], train["y"])
    hgb = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=1.0, random_state=RANDOM_SEED)
    hgb.fit(train[feature_cols], train["y"])
    results = []
    for name, predictor in (("logistic_c1", lambda x: logistic.predict_proba(x)[:,1]), ("hist_gradient_boosting_fixed", lambda x: hgb.predict_proba(x)[:,1])):
        splits = {}
        for label, frame in (("validation", val), ("test", test)):
            p = predictor(frame[feature_cols]); base = predict_baseline(frame, rates)
            splits[label] = evaluate(frame, p, base)
        results.append({"model": name, "splits": splits, "replication_supported": splits["test"]["replication_supported"]})
    report = {"experiment":"004_independent_exact_timestamp_hazard", "archive":archive_meta, "state_rows":int(len(states)), "unique_matches":int(states["match_id"].nunique()), "split_counts":{k:int(v) for k,v in states["split"].value_counts().items()}, "training_baseline_rates":{f"T-{k}h":v for k,v in rates.items()}, "models":results, "any_replication_supported":any(r["replication_supported"] for r in results)}
    (root/"result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
