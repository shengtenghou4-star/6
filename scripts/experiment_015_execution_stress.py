from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import experiment_008_named_book_clv as exp8
import experiment_009_frozen_return_audit as exp9
import experiment_011_closing_line_residual as exp11
import experiment_013_selection_ranking_decomposition as exp13
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import (
    BOOKMAKER_NAMES,
    CUTOFFS,
    DOWNLOAD_URL,
    OUTCOMES,
    SELECTED_BOOKS,
    SERIES_FILES,
    download,
    extract_required,
    raw_and_devig,
)
from marketlab.execution_stress import (
    ExecutionScenario,
    apply_execution_scenario,
    compare_scenario_ledgers,
    default_scenarios,
    event_cluster_bootstrap,
    scenario_metrics,
    scenario_to_dict,
)


SIGNAL_HOURS = exp11.SIGNAL_HOURS
DELAYS = (0, 1, 2, 3)


def build_execution_prices(
    paths: list[Path],
    identity: pd.DataFrame,
    *,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {
        "match_id",
        "hours_before_kickoff",
        "book_slot",
        "selected_outcome_index",
        "selected_outcome",
    }
    missing = sorted(required - set(identity.columns))
    if missing:
        raise ValueError(f"identity missing columns: {missing}")
    keys = ["match_id", "hours_before_kickoff", "book_slot"]
    if identity.duplicated(keys).any():
        raise ValueError("duplicate execution-price identity")
    wanted_frame = identity[[*keys, "selected_outcome_index", "selected_outcome"]].copy()
    wanted_frame["match_id"] = wanted_frame["match_id"].astype(str)
    wanted_frame["book"] = wanted_frame["book_slot"].str.removeprefix("b").astype(int)
    wanted: dict[tuple[int, int], dict[str, int]] = {}
    for (hours, book), group in wanted_frame.groupby(
        ["hours_before_kickoff", "book"], sort=False
    ):
        wanted[(int(hours), int(book))] = dict(
            zip(
                group["match_id"].astype(str),
                group["selected_outcome_index"].astype(int),
                strict=True,
            )
        )

    needed_indices = sorted(
        {
            CUTOFFS[hours] + 1 + delay
            for hours in SIGNAL_HOURS
            for delay in DELAYS
        }
    )
    usecols = ["match_id"] + [
        f"{outcome}_b{book}_{index}"
        for book in SELECTED_BOOKS
        for outcome in OUTCOMES
        for index in needed_indices
    ]
    parts: list[pd.DataFrame] = []
    for path in paths:
        for frame in pd.read_csv(
            path, usecols=usecols, chunksize=chunksize, low_memory=False
        ):
            match_ids = frame["match_id"].astype(str).to_numpy()
            cache = {
                index: raw_and_devig(frame, SELECTED_BOOKS, index)
                for index in needed_indices
            }
            for hours in SIGNAL_HOURS:
                for book_position, book in enumerate(SELECTED_BOOKS):
                    requested = wanted.get((hours, book), {})
                    if not requested:
                        continue
                    mask = np.fromiter(
                        (match_id in requested for match_id in match_ids),
                        dtype=bool,
                        count=len(match_ids),
                    )
                    if not mask.any():
                        continue
                    positions = np.flatnonzero(mask)
                    selected_indices = np.fromiter(
                        (requested[match_ids[position]] for position in positions),
                        dtype=np.int64,
                        count=len(positions),
                    )
                    part = pd.DataFrame(
                        {
                            "match_id": match_ids[positions],
                            "hours_before_kickoff": hours,
                            "book_slot": f"b{book}",
                            "selected_outcome_index": selected_indices,
                            "selected_outcome": np.asarray(OUTCOMES, dtype=object)[
                                selected_indices
                            ],
                        }
                    )
                    for delay in DELAYS:
                        index = CUTOFFS[hours] + 1 + delay
                        raw, _p, _over, complete = cache[index]
                        valid = complete[positions, book_position]
                        prices = np.full(len(positions), np.nan, dtype=float)
                        if valid.any():
                            prices[valid] = raw[
                                positions[valid],
                                book_position,
                                selected_indices[valid],
                            ]
                        part[f"execution_decimal_odds_delay_{delay}h"] = prices
                    parts.append(part)
    if not parts:
        raise RuntimeError("no execution-price records")
    output = pd.concat(parts, ignore_index=True)
    if output.duplicated(keys).any():
        duplicates = int(output.duplicated(keys, keep=False).sum())
        raise RuntimeError(f"duplicate execution-price rows: {duplicates}")
    expected = len(identity)
    if len(output) != expected:
        missing_rows = expected - len(output)
        raise RuntimeError(
            f"execution-price extraction lost identities: {expected} -> {len(output)} ({missing_rows})"
        )
    completeness = {
        f"delay_{delay}h": float(
            output[f"execution_decimal_odds_delay_{delay}h"].notna().mean()
        )
        for delay in DELAYS
    }
    return output, {
        "rows": int(len(output)),
        "matches": int(output["match_id"].nunique()),
        "completeness_by_delay": completeness,
        "rows_by_book": {
            str(key): int(value)
            for key, value in output["book_slot"].value_counts().sort_index().items()
        },
        "rows_by_cutoff": {
            str(int(key)): int(value)
            for key, value in output["hours_before_kickoff"]
            .value_counts()
            .sort_index()
            .items()
        },
    }


def attach_execution_and_outcomes(
    strategy: pd.DataFrame,
    test: pd.DataFrame,
    execution_prices: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> pd.DataFrame:
    with_observation = exp9.attach_prices_before_outcomes(strategy, test)
    keys = ["match_id", "hours_before_kickoff", "book_slot"]
    price_columns = keys + [
        "selected_outcome_index",
        "selected_outcome",
        *[f"execution_decimal_odds_delay_{delay}h" for delay in DELAYS],
    ]
    merged = with_observation.merge(
        execution_prices[price_columns],
        on=keys,
        how="left",
        validate="one_to_one",
        suffixes=("", "_execution"),
    )
    if len(merged) != len(with_observation):
        raise RuntimeError("execution-price join changed strategy row count")
    if merged[[f"execution_decimal_odds_delay_{delay}h" for delay in DELAYS]].isna().all(axis=1).any():
        raise RuntimeError("strategy row has no execution prices")
    if not (
        merged["selected_outcome"].astype(str)
        == merged["selected_outcome_execution"].astype(str)
    ).all():
        raise RuntimeError("execution-price selected outcome mismatch")
    available = merged["execution_decimal_odds_delay_0h"].notna()
    difference = np.abs(
        merged.loc[available, "observation_decimal_odds"].to_numpy(float)
        - merged.loc[available, "execution_decimal_odds_delay_0h"].to_numpy(float)
    )
    if difference.size and float(difference.max()) > 1e-10:
        raise ValueError(
            f"delay-zero execution price does not reproduce observation price: {difference.max()}"
        )
    merged.drop(
        columns=["selected_outcome_execution", "selected_outcome_index_execution"],
        inplace=True,
    )
    return exp9.settle_after_selection(merged, outcomes)


def bookmaker_incremental_stability(
    baseline: pd.DataFrame,
    overlay: pd.DataFrame,
) -> dict[str, Any]:
    keys = ["match_id", "hours_before_kickoff"]
    columns = keys + [
        "book_slot",
        "bookmaker_name",
        "net_return_after_friction",
    ]
    joined = baseline[columns].merge(
        overlay[columns],
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_overlay"),
    )
    joined["incremental"] = (
        joined["net_return_after_friction_overlay"]
        - joined["net_return_after_friction_baseline"]
    )
    by_overlay_book: dict[str, Any] = {}
    for book, group in joined.groupby("bookmaker_name_overlay", sort=True):
        by_overlay_book[str(book)] = {
            "opportunities": int(len(group)),
            "incremental_profit_units": float(group["incremental"].sum()),
            "incremental_return_per_opportunity": float(group["incremental"].mean()),
        }
    leave_one_book_out: dict[str, Any] = {}
    all_books = sorted(
        set(joined["bookmaker_name_baseline"].astype(str))
        | set(joined["bookmaker_name_overlay"].astype(str))
    )
    for book in all_books:
        keep = (
            joined["bookmaker_name_baseline"].astype(str) != book
        ) & (joined["bookmaker_name_overlay"].astype(str) != book)
        group = joined[keep]
        if group.empty:
            continue
        leave_one_book_out[book] = {
            "opportunities": int(len(group)),
            "incremental_return_per_opportunity": float(group["incremental"].mean()),
            "paired_match_bootstrap": event_cluster_bootstrap(
                group, group["incremental"].to_numpy(float)
            ),
        }
    positive = {
        book: values["incremental_profit_units"]
        for book, values in by_overlay_book.items()
        if values["incremental_profit_units"] > 0
    }
    positive_total = sum(positive.values())
    maximum_positive_share = (
        max(positive.values()) / positive_total if positive_total > 0 else None
    )
    return {
        "by_overlay_selected_book": by_overlay_book,
        "leave_one_book_out": leave_one_book_out,
        "maximum_positive_book_contribution_share": maximum_positive_share,
    }


def run_scenarios(
    baseline: pd.DataFrame,
    overlay: pd.DataFrame,
    scenarios: tuple[ExecutionScenario, ...],
    output_root: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    results: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    ledger_root = output_root / "scenario-ledgers"
    ledger_root.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        baseline_ledger = apply_execution_scenario(baseline, scenario)
        overlay_ledger = apply_execution_scenario(overlay, scenario)
        baseline_metrics = scenario_metrics(baseline_ledger)
        overlay_metrics = scenario_metrics(overlay_ledger)
        comparison = compare_scenario_ledgers(baseline_ledger, overlay_ledger)
        stability = bookmaker_incremental_stability(baseline_ledger, overlay_ledger)
        results[scenario.name] = {
            "scenario": scenario_to_dict(scenario),
            "baseline": baseline_metrics,
            "rank_only_overlay": overlay_metrics,
            "incremental_overlay_minus_baseline": comparison,
            "bookmaker_stability": stability,
        }
        rows.append(
            {
                **scenario_to_dict(scenario),
                "baseline_fills": baseline_metrics["fills"],
                "baseline_roi_per_fill": baseline_metrics["roi_per_fill"],
                "baseline_return_per_opportunity": baseline_metrics[
                    "return_per_opportunity"
                ],
                "overlay_fills": overlay_metrics["fills"],
                "overlay_roi_per_fill": overlay_metrics["roi_per_fill"],
                "overlay_return_per_opportunity": overlay_metrics[
                    "return_per_opportunity"
                ],
                "incremental_return_per_opportunity": comparison[
                    "incremental_return_per_opportunity"
                ],
                "incremental_ci95_low": comparison["paired_match_bootstrap"][
                    "ci95_low"
                ],
                "incremental_ci95_high": comparison["paired_match_bootstrap"][
                    "ci95_high"
                ],
                "maximum_positive_book_contribution_share": stability[
                    "maximum_positive_book_contribution_share"
                ],
            }
        )
        if scenario.name in {
            "delay_0h__slip_0bps__fill_100pct",
            "delay_1h__slip_25bps__fill_90pct",
            "delay_2h__slip_50bps__fill_75pct",
            "delay_3h__slip_100bps__fill_50pct",
        }:
            baseline_ledger.to_csv(
                ledger_root / f"{scenario.name}__baseline.csv.gz",
                index=False,
                compression="gzip",
            )
            overlay_ledger.to_csv(
                ledger_root / f"{scenario.name}__rank_only.csv.gz",
                index=False,
                compression="gzip",
            )
    summary = pd.DataFrame(rows).sort_values(
        ["latency_hours", "slippage_bps", "base_fill_rate"],
        ascending=[True, True, False],
        kind="mergesort",
    )
    return results, summary


def frozen_gate(summary: pd.DataFrame) -> dict[str, Any]:
    def row(name: str) -> pd.Series:
        selected = summary[summary["name"] == name]
        if len(selected) != 1:
            raise RuntimeError(f"missing frozen scenario: {name}")
        return selected.iloc[0]

    zero = row("delay_0h__slip_0bps__fill_100pct")
    practical = row("delay_1h__slip_25bps__fill_90pct")
    core = summary[
        summary["name"].isin(
            [
                "delay_0h__slip_0bps__fill_100pct",
                "delay_1h__slip_25bps__fill_90pct",
                "delay_2h__slip_50bps__fill_75pct",
                "delay_3h__slip_100bps__fill_50pct",
            ]
        )
    ]
    checks = {
        "zero_friction_overlay_roi_positive": bool(
            zero["overlay_roi_per_fill"] is not None
            and zero["overlay_roi_per_fill"] > 0
        ),
        "zero_friction_incremental_ci_above_zero": bool(
            zero["incremental_ci95_low"] > 0
        ),
        "practical_overlay_roi_positive": bool(
            practical["overlay_roi_per_fill"] is not None
            and practical["overlay_roi_per_fill"] > 0
        ),
        "practical_incremental_ci_above_zero": bool(
            practical["incremental_ci95_low"] > 0
        ),
        "positive_incremental_point_lift_all_four_core_scenarios": bool(
            (core["incremental_return_per_opportunity"] > 0).all()
        ),
        "practical_positive_contribution_not_over_40pct_one_book": bool(
            practical["maximum_positive_book_contribution_share"] is not None
            and practical["maximum_positive_book_contribution_share"] <= 0.40
        ),
    }
    return {
        "checks": checks,
        "promoted": all(checks.values()),
        "decision": (
            "historical execution envelope promoted"
            if all(checks.values())
            else "historical execution envelope not promoted"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stress-test the rank-only residual overlay under delayed and degraded execution."
    )
    parser.add_argument("--output-root", default="artifacts/experiment-015")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress_path = root / "progress.json"
    failure_path = root / "failure.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(
            json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("reconstructing_frozen_normal_and_residual_models")
        datasets = residual_gen.build_all_state_records(
            source_paths, chunksize=args.chunksize
        )
        diagnostics = datasets.pop("diagnostics")
        normal_hazard, normal_movement, training_counts = (
            residual_gen.train_frozen_models(
                datasets["train"],
                hazard_max=args.hazard_max_train,
                movement_max=args.movement_max_train,
            )
        )
        residual_frames: dict[str, pd.DataFrame] = {}
        x_frames: dict[str, pd.DataFrame] = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            residual_frames[split] = residual_gen.build_residual_frame(
                split, datasets[split], normal_hazard, normal_movement
            )
            x_frames[split], columns = exp8.x_frame(datasets[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif raw_x_columns != columns:
                raise RuntimeError("validation/test raw X schemas differ")
        assert raw_x_columns is not None

        progress("reconstructing_rank_only_closing_strategy")
        future, closing_profile = exp11.build_closing_prices(
            source_paths,
            [residual_frames["validation"], residual_frames["test"]],
            chunksize=args.chunksize,
        )
        validation, baseline_columns, augmented_columns = exp8.model_frame(
            residual_frames["validation"],
            x_frames["validation"],
            future,
            raw_x_columns,
        )
        test, baseline_test, augmented_test = exp8.model_frame(
            residual_frames["test"],
            x_frames["test"],
            future,
            raw_x_columns,
        )
        if baseline_columns != baseline_test or augmented_columns != augmented_test:
            raise RuntimeError("validation/test schemas differ")
        baseline_probability, baseline_delta = exp13.fit_models(
            validation, test, baseline_columns
        )
        action_probability, action_delta = exp13.fit_models(
            validation, test, augmented_columns
        )
        baseline_expected = baseline_probability[:, None] * baseline_delta
        action_expected = action_probability[:, None] * action_delta
        baseline_identity = exp13.choose_candidate_identity(
            test, baseline_expected, "baseline_identity"
        )
        baseline_strategy = exp13.strategy_from_identity(
            test,
            baseline_identity,
            baseline_expected,
            "raw_baseline",
        )
        rank_only_strategy = exp13.strategy_from_identity(
            test,
            baseline_identity,
            action_expected,
            "rank_only_overlay",
        )

        progress("extracting_delayed_execution_prices")
        execution_prices, execution_profile = build_execution_prices(
            source_paths, baseline_identity, chunksize=args.chunksize
        )
        outcomes, outcome_profile = exp9.load_outcomes(source_paths)
        baseline_settled = attach_execution_and_outcomes(
            baseline_strategy, test, execution_prices, outcomes
        )
        rank_only_settled = attach_execution_and_outcomes(
            rank_only_strategy, test, execution_prices, outcomes
        )
        baseline_settled.to_csv(
            root / "baseline_settled_with_execution_prices.csv.gz",
            index=False,
            compression="gzip",
        )
        rank_only_settled.to_csv(
            root / "rank_only_settled_with_execution_prices.csv.gz",
            index=False,
            compression="gzip",
        )

        progress("running_frozen_friction_grid")
        scenarios = default_scenarios()
        scenario_results, summary = run_scenarios(
            baseline_settled, rank_only_settled, scenarios, root
        )
        summary.to_csv(root / "scenario-summary.csv", index=False)
        gate = frozen_gate(summary)
        report = {
            "experiment": "015_rank_only_execution_friction_stress",
            "status": "completed",
            "evidentiary_status": (
                "diagnostic_historical_outcomes_previously_opened_not_prospective_profit_test"
            ),
            "archive": archive_meta,
            "training_counts": training_counts,
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "execution_price_profile": execution_profile,
            "outcome_profile": outcome_profile,
            "strategies": {
                "identity": "raw market fixes bookmaker and outcome; action residuals rerank opportunities only",
                "trade_fraction": exp11.TRADE_FRACTION,
                "opportunities": int(len(baseline_strategy)),
                "baseline_trades": int(baseline_strategy["traded"].sum()),
                "rank_only_trades": int(rank_only_strategy["traded"].sum()),
            },
            "scenario_grid": {
                "count": len(scenarios),
                "latency_hours": list(DELAYS),
                "slippage_bps": [0, 25, 50, 100],
                "base_fill_rates": [1.0, 0.9, 0.75, 0.5],
                "adverse_fill_sensitivity": 20.0,
                "fill_randomization": "deterministic SHA-256 by match/cutoff/book/outcome/scenario; outcome-blind",
            },
            "frozen_gate": gate,
            "scenarios": scenario_results,
            "evidence_boundary": {
                "historical_outcomes_previously_opened": True,
                "real_account_limits_observed": False,
                "actual_bet_rejections_observed": False,
                "prospective_profit_claim": False,
            },
        }
        (root / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "scenario_count": len(scenarios),
                    "gate": gate,
                },
                indent=2,
                sort_keys=True,
            )
        )
        failure_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "progress": json.loads(
                        progress_path.read_text(encoding="utf-8")
                    )
                    if progress_path.exists()
                    else None,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
