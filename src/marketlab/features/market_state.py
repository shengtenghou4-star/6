from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class SelectionQuote:
    bookmaker_id: str
    selection_id: str
    decimal_price: float
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.bookmaker_id:
            raise ValueError("bookmaker_id is required")
        if not self.selection_id:
            raise ValueError("selection_id is required")
        if self.decimal_price <= 1.0:
            raise ValueError("decimal_price must be > 1.0")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(timezone.utc))


@dataclass(frozen=True, slots=True)
class BookmakerMarketState:
    bookmaker_id: str
    observed_at: datetime
    probabilities: dict[str, float]
    overround: float


@dataclass(frozen=True, slots=True)
class ConsensusState:
    observed_at: datetime
    probabilities: dict[str, float]
    contributing_bookmakers: dict[str, int]


@dataclass(frozen=True, slots=True)
class MovementPrimitive:
    bookmaker_id: str
    selection_id: str
    previous_at: datetime
    current_at: datetime
    elapsed_seconds: float
    probability_delta: float
    consensus_delta: float | None
    deviation_previous: float | None
    deviation_current: float | None
    deviation_delta: float | None


def _ensure_same_timestamp(quotes: Sequence[SelectionQuote]) -> datetime:
    if not quotes:
        raise ValueError("at least one quote is required")
    observed = quotes[0].observed_at
    if any(quote.observed_at != observed for quote in quotes):
        raise ValueError("market snapshot quotes must share the same observed_at timestamp")
    return observed


def proportional_devig(quotes: Sequence[SelectionQuote], *, expected_selections: set[str] | None = None) -> BookmakerMarketState:
    """Convert one bookmaker's complete mutually-exclusive market into normalized probabilities.

    This is deliberately a simple proportional de-vig transform. It is a reusable baseline,
    not a claim that proportional de-vigging is the final or best probability model.
    """

    observed_at = _ensure_same_timestamp(quotes)
    bookmaker_ids = {quote.bookmaker_id for quote in quotes}
    if len(bookmaker_ids) != 1:
        raise ValueError("proportional_devig requires quotes from exactly one bookmaker")

    selection_ids = [quote.selection_id for quote in quotes]
    if len(selection_ids) != len(set(selection_ids)):
        raise ValueError("duplicate selection_id within bookmaker snapshot")
    if expected_selections is not None and set(selection_ids) != expected_selections:
        missing = sorted(expected_selections - set(selection_ids))
        extra = sorted(set(selection_ids) - expected_selections)
        raise ValueError(f"incomplete/invalid market selections; missing={missing}, extra={extra}")

    raw = {quote.selection_id: 1.0 / quote.decimal_price for quote in quotes}
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("invalid implied-probability total")
    probabilities = {selection: value / total for selection, value in raw.items()}
    return BookmakerMarketState(
        bookmaker_id=next(iter(bookmaker_ids)),
        observed_at=observed_at,
        probabilities=probabilities,
        overround=total - 1.0,
    )


def consensus_median(states: Sequence[BookmakerMarketState], *, expected_selections: set[str] | None = None) -> ConsensusState:
    """Build a robust cross-book consensus using the median de-vigged probability per selection."""

    if not states:
        raise ValueError("at least one bookmaker state is required")
    observed_at = states[0].observed_at
    if any(state.observed_at != observed_at for state in states):
        raise ValueError("consensus states must share the same observed_at timestamp")
    bookmaker_ids = [state.bookmaker_id for state in states]
    if len(bookmaker_ids) != len(set(bookmaker_ids)):
        raise ValueError("duplicate bookmaker state in consensus snapshot")

    selections = expected_selections or set().union(*(state.probabilities for state in states))
    if not selections:
        raise ValueError("no selections available for consensus")

    values: dict[str, list[float]] = {selection: [] for selection in selections}
    for state in states:
        if expected_selections is not None and set(state.probabilities) != expected_selections:
            raise ValueError(f"bookmaker {state.bookmaker_id} has incomplete selections for consensus")
        for selection in selections:
            value = state.probabilities.get(selection)
            if value is not None:
                values[selection].append(value)

    if any(not bucket for bucket in values.values()):
        missing = sorted(selection for selection, bucket in values.items() if not bucket)
        raise ValueError(f"consensus has no observations for selections: {missing}")

    raw_medians = {selection: median(bucket) for selection, bucket in values.items()}
    total = sum(raw_medians.values())
    if total <= 0:
        raise ValueError("invalid consensus probability total")
    normalized = {selection: value / total for selection, value in raw_medians.items()}
    return ConsensusState(
        observed_at=observed_at,
        probabilities=normalized,
        contributing_bookmakers={selection: len(values[selection]) for selection in selections},
    )


