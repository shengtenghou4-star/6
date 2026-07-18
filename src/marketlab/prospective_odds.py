from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


PROVIDER = "the_odds_api_v4"
QUOTA_HEADERS = ("x-requests-remaining", "x-requests-used", "x-requests-last")
ISO_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


@dataclass(frozen=True, slots=True)
class SnapshotRequest:
    sport: str
    markets: tuple[str, ...] = ("h2h",)
    regions: tuple[str, ...] = ()
    bookmakers: tuple[str, ...] = ()
    commence_time_from: str | None = None
    commence_time_to: str | None = None

    def __post_init__(self) -> None:
        if not self.sport.strip():
            raise ValueError("sport must not be empty")
        if not self.markets or any(not item.strip() for item in self.markets):
            raise ValueError("at least one non-empty market is required")
        if bool(self.regions) == bool(self.bookmakers):
            raise ValueError("specify exactly one of regions or bookmakers")
        for value, label in (
            (self.commence_time_from, "commence_time_from"),
            (self.commence_time_to, "commence_time_to"),
        ):
            if value is not None and not is_valid_iso_utc(value):
                raise ValueError(f"{label} must be an ISO-8601 UTC timestamp ending in Z")

    def public_parameters(self) -> dict[str, str]:
        params = {
            "markets": ",".join(self.markets),
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        if self.regions:
            params["regions"] = ",".join(self.regions)
        if self.bookmakers:
            params["bookmakers"] = ",".join(self.bookmakers)
        if self.commence_time_from:
            params["commenceTimeFrom"] = self.commence_time_from
        if self.commence_time_to:
            params["commenceTimeTo"] = self.commence_time_to
        return params

    def secure_parameters(self, api_key: str) -> dict[str, str]:
        if not api_key:
            raise ValueError("API key must not be empty")
        return {**self.public_parameters(), "apiKey": api_key}


@dataclass(frozen=True, slots=True)
class NormalizationDiagnostics:
    events_seen: int
    bookmakers_seen: int
    markets_seen: int
    outcomes_seen: int
    normalized_rows: int
    malformed_events: int
    malformed_bookmakers: int
    malformed_markets: int
    malformed_outcomes: int
    invalid_commence_times: int
    invalid_bookmaker_update_times: int
    invalid_market_update_times: int
    invalid_decimal_prices: int


NORMALIZED_FIELDS = (
    "provider",
    "snapshot_ingested_at_utc",
    "event_id",
    "sport_key",
    "sport_title",
    "commence_time",
    "commence_time_valid",
    "home_team",
    "away_team",
    "bookmaker_key",
    "bookmaker_title",
    "bookmaker_last_update",
    "bookmaker_last_update_valid",
    "market_key",
    "market_last_update",
    "market_last_update_valid",
    "outcome_name",
    "outcome_description",
    "price_decimal",
    "price_valid_decimal",
    "point",
    "point_present",
    "outcome_link",
    "outcome_sid",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def is_valid_iso_utc(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_UTC_PATTERN.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _safe_scalar(value: Any) -> str | float | int | bool | None:
    if value is None or isinstance(value, (str, float, int, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_current_odds_payload(
    payload: Any,
    *,
    ingested_at_utc: str,
) -> tuple[list[dict[str, Any]], NormalizationDiagnostics]:
    if not is_valid_iso_utc(ingested_at_utc):
        raise ValueError("ingested_at_utc must be an ISO-8601 UTC timestamp ending in Z")
    if not isinstance(payload, list):
        raise ValueError("current odds response root must be a JSON list")

    rows: list[dict[str, Any]] = []
    events_seen = bookmakers_seen = markets_seen = outcomes_seen = 0
    malformed_events = malformed_bookmakers = malformed_markets = malformed_outcomes = 0
    invalid_commence_times = invalid_bookmaker_update_times = invalid_market_update_times = 0
    invalid_decimal_prices = 0

    for event in payload:
        events_seen += 1
        if not isinstance(event, dict):
            malformed_events += 1
            continue
        event_id = event.get("id")
        sport_key = event.get("sport_key")
        commence_time = event.get("commence_time")
        commence_valid = is_valid_iso_utc(commence_time)
        if not commence_valid:
            invalid_commence_times += 1
        bookmakers = event.get("bookmakers")
        if not isinstance(bookmakers, list):
            malformed_events += 1
            continue

        for bookmaker in bookmakers:
            bookmakers_seen += 1
            if not isinstance(bookmaker, dict):
                malformed_bookmakers += 1
                continue
            bookmaker_last_update = bookmaker.get("last_update")
            bookmaker_update_valid = bookmaker_last_update is None or is_valid_iso_utc(bookmaker_last_update)
            if not bookmaker_update_valid:
                invalid_bookmaker_update_times += 1
            markets = bookmaker.get("markets")
            if not isinstance(markets, list):
                malformed_bookmakers += 1
                continue

            for market in markets:
                markets_seen += 1
                if not isinstance(market, dict):
                    malformed_markets += 1
                    continue
                market_last_update = market.get("last_update")
                market_update_valid = market_last_update is None or is_valid_iso_utc(market_last_update)
                if not market_update_valid:
                    invalid_market_update_times += 1
                outcomes = market.get("outcomes")
                if not isinstance(outcomes, list):
                    malformed_markets += 1
                    continue

                for outcome in outcomes:
                    outcomes_seen += 1
                    if not isinstance(outcome, dict):
                        malformed_outcomes += 1
                        continue
                    raw_price = outcome.get("price")
                    price_valid = (
                        isinstance(raw_price, (int, float))
                        and not isinstance(raw_price, bool)
                        and float(raw_price) > 1.0
                    )
                    if not price_valid:
                        invalid_decimal_prices += 1
                    point = outcome.get("point")
                    rows.append(
                        {
                            "provider": PROVIDER,
                            "snapshot_ingested_at_utc": ingested_at_utc,
                            "event_id": _safe_scalar(event_id),
                            "sport_key": _safe_scalar(sport_key),
                            "sport_title": _safe_scalar(event.get("sport_title")),
                            "commence_time": _safe_scalar(commence_time),
                            "commence_time_valid": commence_valid,
                            "home_team": _safe_scalar(event.get("home_team")),
                            "away_team": _safe_scalar(event.get("away_team")),
                            "bookmaker_key": _safe_scalar(bookmaker.get("key")),
                            "bookmaker_title": _safe_scalar(bookmaker.get("title")),
                            "bookmaker_last_update": _safe_scalar(bookmaker_last_update),
                            "bookmaker_last_update_valid": bookmaker_update_valid,
                            "market_key": _safe_scalar(market.get("key")),
                            "market_last_update": _safe_scalar(market_last_update),
                            "market_last_update_valid": market_update_valid,
                            "outcome_name": _safe_scalar(outcome.get("name")),
                            "outcome_description": _safe_scalar(outcome.get("description")),
                            "price_decimal": _safe_scalar(raw_price),
                            "price_valid_decimal": price_valid,
                            "point": _safe_scalar(point),
                            "point_present": point is not None,
                            "outcome_link": _safe_scalar(outcome.get("link")),
                            "outcome_sid": _safe_scalar(outcome.get("sid")),
                        }
                    )

    diagnostics = NormalizationDiagnostics(
        events_seen=events_seen,
        bookmakers_seen=bookmakers_seen,
        markets_seen=markets_seen,
        outcomes_seen=outcomes_seen,
        normalized_rows=len(rows),
        malformed_events=malformed_events,
        malformed_bookmakers=malformed_bookmakers,
        malformed_markets=malformed_markets,
        malformed_outcomes=malformed_outcomes,
        invalid_commence_times=invalid_commence_times,
        invalid_bookmaker_update_times=invalid_bookmaker_update_times,
        invalid_market_update_times=invalid_market_update_times,
        invalid_decimal_prices=invalid_decimal_prices,
    )
    return rows, diagnostics


def snapshot_directory_name(*, ingested_at_utc: str, sport: str, raw_sha256: str) -> str:
    timestamp = ingested_at_utc.replace("-", "").replace(":", "").replace(".", "_").replace("Z", "Z")
    sport_slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", sport).strip("-") or "sport"
    return f"{timestamp}__{sport_slug}__{raw_sha256[:12]}"


def _quota_metadata(headers: Mapping[str, Any]) -> dict[str, str | None]:
    lowered = {str(key).casefold(): str(value) for key, value in headers.items()}
    return {header: lowered.get(header) for header in QUOTA_HEADERS}


def archive_current_odds_snapshot(
    *,
    output_root: Path,
    request: SnapshotRequest,
    raw_response_bytes: bytes,
    response_headers: Mapping[str, Any],
    ingested_at_utc: str,
    http_status: int,
    response_url_without_api_key: str,
) -> Path:
    if not raw_response_bytes:
        raise ValueError("raw response must not be empty")
    if not is_valid_iso_utc(ingested_at_utc):
        raise ValueError("invalid ingestion timestamp")
    if "apikey" in response_url_without_api_key.casefold():
        raise ValueError("response_url_without_api_key must not contain an API key parameter")

    raw_sha256 = hashlib.sha256(raw_response_bytes).hexdigest()
    directory = output_root / snapshot_directory_name(
        ingested_at_utc=ingested_at_utc,
        sport=request.sport,
        raw_sha256=raw_sha256,
    )
    if directory.exists():
        raise FileExistsError(f"immutable snapshot directory already exists: {directory}")
    directory.mkdir(parents=True, exist_ok=False)

    raw_path = directory / "raw-response.json"
    raw_path.write_bytes(raw_response_bytes)
    try:
        payload = json.loads(raw_response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        failure = {
            "provider": PROVIDER,
            "ingested_at_utc": ingested_at_utc,
            "http_status": http_status,
            "raw_response_bytes": len(raw_response_bytes),
            "raw_sha256": raw_sha256,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        (directory / "failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        raise

    rows, diagnostics = normalize_current_odds_payload(payload, ingested_at_utc=ingested_at_utc)
    normalized_path = directory / "normalized-outcomes.csv"
    with normalized_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(NORMALIZED_FIELDS), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)

    unique_events = len({str(row["event_id"]) for row in rows})
    unique_bookmakers = len({str(row["bookmaker_key"]) for row in rows})
    unique_markets = len({str(row["market_key"]) for row in rows})
    manifest = {
        "schema_version": 1,
        "provider": PROVIDER,
        "endpoint": f"/v4/sports/{request.sport}/odds",
        "response_url_without_api_key": response_url_without_api_key,
        "request": {
            "sport": request.sport,
            "parameters": request.public_parameters(),
        },
        "ingested_at_utc": ingested_at_utc,
        "http_status": int(http_status),
        "response_headers": {
            "content-type": next(
                (str(value) for key, value in response_headers.items() if str(key).casefold() == "content-type"),
                None,
            ),
            "quota": _quota_metadata(response_headers),
        },
        "raw": {
            "path": raw_path.name,
            "bytes": len(raw_response_bytes),
            "sha256": raw_sha256,
        },
        "normalized": {
            "path": normalized_path.name,
            "rows": len(rows),
            "unique_events": unique_events,
            "unique_bookmakers": unique_bookmakers,
            "unique_markets": unique_markets,
            "fields": list(NORMALIZED_FIELDS),
        },
        "diagnostics": asdict(diagnostics),
        "immutability": "directory creation is exclusive; reruns never overwrite an existing snapshot",
        "timing_note": "ingested_at_utc is collector time; bookmaker/market last_update fields are preserved separately when supplied by the provider",
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    if "apikey" in manifest_text.casefold():
        raise ValueError("manifest unexpectedly contains API key material")
    (directory / "manifest.json").write_text(manifest_text, encoding="utf-8")
    return directory


def parse_csv_tuple(value: str | Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    return tuple(item.strip() for item in items if item and item.strip())
