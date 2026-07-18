from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


DRAW_LABELS = {"draw", "tie", "x"}
QUOTE_KEYS = ["event_id", "bookmaker_key", "market_key"]
SNAPSHOT_QUOTE_KEYS = ["snapshot_id", *QUOTE_KEYS]


@dataclass(frozen=True, slots=True)
class SequenceDiagnostics:
    snapshots: int
    normalized_rows: int
    market_rows: int
    quote_states: int
    incomplete_quote_groups: int
    ambiguous_outcome_groups: int
    invalid_price_groups: int
    inconsistent_metadata_groups: int
    post_commence_quote_states: int


@dataclass(frozen=True, slots=True)
class SnapshotEvidence:
    directory: Path
    snapshot_id: str
    ingested_at: pd.Timestamp
    raw_sha256: str
    normalized_rows: int
    manifest: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_utc(value: Any, *, label: str, allow_missing: bool = False) -> pd.Timestamp | pd.NaT:
    if value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip() == "":
        if allow_missing:
            return pd.NaT
        raise ValueError(f"missing {label}")
    parsed = pd.to_datetime(str(value), utc=True, errors="coerce")
    if pd.isna(parsed):
        if allow_missing:
            return pd.NaT
        raise ValueError(f"invalid {label}: {value!r}")
    return pd.Timestamp(parsed)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def discover_snapshot_directories(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(root)
    directories = sorted(
        {
            path.parent
            for path in root.rglob("manifest.json")
            if (path.parent / "normalized-outcomes.csv").is_file()
            and (path.parent / "raw-response.json").is_file()
        }
    )
    if not directories:
        raise RuntimeError(f"no complete snapshot directories under {root}")
    return directories


def verify_snapshot(directory: Path) -> SnapshotEvidence:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_meta = manifest.get("raw")
    normalized_meta = manifest.get("normalized")
    if not isinstance(raw_meta, dict) or not isinstance(normalized_meta, dict):
        raise ValueError(f"snapshot manifest missing raw/normalized metadata: {directory}")
    raw_path = directory / str(raw_meta.get("path", "raw-response.json"))
    normalized_path = directory / str(normalized_meta.get("path", "normalized-outcomes.csv"))
    if not raw_path.is_file() or not normalized_path.is_file():
        raise FileNotFoundError(f"snapshot evidence file missing: {directory}")
    expected_sha = str(raw_meta.get("sha256", ""))
    actual_sha = _sha256(raw_path)
    if not expected_sha or actual_sha != expected_sha:
        raise ValueError(f"raw SHA-256 mismatch for {directory}")
    ingested_at = _parse_utc(manifest.get("ingested_at_utc"), label="manifest ingested_at_utc")
    expected_rows = int(normalized_meta.get("rows", -1))
    actual_rows = sum(1 for _ in normalized_path.open(encoding="utf-8")) - 1
    if expected_rows != actual_rows:
        raise ValueError(
            f"normalized row-count mismatch for {directory}: manifest={expected_rows}, file={actual_rows}"
        )
    return SnapshotEvidence(
        directory=directory,
        snapshot_id=directory.name,
        ingested_at=ingested_at,
        raw_sha256=actual_sha,
        normalized_rows=actual_rows,
        manifest=manifest,
    )


def _canonical_outcome(name: Any, home_team: Any, away_team: Any) -> str | None:
    value = str(name).strip().casefold()
    home = str(home_team).strip().casefold()
    away = str(away_team).strip().casefold()
    if value and value == home:
        return "home"
    if value and value == away:
        return "away"
    if value in DRAW_LABELS:
        return "draw"
    return None


def _consistent_value(group: pd.DataFrame, column: str) -> Any:
    values = group[column].dropna().astype(str).unique().tolist()
    if len(values) != 1:
        raise ValueError(column)
    return values[0]


def _quote_hash(home: float, draw: float, away: float) -> str:
    payload = json.dumps([home, draw, away], separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def build_quote_ledger(
    snapshot_directories: Sequence[Path],
    *,
    market_key: str = "h2h",
    minimum_other_books: int = 3,
) -> tuple[pd.DataFrame, SequenceDiagnostics]:
    if minimum_other_books < 1:
        raise ValueError("minimum_other_books must be positive")
    evidence = [verify_snapshot(path) for path in snapshot_directories]
    evidence.sort(key=lambda item: (item.ingested_at, item.snapshot_id))
    if len({item.snapshot_id for item in evidence}) != len(evidence):
        raise ValueError("duplicate snapshot identity")
    times = [item.ingested_at for item in evidence]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("snapshot ingestion timestamps must be strictly increasing")

    states: list[dict[str, Any]] = []
    normalized_rows = market_rows = 0
    incomplete = ambiguous = invalid_price = inconsistent = 0

    for item in evidence:
        path = item.directory / str(item.manifest["normalized"]["path"])
        frame = pd.read_csv(path, low_memory=False)
        normalized_rows += len(frame)
        frame = frame[frame["market_key"].astype(str) == market_key].copy()
        market_rows += len(frame)
        if frame.empty:
            continue
        if frame["snapshot_ingested_at_utc"].astype(str).nunique() != 1:
            raise ValueError(f"multiple normalized ingestion timestamps in {item.directory}")
        normalized_ingested = _parse_utc(
            frame["snapshot_ingested_at_utc"].iloc[0],
            label="normalized snapshot_ingested_at_utc",
        )
        if normalized_ingested != item.ingested_at:
            raise ValueError(f"manifest/normalized ingestion timestamp mismatch: {item.directory}")

        for keys, group in frame.groupby(QUOTE_KEYS, sort=True, dropna=False):
            try:
                home_team = _consistent_value(group, "home_team")
                away_team = _consistent_value(group, "away_team")
                commence_time_text = _consistent_value(group, "commence_time")
                sport_key = _consistent_value(group, "sport_key")
                bookmaker_title = _consistent_value(group, "bookmaker_title")
            except ValueError:
                inconsistent += 1
                continue
            canonical = [
                _canonical_outcome(name, home_team, away_team)
                for name in group["outcome_name"]
            ]
            if any(value is None for value in canonical):
                ambiguous += 1
                continue
            if len(canonical) != 3 or set(canonical) != {"home", "draw", "away"}:
                incomplete += 1
                continue
            if len(set(canonical)) != len(canonical):
                ambiguous += 1
                continue
            price_map: dict[str, float] = {}
            valid = True
            for canonical_name, (_, row) in zip(canonical, group.iterrows()):
                try:
                    price = float(row["price_decimal"])
                except (TypeError, ValueError):
                    valid = False
                    break
                if not _truthy(row.get("price_valid_decimal", False)) or not np.isfinite(price) or price <= 1.0:
                    valid = False
                    break
                price_map[str(canonical_name)] = price
            if not valid:
                invalid_price += 1
                continue
            raw = np.asarray([price_map["home"], price_map["draw"], price_map["away"]], dtype=float)
            implied = 1.0 / raw
            total = float(implied.sum())
            if not np.isfinite(total) or total <= 0.0:
                invalid_price += 1
                continue
            fair = implied / total
            bookmaker_update_values = group["bookmaker_last_update"].dropna().astype(str).unique().tolist()
            market_update_values = group["market_last_update"].dropna().astype(str).unique().tolist()
            if len(bookmaker_update_values) > 1 or len(market_update_values) > 1:
                inconsistent += 1
                continue
            bookmaker_update = _parse_utc(
                bookmaker_update_values[0] if bookmaker_update_values else None,
                label="bookmaker_last_update",
                allow_missing=True,
            )
            market_update = _parse_utc(
                market_update_values[0] if market_update_values else None,
                label="market_last_update",
                allow_missing=True,
            )
            commence = _parse_utc(commence_time_text, label="commence_time")
            states.append(
                {
                    "snapshot_id": item.snapshot_id,
                    "snapshot_ingested_at": item.ingested_at,
                    "raw_sha256": item.raw_sha256,
                    "event_id": str(keys[0]),
                    "bookmaker_key": str(keys[1]),
                    "market_key": str(keys[2]),
                    "sport_key": sport_key,
                    "home_team": home_team,
                    "away_team": away_team,
                    "bookmaker_title": bookmaker_title,
                    "commence_time": commence,
                    "bookmaker_last_update": bookmaker_update,
                    "market_last_update": market_update,
                    "home_odds": raw[0],
                    "draw_odds": raw[1],
                    "away_odds": raw[2],
                    "home_p": fair[0],
                    "draw_p": fair[1],
                    "away_p": fair[2],
                    "overround": total - 1.0,
                    "quote_state_sha256": _quote_hash(*raw),
                }
            )

    ledger = pd.DataFrame(states)
    if ledger.empty:
        raise RuntimeError("no complete quote states")
    if ledger.duplicated(SNAPSHOT_QUOTE_KEYS).any():
        raise ValueError("duplicate snapshot/event/bookmaker/market quote state")
    ledger.sort_values(
        ["event_id", "bookmaker_key", "market_key", "snapshot_ingested_at", "snapshot_id"],
        inplace=True,
        kind="mergesort",
    )
    group = ledger.groupby(QUOTE_KEYS, sort=False, group_keys=False)
    ledger["previous_snapshot_id"] = group["snapshot_id"].shift(1)
    previous_time = group["snapshot_ingested_at"].shift(1)
    ledger["seconds_since_previous_observation"] = (
        ledger["snapshot_ingested_at"] - previous_time
    ).dt.total_seconds()
    previous_hash = group["quote_state_sha256"].shift(1)
    ledger["quote_changed_from_previous"] = np.where(
        previous_hash.isna(), False, ledger["quote_state_sha256"] != previous_hash
    )
    effective_update = ledger["market_last_update"].where(
        ledger["market_last_update"].notna(), ledger["bookmaker_last_update"]
    )
    previous_update = effective_update.groupby(
        [ledger[column] for column in QUOTE_KEYS], sort=False
    ).shift(1)
    ledger["provider_update_advanced"] = np.where(
        previous_update.isna() | effective_update.isna(),
        pd.NA,
        effective_update > previous_update,
    )
    ledger["state_changed_without_provider_update_advance"] = (
        ledger["quote_changed_from_previous"]
        & ledger["provider_update_advanced"].astype("boolean").fillna(False).eq(False)
        & previous_update.notna()
        & effective_update.notna()
    )
    ledger["hours_to_commence"] = (
        ledger["commence_time"] - ledger["snapshot_ingested_at"]
    ).dt.total_seconds() / 3600.0

    for outcome in ("home", "draw", "away"):
        ledger[f"consensus_{outcome}_p_ex_target"] = np.nan
        ledger[f"dispersion_{outcome}_p_ex_target"] = np.nan
    ledger["consensus_other_book_coverage"] = 0
    for _, snapshot_event in ledger.groupby(
        ["snapshot_id", "event_id", "market_key"], sort=False
    ):
        indices = snapshot_event.index.to_numpy()
        values = snapshot_event[["home_p", "draw_p", "away_p"]].to_numpy(dtype=float)
        for position, index in enumerate(indices):
            other = np.delete(values, position, axis=0)
            ledger.at[index, "consensus_other_book_coverage"] = len(other)
            if len(other) < minimum_other_books:
                continue
            for outcome_index, outcome in enumerate(("home", "draw", "away")):
                ledger.at[index, f"consensus_{outcome}_p_ex_target"] = float(
                    other[:, outcome_index].mean()
                )
                ledger.at[index, f"dispersion_{outcome}_p_ex_target"] = float(
                    other[:, outcome_index].std(ddof=0)
                )

    post_commence = int((ledger["snapshot_ingested_at"] >= ledger["commence_time"]).sum())
    diagnostics = SequenceDiagnostics(
        snapshots=len(evidence),
        normalized_rows=normalized_rows,
        market_rows=market_rows,
        quote_states=len(ledger),
        incomplete_quote_groups=incomplete,
        ambiguous_outcome_groups=ambiguous,
        invalid_price_groups=invalid_price,
        inconsistent_metadata_groups=inconsistent,
        post_commence_quote_states=post_commence,
    )
    ledger.reset_index(drop=True, inplace=True)
    return ledger, diagnostics
