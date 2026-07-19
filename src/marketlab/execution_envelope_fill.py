from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

MECHANISMS = (
    "common_random",
    "adverse_move_rejection",
    "edge_rejection",
    "book_clustered_outage",
)

REQUIRED_COLUMNS = {
    "match_id",
    "hours_before_kickoff",
    "book_slot",
    "bookmaker_name",
    "selected_outcome",
    "traded",
    "won",
    "observation_decimal_odds",
}


@dataclass(frozen=True, slots=True)
class EnvelopeSpec:
    name: str
    latency_hours: int
    fill_rate: float
    mechanism: str
    slippage_bps: float = 0.0
    seed: int = 20260719

    def __post_init__(self) -> None:
        if self.latency_hours < 0:
            raise ValueError("latency_hours must be nonnegative")
        if not 0.0 <= self.fill_rate <= 1.0:
            raise ValueError("fill_rate must be in [0, 1]")
        if self.mechanism not in MECHANISMS:
            raise ValueError(f"unknown mechanism: {self.mechanism}")
        if self.slippage_bps < 0.0:
            raise ValueError("slippage_bps must be nonnegative")


def spec_to_dict(spec: EnvelopeSpec) -> dict[str, Any]:
    return asdict(spec)


def deterministic_uniform(keys: Iterable[str], *, seed: int) -> np.ndarray:
    values: list[float] = []
    for key in keys:
        digest = hashlib.sha256(f"{seed}|{key}".encode("utf-8")).digest()
        integer = int.from_bytes(digest[:8], "big", signed=False)
        values.append((integer + 0.5) / 2**64)
    return np.asarray(values, dtype=float)


def _row_identity(frame: pd.DataFrame, group: str) -> pd.Series:
    return (
        frame["match_id"].astype(str)
        + "|"
        + frame["hours_before_kickoff"].astype(str)
        + "|"
        + group
    )


def _target_count(mask: np.ndarray, fill_rate: float) -> int:
    return int(math.floor(int(mask.sum()) * fill_rate + 1e-12))


def _rank_fill(
    eligible: np.ndarray,
    target: int,
    primary: np.ndarray,
    tie_break: np.ndarray,
) -> np.ndarray:
    filled = np.zeros(len(eligible), dtype=bool)
    if target <= 0:
        return filled
    positions = np.flatnonzero(eligible)
    order = np.lexsort((tie_break[positions], primary[positions]))
    filled[positions[order[:target]]] = True
    return filled


def _book_cluster_fill(
    frame: pd.DataFrame,
    eligible: np.ndarray,
    target: int,
    row_uniform: np.ndarray,
    *,
    seed: int,
    group: str,
) -> np.ndarray:
    filled = np.zeros(len(frame), dtype=bool)
    if target <= 0:
        return filled
    positions = np.flatnonzero(eligible)
    books = frame.iloc[positions]["book_slot"].astype(str).to_numpy()
    unique_books = sorted(set(books))
    book_uniform = deterministic_uniform(
        [f"{group}|book|{book}" for book in unique_books], seed=seed
    )
    ordered_books = [
        book for _, book in sorted(zip(book_uniform, unique_books, strict=True))
    ]
    remaining = target
    for book in ordered_books:
        book_positions = positions[books == book]
        if len(book_positions) <= remaining:
            filled[book_positions] = True
            remaining -= len(book_positions)
        else:
            order = np.argsort(row_uniform[book_positions], kind="mergesort")
            filled[book_positions[order[:remaining]]] = True
            remaining = 0
        if remaining == 0:
            break
    if int(filled.sum()) != target:
        raise RuntimeError("book-cluster fill did not hit the exact target")
    return filled


def apply_envelope(
    settled: pd.DataFrame,
    spec: EnvelopeSpec,
    *,
    score_column: str,
) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(settled.columns))
    if missing:
        raise ValueError(f"settled strategy missing columns: {missing}")
    if score_column not in settled.columns:
        raise ValueError(f"settled strategy missing score column: {score_column}")
    execution_column = f"execution_decimal_odds_delay_{spec.latency_hours}h"
    if execution_column not in settled.columns:
        raise ValueError(f"settled strategy missing execution column: {execution_column}")

    frame = settled.copy()
    observation = pd.to_numeric(
        frame["observation_decimal_odds"], errors="coerce"
    ).to_numpy(float)
    execution = pd.to_numeric(frame[execution_column], errors="coerce").to_numpy(float)
    score = pd.to_numeric(frame[score_column], errors="coerce").to_numpy(float)
    if not np.isfinite(observation).all() or np.any(observation <= 1.0):
        raise ValueError("invalid observation odds")
    if not np.isfinite(score).all():
        raise ValueError("non-finite frozen score")

    valid_execution = np.isfinite(execution) & (execution > 1.0)
    attempted = frame["traded"].astype(bool).to_numpy()
    eligible = attempted & valid_execution
    target = _target_count(eligible, spec.fill_rate)
    adverse_log_move = np.zeros(len(frame), dtype=float)
    adverse_log_move[valid_execution] = np.maximum(
        0.0, np.log(observation[valid_execution] / execution[valid_execution])
    )
    group = f"delay_{spec.latency_hours}h|mechanism_{spec.mechanism}"
    row_uniform = deterministic_uniform(
        _row_identity(frame, group).tolist(), seed=spec.seed
    )

    if spec.mechanism == "common_random":
        filled = _rank_fill(eligible, target, row_uniform, row_uniform)
    elif spec.mechanism == "adverse_move_rejection":
        filled = _rank_fill(eligible, target, adverse_log_move, row_uniform)
    elif spec.mechanism == "edge_rejection":
        filled = _rank_fill(eligible, target, score, row_uniform)
    else:
        filled = _book_cluster_fill(
            frame,
            eligible,
            target,
            row_uniform,
            seed=spec.seed,
            group=group,
        )

    haircut = math.exp(-spec.slippage_bps / 10_000.0)
    executed_odds = np.where(
        valid_execution, np.maximum(1.000001, execution * haircut), np.nan
    )
    won = frame["won"].astype(bool).to_numpy()
    net_return = np.where(
        filled, np.where(won, executed_odds - 1.0, -1.0), 0.0
    )

    frame["envelope_name"] = spec.name
    frame["latency_hours"] = spec.latency_hours
    frame["fill_rate_target"] = spec.fill_rate
    frame["fill_mechanism"] = spec.mechanism
    frame["slippage_bps"] = spec.slippage_bps
    frame["execution_price_available"] = valid_execution
    frame["adverse_log_move"] = adverse_log_move
    frame["fill_uniform"] = row_uniform
    frame["attempted"] = attempted
    frame["eligible_for_fill"] = eligible
    frame["filled"] = filled
    frame["executed_decimal_odds"] = executed_odds
    frame["net_return_after_friction"] = net_return
    return frame
