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
    "Div", "Date", "Time", "HomeTeam", "AwayTeam",
    "_season", "_division", "_source_archive", "_source_file",
}

POSTMATCH_OUTCOME_COLUMNS = {
    "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR", "Res", "HG", "AG",
}

# Football-Data has used multiple historical abbreviations for realized match statistics.
# These are all blocked for pre-match use regardless of era.
POSTMATCH_STATS_COLUMNS = {
    "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR",
    "HO", "AO", "HHW", "AHW", "HFKC", "AFKC", "HBP", "ABP", "Attendance",
}

MARKET_PREFIXES = (
    "B365", "1XB", "BMGM", "BFE", "BFD", "BF", "PIN", "PS", "P",
    "WH", "BW", "IW", "VC", "BV", "CL", "LB", "GB", "SB", "SJ", "BS",
    "SO", "SY", "MAX", "AVG", "BBAV", "BBMX",
)

MARKET_SUFFIXES = {
    "H", "D", "A", "CH", "CD", "CA",
    "HH", "HA", "AH", "AHH", "AHA", "CAHH", "CAHA",
    ">2.5", "<2.5", "C>2.5", "C<2.5",
}

CLOSING_MARKET_SUFFIXES = {
    "CH", "CD", "CA", "CAHH", "CAHA", "C>2.5", "C<2.5",
}

# Source-wide market metadata/line fields that do not follow bookmaker-prefix + price-suffix form.
SPECIAL_MARKET_FIRST_SET_COLUMNS = {
    "AHh",   # Asian handicap line / home handicap
    "Bb1X2", "BbAH", "BbAHh", "BbOU",  # legacy Betbrain market summary fields
}
SPECIAL_MARKET_CLOSING_COLUMNS = {"AHCh"}


def _market_parts(column: str) -> tuple[str, str] | None:
    upper = column.upper()
    for prefix in sorted(MARKET_PREFIXES, key=len, reverse=True):
        if not upper.startswith(prefix):
            continue
        suffix = upper[len(prefix):]
        if suffix in MARKET_SUFFIXES:
            return prefix, suffix
    return None


def _looks_like_market_column(column: str) -> bool:
    return column in SPECIAL_MARKET_FIRST_SET_COLUMNS or column in SPECIAL_MARKET_CLOSING_COLUMNS or _market_parts(column) is not None


def _looks_like_closing_market_column(column: str) -> bool:
    if column in SPECIAL_MARKET_CLOSING_COLUMNS:
        return True
    parts = _market_parts(column)
    return parts is not None and parts[1] in CLOSING_MARKET_SUFFIXES


def classify_football_data_column(column: str) -> AvailabilityDecision:
    if column in IDENTITY_COLUMNS:
        return AvailabilityDecision(column, AvailabilityClass.IDENTITY, True, "source identity/provenance field; not a predictive signal by itself")

    if column in POSTMATCH_OUTCOME_COLUMNS:
        return AvailabilityDecision(column, AvailabilityClass.POSTMATCH_OUTCOME, False, "match result or score is known only after/during the match")

    if column in POSTMATCH_STATS_COLUMNS:
        return AvailabilityDecision(column, AvailabilityClass.POSTMATCH_STATS, False, "match statistics are realized during/after the match")

    if column == "Referee":
        return AvailabilityDecision(column, AvailabilityClass.PREMATCH_CONTEXT_UNKNOWN_TIME, False, "referee may be announced pre-match, but this dataset does not prove first-known time")

    if _looks_like_market_column(column):
        if _looks_like_closing_market_column(column):
            return AvailabilityDecision(column, AvailabilityClass.MARKET_CLOSING, False, "closing-market field cannot be used at an earlier prediction cutoff")
        return AvailabilityDecision(column, AvailabilityClass.MARKET_FIRST_SET_UNKNOWN_TIME, False, "market field lacks an exact observation timestamp in the coarse source")

    return AvailabilityDecision(column, AvailabilityClass.UNKNOWN, False, "availability timing is not proven; explicit experiment approval required")


def assert_default_prematch_safe(columns: list[str] | tuple[str, ...] | set[str]) -> None:
    decisions = [classify_football_data_column(column) for column in columns]
    unsafe = [decision for decision in decisions if not decision.default_prematch_safe]
    if unsafe:
        summary = ", ".join(f"{item.column}:{item.availability}" for item in unsafe[:20])
        extra = "" if len(unsafe) <= 20 else f" (+{len(unsafe) - 20} more)"
        raise ValueError(f"unsafe/unknown pre-match columns require explicit protocol approval: {summary}{extra}")
