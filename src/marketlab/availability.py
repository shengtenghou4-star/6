from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AvailabilityClass(StrEnum):
    IDENTITY = "identity"
    PREMATCH_CONTEXT_UNKNOWN_TIME = "prematch_context_unknown_time"
    MARKET_FIRST_SET_UNKNOWN_TIME = "market_first_set_unknown_time"
    MARKET_CLOSING = "market_closing"
    POSTMATCH_OUTCOME = "postmatch_outcome"
    POSTMATCH_STATS = "postmatch_stats"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AvailabilityDecision:
    column: str
    availability: AvailabilityClass
    default_prematch_safe: bool
    reason: str


IDENTITY_COLUMNS = {
    "Div",
    "Date",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "_season",
    "_division",
    "_source_archive",
    "_source_file",
}

POSTMATCH_OUTCOME_COLUMNS = {
    "FTHG",
    "FTAG",
    "FTR",
    "HTHG",
    "HTAG",
    "HTR",
    "Res",
    "HG",
    "AG",
}

POSTMATCH_STATS_COLUMNS = {
    "HS",
    "AS",
    "HST",
    "AST",
    "HF",
    "AF",
    "HC",
    "AC",
    "HY",
    "AY",
    "HR",
    "AR",
}

# Known Football-Data bookmaker/aggregate prefixes. Matching is prefix-aware rather
# than arbitrary substring matching so ordinary future columns cannot accidentally
# become approved market fields just because they contain a short provider code.
MARKET_PREFIXES = (
    "B365",
    "P",
    "PS",
    "PIN",
    "WH",
    "BW",
    "IW",
    "VC",
    "LB",
    "GB",
    "SB",
    "SJ",
    "BS",
    "SO",
    "SY",
    "MAX",
    "AVG",
    "BBAV",
    "BBMX",
)

MARKET_SUFFIXES = {
    "H",
    "D",
    "A",
    "CH",
    "CD",
    "CA",
    "HH",
    "HA",
    "AH",
    "CAHH",
    "CAHA",
    ">2.5",
    "<2.5",
    "C>2.5",
    "C<2.5",
}

CLOSING_MARKET_SUFFIXES = {
    "CH",
    "CD",
    "CA",
    "CAHH",
    "CAHA",
    "C>2.5",
    "C<2.5",
}


def _market_parts(column: str) -> tuple[str, str] | None:
    upper = column.upper()
    # Longest prefix wins, avoiding P matching PIN/PS.
    for prefix in sorted(MARKET_PREFIXES, key=len, reverse=True):
        if not upper.startswith(prefix):
            continue
        suffix = upper[len(prefix) :]
        if suffix in MARKET_SUFFIXES:
            return prefix, suffix
    return None


def _looks_like_market_column(column: str) -> bool:
    return _market_parts(column) is not None


def _looks_like_closing_market_column(column: str) -> bool:
    parts = _market_parts(column)
    return parts is not None and parts[1] in CLOSING_MARKET_SUFFIXES


def classify_football_data_column(column: str) -> AvailabilityDecision:
    if column in IDENTITY_COLUMNS:
        return AvailabilityDecision(
            column=column,
            availability=AvailabilityClass.IDENTITY,
            default_prematch_safe=True,
            reason="source identity/provenance field; not a predictive signal by itself",
        )

    if column in POSTMATCH_OUTCOME_COLUMNS:
        return AvailabilityDecision(
            column=column,
            availability=AvailabilityClass.POSTMATCH_OUTCOME,
            default_prematch_safe=False,
            reason="match result or score is known only after/during the match",
        )

    if column in POSTMATCH_STATS_COLUMNS:
        return AvailabilityDecision(
            column=column,
            availability=AvailabilityClass.POSTMATCH_STATS,
            default_prematch_safe=False,
            reason="match statistics are realized during/after the match",
        )

    if column == "Referee":
        return AvailabilityDecision(
            column=column,
            availability=AvailabilityClass.PREMATCH_CONTEXT_UNKNOWN_TIME,
            default_prematch_safe=False,
            reason="referee may be announced pre-match, but this dataset does not prove first-known time",
        )

    if _looks_like_market_column(column):
        if _looks_like_closing_market_column(column):
            return AvailabilityDecision(
                column=column,
                availability=AvailabilityClass.MARKET_CLOSING,
                default_prematch_safe=False,
                reason="closing-market field cannot be used at an earlier prediction cutoff",
            )
        return AvailabilityDecision(
            column=column,
            availability=AvailabilityClass.MARKET_FIRST_SET_UNKNOWN_TIME,
            default_prematch_safe=False,
            reason="market field lacks an exact observation timestamp in the coarse source",
        )

    return AvailabilityDecision(
        column=column,
        availability=AvailabilityClass.UNKNOWN,
        default_prematch_safe=False,
        reason="availability timing is not proven; explicit experiment approval required",
    )


def assert_default_prematch_safe(columns: list[str] | tuple[str, ...] | set[str]) -> None:
    decisions = [classify_football_data_column(column) for column in columns]
    unsafe = [decision for decision in decisions if not decision.default_prematch_safe]
    if unsafe:
        summary = ", ".join(f"{item.column}:{item.availability}" for item in unsafe[:20])
        extra = "" if len(unsafe) <= 20 else f" (+{len(unsafe) - 20} more)"
        raise ValueError(f"unsafe/unknown pre-match columns require explicit protocol approval: {summary}{extra}")
