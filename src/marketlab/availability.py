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

POSTMATCH_STATS_PREFIXES = {
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


def _looks_like_market_column(column: str) -> bool:
    upper = column.upper()
    # Football-Data bookmaker/market fields vary substantially by era. This deliberately
    # errs on the side of classifying ambiguous odds/line fields as market data rather
    # than silently treating them as ordinary context.
    tokens = (
        "B365",
        "PIN",
        "PS",
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
        "AH",
        "OU",
        ">2.5",
        "<2.5",
    )
    return any(token in upper for token in tokens)


def _looks_like_closing_market_column(column: str) -> bool:
    upper = column.upper()
    # Recent Football-Data schemas commonly encode closing variants with a C immediately
    # before the H/D/A or line/price suffix (e.g. AvgCH, B365CA, PCA). We keep the rule
    # intentionally narrow; uncertain fields remain UNKNOWN or first-set market data.
    closing_suffixes = (
        "CH",
        "CD",
        "CA",
        "CAHH",
        "CAHA",
        "C>2.5",
        "C<2.5",
    )
    return any(upper.endswith(suffix) for suffix in closing_suffixes)


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

    if column in POSTMATCH_STATS_PREFIXES:
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
    unsafe = [classify_football_data_column(column) for column in columns if not classify_football_data_column(column).default_prematch_safe]
    if unsafe:
        summary = ", ".join(f"{item.column}:{item.availability}" for item in unsafe[:20])
        extra = "" if len(unsafe) <= 20 else f" (+{len(unsafe) - 20} more)"
        raise ValueError(f"unsafe/unknown pre-match columns require explicit protocol approval: {summary}{extra}")
