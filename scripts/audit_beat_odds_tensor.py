from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


DATASET_SLUG = "austro/beat-the-bookie-worldwide-football-dataset"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
SERIES_FILES = ("odds_series.csv.gz", "odds_series_b.csv.gz")
OUTCOMES = ("home", "draw", "away")
BOOKMAKERS = tuple(range(1, 33))
TIME_INDEX = tuple(range(72))
EXPECTED_ODDS_COLUMNS = [
    f"{outcome}_b{book}_{time_index}"
    for book in BOOKMAKERS
    for outcome in OUTCOMES
    for time_index in TIME_INDEX
]


def download(url: str, path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256()
    total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
                fh.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "final_url": str(response.url)}


def extract_series(archive: Path, destination: Path) -> dict[str, str]:
    destination.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, str] = {}
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        for filename in SERIES_FILES:
            if filename not in names:
                raise ValueError(f"archive missing required time-series file: {filename}")
            target = destination / filename
            with zf.open(filename) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted[filename] = str(target)
    return extracted


def inspect_header(path: Path) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8-sig", errors="strict") as fh:
        header = fh.readline().rstrip("\n\r").split(",")
    return header


def matrix_to_nested(matrix: np.ndarray) -> dict[str, Any]:
    # shape: bookmaker × outcome × time
    return {
        f"b{book}": {
            outcome: [int(value) for value in matrix[book - 1, outcome_index, :].tolist()]
            for outcome_index, outcome in enumerate(OUTCOMES)
        }
        for book in BOOKMAKERS
    }


def vector_summary(values: np.ndarray) -> dict[str, Any]:
    return {
        "values": [float(value) for value in values.tolist()],
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
        "first": float(values[0]),
        "last": float(values[-1]),
        "pearson_index_correlation": float(np.corrcoef(np.arange(len(values), dtype=float), values)[0, 1])
        if np.nanstd(values) > 0
        else None,
    }


