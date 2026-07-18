from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_006_independent_residual_outcome as exp6
import experiment_008_named_book_clv as exp8
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import (
    CUTOFFS,
    DOWNLOAD_URL,
    SELECTED_BOOKS,
    SERIES_FILES,
    download,
    extract_required,
)


RANDOM_SEED = 20260718
OUTCOMES = ("home", "draw", "away")


def load_outcomes(paths: list[Path]) -> tuple[pd.DataFrame, dict[str, Any]]:
    pieces: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(
            path,
            usecols=["match_id", "match_date", "score_home", "score_away"],
            low_memory=False,
        )
        pieces.append(frame)
    outcomes = pd.concat(pieces, ignore_index=True)
    outcomes["match_id"] = outcomes["match_id"].astype(str)
    outcomes["match_date"] = pd.to_datetime(outcomes["match_date"], errors="coerce")
    outcomes["score_home"] = pd.to_numeric(outcomes["score_home"], errors="coerce")
    outcomes["score_away"] = pd.to_numeric(outcomes["score_away"], errors="coerce")
    outcomes = outcomes.dropna(subset=["match_id", "match_date", "score_home", "score_away"]).copy()

    conflicts = outcomes.groupby("match_id")[["match_date", "score_home", "score_away"]].nunique(dropna=False)
    conflicts = conflicts[
        (conflicts["match_date"] > 1)
        | (conflicts["score_home"] > 1)
        | (conflicts["score_away"] > 1)
    ]
    if not conflicts.empty:
        raise ValueError(f"conflicting outcome metadata for {len(conflicts)} match IDs")

    outcomes = outcomes.drop_duplicates("match_id", keep="first").copy()
    home = outcomes["score_home"].to_numpy(dtype=float)
    away = outcomes["score_away"].to_numpy(dtype=float)
    outcomes["winning_outcome"] = np.where(home > away, "home", np.where(home == away, "draw", "away"))
    return outcomes[["match_id", "match_date", "score_home", "score_away", "winning_outcome"]], {
        "matches": int(len(outcomes)),
        "winning_outcome_counts": {str(k): int(v) for k, v in outcomes["winning_outcome"].value_counts().sort_index().items()},
    }