def deviation_from_consensus(
    state: BookmakerMarketState,
    consensus: ConsensusState,
) -> dict[str, float]:
    if state.observed_at != consensus.observed_at:
        raise ValueError("bookmaker state and consensus must share observed_at")
    missing = set(state.probabilities) - set(consensus.probabilities)
    if missing:
        raise ValueError(f"consensus missing selections: {sorted(missing)}")
    return {
        selection: probability - consensus.probabilities[selection]
        for selection, probability in state.probabilities.items()
    }


def movement_primitives(
    previous: BookmakerMarketState,
    current: BookmakerMarketState,
    *,
    previous_consensus: ConsensusState | None = None,
    current_consensus: ConsensusState | None = None,
) -> list[MovementPrimitive]:
    """Describe only observed movement between two time-ordered states.

    The function does not infer bookmaker intent. It exposes raw movement and relative-market
    movement that later models may accept, reject, transform or replace.
    """

    if previous.bookmaker_id != current.bookmaker_id:
        raise ValueError("movement requires the same bookmaker")
    if current.observed_at <= previous.observed_at:
        raise ValueError("current state must be strictly later than previous state")
    if set(previous.probabilities) != set(current.probabilities):
        raise ValueError("selection set changed between bookmaker states")

    for consensus, label, timestamp in (
        (previous_consensus, "previous_consensus", previous.observed_at),
        (current_consensus, "current_consensus", current.observed_at),
    ):
        if consensus is not None and consensus.observed_at != timestamp:
            raise ValueError(f"{label} timestamp does not match bookmaker state")

    elapsed = (current.observed_at - previous.observed_at).total_seconds()
    previous_deviation = deviation_from_consensus(previous, previous_consensus) if previous_consensus else None
    current_deviation = deviation_from_consensus(current, current_consensus) if current_consensus else None

    output: list[MovementPrimitive] = []
    for selection in sorted(current.probabilities):
        consensus_delta = None
        if previous_consensus is not None and current_consensus is not None:
            consensus_delta = current_consensus.probabilities[selection] - previous_consensus.probabilities[selection]

        dev_prev = previous_deviation[selection] if previous_deviation is not None else None
        dev_current = current_deviation[selection] if current_deviation is not None else None
        dev_delta = dev_current - dev_prev if dev_prev is not None and dev_current is not None else None
        output.append(
            MovementPrimitive(
                bookmaker_id=current.bookmaker_id,
                selection_id=selection,
                previous_at=previous.observed_at,
                current_at=current.observed_at,
                elapsed_seconds=elapsed,
                probability_delta=current.probabilities[selection] - previous.probabilities[selection],
                consensus_delta=consensus_delta,
                deviation_previous=dev_prev,
                deviation_current=dev_current,
                deviation_delta=dev_delta,
            )
        )
    return output


def latest_quotes_at_or_before(
    quotes: Iterable[SelectionQuote],
    cutoff: datetime,
) -> dict[tuple[str, str], SelectionQuote]:
    """Select the latest quote per (bookmaker, selection) without admitting future observations."""

    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")
    cutoff_utc = cutoff.astimezone(timezone.utc)
    latest: dict[tuple[str, str], SelectionQuote] = {}
    for quote in quotes:
        if quote.observed_at > cutoff_utc:
            continue
        key = (quote.bookmaker_id, quote.selection_id)
        existing = latest.get(key)
        if existing is None or quote.observed_at > existing.observed_at:
            latest[key] = quote
    return latest