def audit_file(path: Path, *, chunksize: int) -> dict[str, Any]:
    header = inspect_header(path)
    expected_prefix = ["match_id", "match_date", "match_time", "score_home", "score_away"]
    if header[:5] != expected_prefix:
        raise ValueError(f"unexpected identity prefix in {path.name}: {header[:5]}")
    odds_columns = header[5:]
    if odds_columns != EXPECTED_ODDS_COLUMNS:
        raise ValueError(f"odds tensor column order/schema differs from expected 32×3×72 layout in {path.name}")

    nonmissing = np.zeros((32, 3, 72), dtype=np.int64)
    adjacent_pairs = np.zeros((32, 3, 71), dtype=np.int64)
    adjacent_changes = np.zeros((32, 3, 71), dtype=np.int64)
    absolute_change_sum = np.zeros((32, 3, 71), dtype=np.float64)
    complete_market = np.zeros((32, 72), dtype=np.int64)
    total_rows = 0
    invalid_le_one = 0
    finite_values = 0
    min_value = math.inf
    max_value = -math.inf

    usecols = EXPECTED_ODDS_COLUMNS
    for chunk in pd.read_csv(
        path,
        usecols=usecols,
        chunksize=chunksize,
        dtype=np.float32,
        na_values=["nan", "NaN", "NULL", "null", ""],
        keep_default_na=True,
        low_memory=False,
    ):
        # pandas preserves requested file order when usecols is list-like only by column index in
        # current versions, so explicitly reindex to the frozen schema before reshaping.
        chunk = chunk.reindex(columns=EXPECTED_ODDS_COLUMNS)
        flat = chunk.to_numpy(dtype=np.float32, copy=False)
        rows = flat.shape[0]
        total_rows += rows
        tensor = flat.reshape(rows, 32, 3, 72)
        finite = np.isfinite(tensor)
        nonmissing += finite.sum(axis=0, dtype=np.int64)
        complete_market += finite.all(axis=2).sum(axis=0, dtype=np.int64)

        if finite.any():
            values = tensor[finite]
            finite_values += int(values.size)
            invalid_le_one += int(np.count_nonzero(values <= 1.0))
            min_value = min(min_value, float(np.min(values)))
            max_value = max(max_value, float(np.max(values)))

        left = tensor[:, :, :, :-1]
        right = tensor[:, :, :, 1:]
        pair_mask = np.isfinite(left) & np.isfinite(right)
        adjacent_pairs += pair_mask.sum(axis=0, dtype=np.int64)
        diff = right - left
        change_mask = pair_mask & (np.abs(diff) > 1e-7)
        adjacent_changes += change_mask.sum(axis=0, dtype=np.int64)
        absolute_change_sum += np.where(change_mask, np.abs(diff), 0.0).sum(axis=0, dtype=np.float64)

    if total_rows == 0:
        raise ValueError(f"no rows found in {path.name}")

    active_books_per_index = complete_market.sum(axis=0).astype(np.float64) / float(total_rows)
    nonmissing_per_index = nonmissing.sum(axis=(0, 1)).astype(np.float64)
    possible_quotes_per_index = float(total_rows * 32 * 3)
    quote_coverage_per_index = nonmissing_per_index / possible_quotes_per_index
    changed_pairs_per_index = adjacent_changes.sum(axis=(0, 1)).astype(np.float64)
    valid_pairs_per_index = adjacent_pairs.sum(axis=(0, 1)).astype(np.float64)
    change_rate_per_adjacent_index = np.divide(
        changed_pairs_per_index,
        valid_pairs_per_index,
        out=np.zeros_like(changed_pairs_per_index),
        where=valid_pairs_per_index > 0,
    )

    bookmaker_complete_counts = complete_market.sum(axis=1)
    bookmaker_complete_fraction = bookmaker_complete_counts / float(total_rows * 72)
    best_books = sorted(
        (
            {"bookmaker_slot": f"b{book}", "complete_market_fraction": float(bookmaker_complete_fraction[book - 1])}
            for book in BOOKMAKERS
        ),
        key=lambda item: (-item["complete_market_fraction"], item["bookmaker_slot"]),
    )

    return {
        "file": path.name,
        "rows": total_rows,
        "schema": {"bookmaker_slots": 32, "outcomes": 3, "time_indices": 72, "odds_columns": len(EXPECTED_ODDS_COLUMNS)},
        "finite_quote_values": finite_values,
        "invalid_values_le_one": invalid_le_one,
        "finite_value_min": None if min_value is math.inf else min_value,
        "finite_value_max": None if max_value is -math.inf else max_value,
        "quote_coverage_by_time_index": vector_summary(quote_coverage_per_index),
        "mean_complete_bookmakers_per_match_by_time_index": vector_summary(active_books_per_index),
        "adjacent_change_rate_by_transition": vector_summary(change_rate_per_adjacent_index),
        "best_bookmaker_slots_by_complete_market_fraction": best_books,
        "nonmissing_counts": matrix_to_nested(nonmissing),
        "adjacent_pair_counts": {
            f"b{book}": {
                outcome: [int(value) for value in adjacent_pairs[book - 1, outcome_index, :].tolist()]
                for outcome_index, outcome in enumerate(OUTCOMES)
            }
            for book in BOOKMAKERS
        },
        "adjacent_change_counts": {
            f"b{book}": {
                outcome: [int(value) for value in adjacent_changes[book - 1, outcome_index, :].tolist()]
                for outcome_index, outcome in enumerate(OUTCOMES)
            }
            for book in BOOKMAKERS
        },
        "absolute_change_sum": {
            f"b{book}": {
                outcome: [float(value) for value in absolute_change_sum[book - 1, outcome_index, :].tolist()]
                for outcome_index, outcome in enumerate(OUTCOMES)
            }
            for book in BOOKMAKERS
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the Beat The Bookie 32×3×72 historical odds tensor.")
    parser.add_argument("--output-root", default="artifacts/beat-odds-tensor-audit")
    parser.add_argument("--chunksize", type=int, default=128)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"

    archive_meta = download(DOWNLOAD_URL, archive)
    extracted_files = extract_series(archive, extracted)
    audits = [audit_file(Path(extracted_files[name]), chunksize=args.chunksize) for name in SERIES_FILES]

    combined_rows = sum(int(item["rows"]) for item in audits)
    if combined_rows != 92_647:
        raise SystemExit(f"row reconciliation failed: {combined_rows} != 92647")

    combined_coverage = np.average(
        np.array([item["quote_coverage_by_time_index"]["values"] for item in audits], dtype=float),
        axis=0,
        weights=np.array([item["rows"] for item in audits], dtype=float),
    )
    orientation_signal = float(np.corrcoef(np.arange(72, dtype=float), combined_coverage)[0, 1]) if np.std(combined_coverage) > 0 else None

    report = {
        "dataset_slug": DATASET_SLUG,
        "archive": archive_meta,
        "combined_rows": combined_rows,
        "files": audits,
        "time_axis_evidence": {
            "source_data_card_statement": "hourly sampled odds time series from up to 32 bookmakers from 72 hours before the start of each game",
            "column_indices": [0, 71],
            "combined_quote_coverage_by_index": [float(value) for value in combined_coverage.tolist()],
            "coverage_vs_index_correlation": orientation_signal,
            "decision_rule": "Do not assign exact hours-to-kickoff to index 0/71 from column names alone. Strong monotonic availability can support an orientation hypothesis, but source-code/paper semantics must be frozen before chronological modeling.",
        },
        "normalized_schema": {
            "primary_key": ["match_id", "bookmaker_slot", "outcome", "time_index"],
            "fields": ["match_id", "match_date", "match_time", "bookmaker_slot", "outcome", "time_index", "decimal_odds"],
            "note": "bookmaker_slot is anonymized b1-b32; normalized representation must remain reversible to the wide source tensor",
        },
    }
    (root / "audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "combined_rows": combined_rows,
                "coverage_vs_index_correlation": orientation_signal,
                "file_rows": {item["file"]: item["rows"] for item in audits},
                "top_books_file_a": audits[0]["best_bookmaker_slots_by_complete_market_fraction"][:10],
                "top_books_file_b": audits[1]["best_bookmaker_slots_by_complete_market_fraction"][:10],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