def attach_prices_before_outcomes(strategy: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    keys = ["match_id", "hours_before_kickoff", "book_slot"]
    price_columns = keys + [f"observation_raw_{outcome}" for outcome in OUTCOMES]
    prices = test[price_columns].copy()
    if prices.duplicated(keys).any():
        raise RuntimeError("duplicate test price keys")
    enriched = strategy.merge(prices, on=keys, how="left", validate="many_to_one")
    if enriched[[f"observation_raw_{outcome}" for outcome in OUTCOMES]].isna().any().any():
        raise RuntimeError("strategy price join left missing observation odds")
    observation = np.select(
        [
            enriched["selected_outcome"].to_numpy() == "home",
            enriched["selected_outcome"].to_numpy() == "draw",
            enriched["selected_outcome"].to_numpy() == "away",
        ],
        [
            enriched["observation_raw_home"].to_numpy(dtype=float),
            enriched["observation_raw_draw"].to_numpy(dtype=float),
            enriched["observation_raw_away"].to_numpy(dtype=float),
        ],
        default=np.nan,
    )
    enriched["observation_decimal_odds"] = observation
    if not np.isfinite(observation).all() or np.any(observation <= 1.0):
        raise ValueError("invalid selected observation decimal odds")
    enriched.drop(columns=[f"observation_raw_{outcome}" for outcome in OUTCOMES], inplace=True)
    return enriched


def settle_after_selection(strategy_with_prices: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    settled = strategy_with_prices.merge(outcomes, on="match_id", how="inner", validate="many_to_one")
    if len(settled) != len(strategy_with_prices):
        raise RuntimeError(
            f"outcome join lost strategy rows: {len(strategy_with_prices)} -> {len(settled)}"
        )
    settled["won"] = settled["selected_outcome"].to_numpy() == settled["winning_outcome"].to_numpy()
    settled["net_return"] = np.where(
        settled["traded"].to_numpy(dtype=bool),
        np.where(
            settled["won"].to_numpy(dtype=bool),
            settled["observation_decimal_odds"].to_numpy(dtype=float) - 1.0,
            -1.0,
        ),
        0.0,
    )
    settled["observation_time_proxy"] = settled["match_date"] - pd.to_timedelta(
        settled["hours_before_kickoff"].to_numpy(dtype=int) - 1,
        unit="h",
    )
    keys = ["match_id", "hours_before_kickoff"]
    if settled.duplicated(keys).any():
        raise RuntimeError("duplicate settled match/cutoff opportunity")
    return settled


def maximum_drawdown(trades: pd.DataFrame) -> dict[str, float]:
    ordered = trades.sort_values(
        ["observation_time_proxy", "match_id", "hours_before_kickoff"],
        ascending=[True, True, False],
        kind="mergesort",
    )
    cumulative = ordered["net_return"].to_numpy(dtype=float).cumsum()
    if len(cumulative) == 0:
        return {"maximum_drawdown_units": 0.0, "ending_profit_units": 0.0, "peak_profit_units": 0.0}
    running_peak = np.maximum.accumulate(np.concatenate([[0.0], cumulative]))[1:]
    drawdown = running_peak - cumulative
    return {
        "maximum_drawdown_units": float(drawdown.max(initial=0.0)),
        "ending_profit_units": float(cumulative[-1]),
        "peak_profit_units": float(running_peak.max(initial=0.0)),
    }


def grouped_metrics(trades: pd.DataFrame, column: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    total_trades = len(trades)
    for value, group in trades.groupby(column, sort=True):
        output[str(value)] = {
            "trades": int(len(group)),
            "trade_share": float(len(group) / total_trades),
            "wins": int(group["won"].sum()),
            "hit_rate": float(group["won"].mean()),
            "mean_decimal_odds": float(group["observation_decimal_odds"].mean()),
            "total_profit_units": float(group["net_return"].sum()),
            "roi": float(group["net_return"].mean()),
            "mean_log_odds_clv": float(group["log_odds_clv"].mean()),
        }
    return output


def strategy_return_metrics(settled: pd.DataFrame) -> dict[str, Any]:
    trades = settled[settled["traded"]].copy()
    if trades.empty:
        raise RuntimeError("frozen strategy produced no trades")
    trade_bootstrap = exp6.bootstrap_match_improvement(
        trades["match_id"].to_numpy(),
        trades["net_return"].to_numpy(dtype=float),
        replicates=1000,
    )
    opportunity_bootstrap = exp6.bootstrap_match_improvement(
        settled["match_id"].to_numpy(),
        settled["net_return"].to_numpy(dtype=float),
        replicates=1000,
    )
    return {
        "opportunities": int(len(settled)),
        "opportunity_matches": int(settled["match_id"].nunique()),
        "trades": int(len(trades)),
        "trade_matches": int(trades["match_id"].nunique()),
        "trade_fraction": float(len(trades) / len(settled)),
        "wins": int(trades["won"].sum()),
        "hit_rate": float(trades["won"].mean()),
        "mean_decimal_odds": float(trades["observation_decimal_odds"].mean()),
        "median_decimal_odds": float(trades["observation_decimal_odds"].median()),
        "total_flat_stake_profit_units": float(trades["net_return"].sum()),
        "roi_per_trade": float(trades["net_return"].mean()),
        "mean_return_per_opportunity": float(settled["net_return"].mean()),
        "trade_roi_match_bootstrap": trade_bootstrap,
        "opportunity_return_match_bootstrap": opportunity_bootstrap,
        "mean_trade_log_odds_clv": float(trades["log_odds_clv"].mean()),
        "mean_trade_fair_probability_clv": float(trades["fair_probability_clv"].mean()),
        "drawdown": maximum_drawdown(trades),
        "by_cutoff": grouped_metrics(trades, "hours_before_kickoff"),
        "by_bookmaker": grouped_metrics(trades, "bookmaker_name"),
        "by_selected_outcome": grouped_metrics(trades, "selected_outcome"),
    }


def compare_returns(baseline: pd.DataFrame, augmented: pd.DataFrame) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    columns = keys + ["traded", "book_slot", "selected_outcome", "net_return"]
    joined = baseline[columns].merge(
        augmented[columns],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_augmented"),
    )
    if len(joined) != len(baseline) or len(joined) != len(augmented):
        raise RuntimeError("baseline and augmented opportunity universes differ")
    difference = (
        joined["net_return_augmented"].to_numpy(dtype=float)
        - joined["net_return_baseline"].to_numpy(dtype=float)
    )
    bootstrap = exp6.bootstrap_match_improvement(
        joined["match_id"].to_numpy(),
        difference,
        replicates=1000,
    )
    baseline_traded = joined["traded_baseline"].to_numpy(dtype=bool)
    augmented_traded = joined["traded_augmented"].to_numpy(dtype=bool)
    both = baseline_traded & augmented_traded
    same_selection = (
        both
        & (joined["book_slot_baseline"].to_numpy() == joined["book_slot_augmented"].to_numpy())
        & (joined["selected_outcome_baseline"].to_numpy() == joined["selected_outcome_augmented"].to_numpy())
    )
    union = baseline_traded | augmented_traded
    return {
        "opportunities": int(len(joined)),
        "mean_augmented_minus_baseline_return_per_opportunity": float(difference.mean()),
        "total_augmented_minus_baseline_profit_units": float(difference.sum()),
        "paired_match_bootstrap": bootstrap,
        "baseline_trades": int(baseline_traded.sum()),
        "augmented_trades": int(augmented_traded.sum()),
        "trade_opportunity_overlap": int(both.sum()),
        "trade_opportunity_jaccard": float(both.sum() / union.sum()) if union.sum() else 0.0,
        "same_book_and_outcome_when_both_trade": int(same_selection.sum()),
        "same_selection_fraction_among_overlap": float(same_selection.sum() / both.sum()) if both.sum() else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit realized returns of frozen Experiment 008 strategies.")
    parser.add_argument("--output-root", default="artifacts/experiment-009")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress_path = root / "progress.json"
    failure_path = root / "failure.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True), encoding="utf-8")

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("reconstructing_frozen_experiment_008")
        datasets = residual_gen.build_all_state_records(source_paths, chunksize=args.chunksize)
        diagnostics = datasets.pop("diagnostics")
        hazard, movement_models, training_counts = residual_gen.train_frozen_models(
            datasets["train"],
            hazard_max=args.hazard_max_train,
            movement_max=args.movement_max_train,
        )

        residual_frames: dict[str, pd.DataFrame] = {}
        x_frames: dict[str, pd.DataFrame] = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            residual_frames[split] = residual_gen.build_residual_frame(
                split, datasets[split], hazard, movement_models
            )
            x_frames[split], columns = exp8.x_frame(datasets[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif raw_x_columns != columns:
                raise RuntimeError("raw X schemas differ")
        assert raw_x_columns is not None

        future, future_profile = exp8.build_future_prices(
            source_paths,
            [residual_frames["validation"], residual_frames["test"]],
            chunksize=args.chunksize,
        )
        validation, baseline_columns, augmented_columns = exp8.model_frame(
            residual_frames["validation"], x_frames["validation"], future, raw_x_columns
        )
        test, baseline_test, augmented_test = exp8.model_frame(
            residual_frames["test"], x_frames["test"], future, raw_x_columns
        )
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test model schemas differ")

        progress("training_frozen_repricing_models")
        baseline_hazard = exp8.fixed_classifier()
        augmented_hazard = exp8.fixed_classifier()
        baseline_hazard.fit(validation[baseline_columns], validation["future_move"])
        augmented_hazard.fit(validation[augmented_columns], validation["future_move"])
        baseline_probability = baseline_hazard.predict_proba(test[baseline_columns])[:, 1]
        augmented_probability = augmented_hazard.predict_proba(test[augmented_columns])[:, 1]

        validation_movers = validation[validation["future_move"] == 1].copy()
        baseline_delta = np.empty((len(test), 3), dtype=float)
        augmented_delta = np.empty((len(test), 3), dtype=float)
        for outcome_index, target in enumerate(exp8.TARGET_DELTA_COLUMNS):
            baseline_model = exp8.fixed_regressor()
            augmented_model = exp8.fixed_regressor()
            baseline_model.fit(validation_movers[baseline_columns], validation_movers[target])
            augmented_model.fit(validation_movers[augmented_columns], validation_movers[target])
            baseline_delta[:, outcome_index] = baseline_model.predict(test[baseline_columns])
            augmented_delta[:, outcome_index] = augmented_model.predict(test[augmented_columns])

        baseline_strategy = exp8.strategy_candidates(
            test,
            baseline_probability[:, None] * baseline_delta,
            "baseline",
        )
        augmented_strategy = exp8.strategy_candidates(
            test,
            augmented_probability[:, None] * augmented_delta,
            "augmented",
        )

        progress("attaching_frozen_prices_before_outcomes")
        baseline_with_prices = attach_prices_before_outcomes(baseline_strategy, test)
        augmented_with_prices = attach_prices_before_outcomes(augmented_strategy, test)

        progress("loading_outcomes_after_strategy_freeze")
        outcomes, outcome_profile = load_outcomes(source_paths)
        baseline_settled = settle_after_selection(baseline_with_prices, outcomes)
        augmented_settled = settle_after_selection(augmented_with_prices, outcomes)

        progress("computing_realized_return_audit")
        baseline_metrics = strategy_return_metrics(baseline_settled)
        augmented_metrics = strategy_return_metrics(augmented_settled)
        comparison = compare_returns(baseline_settled, augmented_settled)

        report = {
            "experiment": "009_frozen_named_book_realized_return_audit",
            "status": "completed",
            "evidentiary_status": "diagnostic_not_confirmatory_outcome_period_previously_opened",
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "future_price_profile": future_profile,
            "outcome_profile": outcome_profile,
            "baseline_strategy": baseline_metrics,
            "augmented_strategy": augmented_metrics,
            "strategy_comparison": comparison,
            "execution_assumptions": {
                "stake": "one unit per frozen trade",
                "price": "selected named-book decimal quote at residual-observation timestamp",
                "commission": 0,
                "slippage": 0,
                "rejections_limits_latency": "not modeled",
            },
        }
        (root / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        baseline_settled.to_csv(root / "baseline_settled.csv.gz", index=False, compression="gzip")
        augmented_settled.to_csv(root / "augmented_settled.csv.gz", index=False, compression="gzip")
        print(json.dumps(report, indent=2, sort_keys=True))
        failure_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "progress": json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else None,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
