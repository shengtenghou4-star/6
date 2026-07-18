from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SELECTIONS = ("H", "D", "A")
BOUNDS = (-math.inf, -0.03, -0.015, -0.0075, 0.0, 0.0075, 0.015, 0.03, math.inf)
SHRINKAGE = 500.0
BOOTSTRAP_SEED = 20260718
BOOTSTRAP_REPS = 2000
REQUIRED = (
    "FTR",
    "AvgH", "AvgD", "AvgA",
    "AvgCH", "AvgCD", "AvgCA",
    "B365H", "B365D", "B365A",
    "B365CH", "B365CD", "B365CA",
)


def load_rows(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    included: list[dict[str, Any]] = []
    counters = Counter()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            counters["rows_seen"] += 1
            if row.get("FTR") not in SELECTIONS:
                counters["excluded_bad_result"] += 1
                continue
            missing = [key for key in REQUIRED if row.get(key) in (None, "")]
            if missing:
                counters["excluded_missing_required"] += 1
                continue
            try:
                odds = {key: float(row[key]) for key in REQUIRED if key != "FTR"}
            except (TypeError, ValueError):
                counters["excluded_non_numeric"] += 1
                continue
            if any(not math.isfinite(value) or value <= 1.0 for value in odds.values()):
                counters["excluded_invalid_odds"] += 1
                continue
            included.append(
                {
                    "division": row.get("_division", row.get("Div", "")),
                    "season": row.get("_season", ""),
                    "result": row["FTR"],
                    "odds": odds,
                }
            )
            counters["included"] += 1
    return included, dict(counters)


def devig(odds: dict[str, float], columns: tuple[str, str, str]) -> list[float]:
    inverse = [1.0 / odds[column] for column in columns]
    total = sum(inverse)
    return [value / total for value in inverse]


def outcome_vector(result: str) -> list[float]:
    return [1.0 if result == selection else 0.0 for selection in SELECTIONS]


def signal_vector(odds: dict[str, float]) -> list[float]:
    signals = []
    for selection in SELECTIONS:
        close_relative = math.log(odds[f"B365C{selection}"] / odds[f"AvgC{selection}"])
        first_relative = math.log(odds[f"B365{selection}"] / odds[f"Avg{selection}"])
        signals.append(close_relative - first_relative)
    return signals


def bin_index(value: float) -> int:
    for index in range(len(BOUNDS) - 1):
        if BOUNDS[index] <= value < BOUNDS[index + 1]:
            return index
    raise AssertionError("unreachable bin")


def learn_corrections(rows: Iterable[dict[str, Any]]) -> tuple[list[list[float]], list[list[dict[str, float]]]]:
    sums = [[0.0 for _ in range(len(BOUNDS) - 1)] for _ in SELECTIONS]
    counts = [[0 for _ in range(len(BOUNDS) - 1)] for _ in SELECTIONS]

    for row in rows:
        odds = row["odds"]
        base = devig(odds, ("AvgCH", "AvgCD", "AvgCA"))
        outcome = outcome_vector(row["result"])
        signals = signal_vector(odds)
        for selection_index in range(3):
            index = bin_index(signals[selection_index])
            sums[selection_index][index] += outcome[selection_index] - base[selection_index]
            counts[selection_index][index] += 1

    corrections: list[list[float]] = []
    diagnostics: list[list[dict[str, float]]] = []
    for selection_index in range(3):
        selection_corrections: list[float] = []
        selection_diagnostics: list[dict[str, float]] = []
        for index in range(len(BOUNDS) - 1):
            count = counts[selection_index][index]
            raw_mean = sums[selection_index][index] / count if count else 0.0
            weight = count / (count + SHRINKAGE) if count else 0.0
            correction = raw_mean * weight
            selection_corrections.append(correction)
            selection_diagnostics.append(
                {
                    "bin": index,
                    "lower": BOUNDS[index],
                    "upper": BOUNDS[index + 1],
                    "n": count,
                    "raw_mean_y_minus_p": raw_mean,
                    "shrinkage_weight": weight,
                    "correction": correction,
                }
            )
        corrections.append(selection_corrections)
        diagnostics.append(selection_diagnostics)
    return corrections, diagnostics


def predict(row: dict[str, Any], corrections: list[list[float]] | None) -> list[float]:
    odds = row["odds"]
    base = devig(odds, ("AvgCH", "AvgCD", "AvgCA"))
    if corrections is None:
        return base
    signals = signal_vector(odds)
    adjusted = [
        min(0.98, max(0.01, base[index] + corrections[index][bin_index(signals[index])]))
        for index in range(3)
    ]
    total = sum(adjusted)
    return [value / total for value in adjusted]


def per_row_losses(row: dict[str, Any], probabilities: list[float]) -> tuple[float, float]:
    outcome = outcome_vector(row["result"])
    brier = sum((probabilities[index] - outcome[index]) ** 2 for index in range(3))
    actual_index = SELECTIONS.index(row["result"])
    log_loss = -math.log(max(probabilities[actual_index], 1e-15))
    return brier, log_loss


def evaluate(rows: list[dict[str, Any]], corrections: list[list[float]]) -> dict[str, Any]:
    base_brier: list[float] = []
    corrected_brier: list[float] = []
    base_log: list[float] = []
    corrected_log: list[float] = []
    by_division: dict[str, dict[str, list[float]]] = {}

    for row in rows:
        base_probs = predict(row, None)
        corrected_probs = predict(row, corrections)
        bb, bl = per_row_losses(row, base_probs)
        cb, cl = per_row_losses(row, corrected_probs)
        base_brier.append(bb)
        corrected_brier.append(cb)
        base_log.append(bl)
        corrected_log.append(cl)
        bucket = by_division.setdefault(
            row["division"],
            {"base_brier": [], "corrected_brier": [], "base_log": [], "corrected_log": []},
        )
        bucket["base_brier"].append(bb)
        bucket["corrected_brier"].append(cb)
        bucket["base_log"].append(bl)
        bucket["corrected_log"].append(cl)

    aggregate = summarize_losses(base_brier, corrected_brier, base_log, corrected_log)
    aggregate["bootstrap_95pct"] = paired_bootstrap(base_brier, corrected_brier, base_log, corrected_log)

    divisions = {
        division: summarize_losses(
            values["base_brier"], values["corrected_brier"], values["base_log"], values["corrected_log"]
        )
        for division, values in sorted(by_division.items())
    }
    return {"aggregate": aggregate, "by_division": divisions}


def summarize_losses(
    base_brier: list[float], corrected_brier: list[float], base_log: list[float], corrected_log: list[float]
) -> dict[str, float]:
    n = len(base_brier)
    if n == 0:
        raise ValueError("cannot evaluate zero rows")
    mean = lambda values: sum(values) / len(values)
    base_b = mean(base_brier)
    corrected_b = mean(corrected_brier)
    base_l = mean(base_log)
    corrected_l = mean(corrected_log)
    return {
        "n": n,
        "base_brier": base_b,
        "corrected_brier": corrected_b,
        "delta_brier_corrected_minus_base": corrected_b - base_b,
        "base_log_loss": base_l,
        "corrected_log_loss": corrected_l,
        "delta_log_loss_corrected_minus_base": corrected_l - base_l,
    }


def paired_bootstrap(
    base_brier: list[float], corrected_brier: list[float], base_log: list[float], corrected_log: list[float]
) -> dict[str, list[float]]:
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(base_brier)
    brier_deltas = [corrected_brier[i] - base_brier[i] for i in range(n)]
    log_deltas = [corrected_log[i] - base_log[i] for i in range(n)]
    boot_brier: list[float] = []
    boot_log: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        indices = [rng.randrange(n) for _ in range(n)]
        boot_brier.append(sum(brier_deltas[i] for i in indices) / n)
        boot_log.append(sum(log_deltas[i] for i in indices) / n)
    boot_brier.sort()
    boot_log.sort()
    low = int(0.025 * BOOTSTRAP_REPS)
    high = int(0.975 * BOOTSTRAP_REPS) - 1
    return {
        "delta_brier": [boot_brier[low], boot_brier[high]],
        "delta_log_loss": [boot_log[low], boot_log[high]],
    }


def jsonify_bounds(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "-inf" if value < 0 else "+inf"
    if isinstance(value, list):
        return [jsonify_bounds(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonify_bounds(item) for key, item in value.items()}
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run preregistered Experiment 000.")
    parser.add_argument("--development", required=True, help="Development bronze CSV.gz")
    parser.add_argument("--holdout", required=True, help="External holdout bronze CSV.gz")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    development, development_counts = load_rows(args.development)
    holdout, holdout_counts = load_rows(args.holdout)
    if not development or not holdout:
        raise SystemExit("development and holdout must both contain eligible rows")

    corrections, diagnostics = learn_corrections(development)
    results = evaluate(holdout, corrections)
    aggregate = results["aggregate"]
    success = (
        aggregate["delta_brier_corrected_minus_base"] < 0
        and aggregate["delta_log_loss_corrected_minus_base"] < 0
    )

    report = jsonify_bounds(
        {
            "experiment": "000_bookmaker_relative_movement",
            "status": "completed",
            "preregistered_rules": {
                "signal_bins": list(BOUNDS),
                "shrinkage": SHRINKAGE,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "bootstrap_reps": BOOTSTRAP_REPS,
            },
            "development_counts": development_counts,
            "holdout_counts": holdout_counts,
            "development_divisions": sorted({row["division"] for row in development}),
            "development_seasons": sorted({row["season"] for row in development}),
            "holdout_divisions": sorted({row["division"] for row in holdout}),
            "holdout_seasons": sorted({row["season"] for row in holdout}),
            "correction_diagnostics": {
                SELECTIONS[index]: diagnostics[index] for index in range(3)
            },
            "results": results,
            "preregistered_success_rule_passed": success,
        }
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"aggregate": aggregate, "success_rule_passed": success}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
