from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor


DATASET_SLUG = "realsingwong/european-football-asian-handicap-odds-time-series"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"
SIGNAL_HOURS = (24, 12, 6, 4)
RANDOM_SEED = 20260718
BOOTSTRAP_REPLICATES = 2000
LINE_UNIT = 0.25
PROBABILITY_UNIT = 0.01


def download(url: str, path: Path, *, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256()
    total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:
        response.raise_for_status()
        final_url = str(response.url)
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
                fh.write(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "final_url": final_url}


def parse_handicap(value: Any) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        raise ValueError("missing handicap")
    text = str(value).strip().replace("−", "-").replace("＋", "+")
    try:
        return abs(float(text))
    except ValueError:
        pass
    if "/" not in text:
        raise ValueError(f"unsupported handicap value: {value!r}")
    left_text, right_text = (part.strip() for part in text.split("/", 1))
    left = float(left_text)
    if right_text.startswith(("+", "-")):
        right = float(right_text)
    else:
        sign = -1.0 if left < 0 else 1.0
        right = sign * float(right_text)
    return abs((left + right) / 2.0)


def transform_quote(home_payout: float, away_payout: float, handicap: Any) -> tuple[float, float, float]:
    if not np.isfinite(home_payout) or not np.isfinite(away_payout):
        raise ValueError("non-finite payout")
    if home_payout <= 0.0 or away_payout <= 0.0:
        raise ValueError("Hong Kong payouts must be positive")
    decimal_home = 1.0 + float(home_payout)
    decimal_away = 1.0 + float(away_payout)
    q_home = 1.0 / decimal_home
    q_away = 1.0 / decimal_away
    total = q_home + q_away
    if total <= 0.0:
        raise ValueError("invalid implied-probability total")
    p_home = q_home / total
    overround = total - 1.0
    return parse_handicap(handicap), p_home, overround


def archive_relative_path(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if len(path.parts) < 2:
        return None
    return PurePosixPath(*path.parts[1:])


def match_id_from_path(path: str) -> str:
    match = re.search(r"match_(\d+)\.csv$", path)
    if not match:
        raise ValueError(f"cannot parse match id from path: {path}")
    return match.group(1)


def load_matches(archive: Path, extracted_root: Path) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, Any]]:
    if extracted_root.exists():
        shutil.rmtree(extracted_root)
    extracted_root.mkdir(parents=True)
    matches: dict[str, pd.DataFrame] = {}
    metadata_rows: list[dict[str, Any]] = []
    invalid_rows = 0
    invalid_handicaps: dict[str, int] = {}
    with zipfile.ZipFile(archive) as zf:
        csv_infos = []
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = archive_relative_path(info.filename)
            if rel is None or not str(rel).startswith("sample/") or not str(rel).endswith(".csv"):
                continue
            csv_infos.append((str(rel), info))
        if len(csv_infos) != 90:
            raise RuntimeError(f"expected 90 sample CSV files, found {len(csv_infos)}")

        for rel, info in sorted(csv_infos):
            target = extracted_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            frame = pd.read_csv(target)
            required = {
                "Teams", "FT Score", "HT Score", "Bookmaker",
                "Home Odds", "Handicap", "Away Odds", "Timestamp",
            }
            missing = sorted(required - set(frame.columns))
            if missing:
                raise ValueError(f"{rel} missing columns: {missing}")
            frame["Timestamp"] = pd.to_datetime(
                frame["Timestamp"].astype(str),
                format="%Y%m%d%H%M%S",
                errors="coerce",
                utc=True,
            ).dt.tz_convert(None)
            frame["Home Odds"] = pd.to_numeric(frame["Home Odds"], errors="coerce")
            frame["Away Odds"] = pd.to_numeric(frame["Away Odds"], errors="coerce")
            frame = frame.dropna(subset=["Timestamp", "Bookmaker", "Home Odds", "Away Odds"]).copy()

            transformed = []
            keep = []
            for index, row in frame.iterrows():
                try:
                    transformed.append(
                        transform_quote(float(row["Home Odds"]), float(row["Away Odds"]), row["Handicap"])
                    )
                    keep.append(index)
                except (ValueError, TypeError) as exc:
                    invalid_rows += 1
                    key = str(row["Handicap"])
                    invalid_handicaps[key] = invalid_handicaps.get(key, 0) + 1
            frame = frame.loc[keep].copy()
            if not transformed:
                raise RuntimeError(f"no valid quotes in {rel}")
            transformed_array = np.asarray(transformed, dtype=float)
            frame["line_magnitude"] = transformed_array[:, 0]
            frame["home_share"] = transformed_array[:, 1]
            frame["overround"] = transformed_array[:, 2]
            frame["Bookmaker"] = frame["Bookmaker"].astype(str)
            frame.sort_values(["Bookmaker", "Timestamp"], inplace=True)

            match_id = match_id_from_path(rel)
            league = PurePosixPath(rel).parts[1]
            close_marker = pd.Timestamp(frame["Timestamp"].max()).as_unit("ns")
            if frame["Teams"].nunique(dropna=False) != 1:
                raise ValueError(f"multiple team labels in {rel}")
            matches[match_id] = frame
            metadata_rows.append(
                {
                    "match_id": match_id,
                    "league": league,
                    "close_marker": close_marker,
                    "source_path": rel,
                    "teams": str(frame["Teams"].iloc[0]),
                    "rows": int(len(frame)),
                    "bookmakers": int(frame["Bookmaker"].nunique()),
                }
            )

    metadata = pd.DataFrame(metadata_rows)
    league_counts = metadata["league"].value_counts().to_dict()
    if league_counts != {"EPL": 30, "LaLiga": 30, "SerieA": 30}:
        raise RuntimeError(f"unexpected league counts: {league_counts}")
    profile = {
        "matches": int(len(metadata)),
        "rows": int(metadata["rows"].sum()),
        "league_counts": {str(k): int(v) for k, v in sorted(league_counts.items())},
        "invalid_quote_rows": int(invalid_rows),
        "invalid_handicap_values": invalid_handicaps,
        "bookmaker_count_min": int(metadata["bookmakers"].min()),
        "bookmaker_count_max": int(metadata["bookmakers"].max()),
    }
    return matches, metadata, profile


def assign_splits(metadata: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    output = metadata.copy()
    output["split"] = ""
    league_profiles: dict[str, Any] = {}
    for league, group in output.groupby("league", sort=True):
        ordered = group.sort_values(["close_marker", "match_id"], kind="mergesort")
        if len(ordered) != 30:
            raise RuntimeError(f"league {league} does not contain 30 matches")
        train_ids = ordered.iloc[:18]["match_id"]
        validation_ids = ordered.iloc[18:24]["match_id"]
        test_ids = ordered.iloc[24:]["match_id"]
        output.loc[output["match_id"].isin(train_ids), "split"] = "train"
        output.loc[output["match_id"].isin(validation_ids), "split"] = "validation"
        output.loc[output["match_id"].isin(test_ids), "split"] = "test"
        league_profiles[str(league)] = {
            "train": train_ids.astype(str).tolist(),
            "validation": validation_ids.astype(str).tolist(),
            "test": test_ids.astype(str).tolist(),
        }
    if (output["split"] == "").any():
        raise RuntimeError("unassigned matches")
    counts = output["split"].value_counts().to_dict()
    if counts != {"train": 54, "validation": 18, "test": 18}:
        raise RuntimeError(f"unexpected split counts: {counts}")
    return output, {
        "counts": {str(k): int(v) for k, v in sorted(counts.items())},
        "by_league": league_profiles,
    }


def state_at(history: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, Any] | None:
    times = history["Timestamp"].to_numpy(dtype="datetime64[ns]").astype(np.int64)
    index = int(np.searchsorted(times, timestamp.value, side="right") - 1)
    if index < 0:
        return None
    row = history.iloc[index]
    return {
        "index": index,
        "time": pd.Timestamp(row["Timestamp"]).as_unit("ns"),
        "line": float(row["line_magnitude"]),
        "home_share": float(row["home_share"]),
        "overround": float(row["overround"]),
        "home_payout": float(row["Home Odds"]),
        "away_payout": float(row["Away Odds"]),
    }


def quote_moved(left: dict[str, Any], right: dict[str, Any]) -> int:
    return int(
        abs(float(right["line"]) - float(left["line"])) > 1e-12
        or abs(float(right["home_payout"]) - float(left["home_payout"])) > 1e-12
        or abs(float(right["away_payout"]) - float(left["away_payout"])) > 1e-12
    )


def summarize_other_books(
    histories: dict[str, pd.DataFrame],
    target_book: str,
    prior_t: pd.Timestamp,
    current_t: pd.Timestamp,
) -> dict[str, float] | None:
    prior_states = []
    current_states = []
    moved = []
    for bookmaker, history in histories.items():
        if bookmaker == target_book:
            continue
        prior = state_at(history, prior_t)
        current = state_at(history, current_t)
        if current is not None:
            current_states.append(current)
        if prior is not None:
            prior_states.append(prior)
        if prior is not None and current is not None:
            moved.append(quote_moved(prior, current))
    if len(current_states) < 3 or len(prior_states) < 3:
        return None

    def values(states: list[dict[str, Any]], key: str) -> np.ndarray:
        return np.asarray([float(item[key]) for item in states], dtype=float)

    current_line = values(current_states, "line")
    current_home = values(current_states, "home_share")
    current_over = values(current_states, "overround")
    prior_line = values(prior_states, "line")
    prior_home = values(prior_states, "home_share")
    prior_over = values(prior_states, "overround")
    return {
        "consensus_current_line": float(np.median(current_line)),
        "consensus_current_home": float(np.median(current_home)),
        "consensus_current_over": float(np.median(current_over)),
        "consensus_prior_line": float(np.median(prior_line)),
        "consensus_prior_home": float(np.median(prior_home)),
        "consensus_prior_over": float(np.median(prior_over)),
        "dispersion_current_line": float(np.std(current_line, ddof=0)),
        "dispersion_current_home": float(np.std(current_home, ddof=0)),
        "dispersion_current_over": float(np.std(current_over, ddof=0)),
        "other_move_fraction": float(np.mean(moved)) if moved else 0.0,
        "other_current_coverage": float(len(current_states)),
        "other_prior_coverage": float(len(prior_states)),
    }


def build_state_records(
    matches: dict[str, pd.DataFrame],
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    bookmaker_universe = sorted(
        {bookmaker for frame in matches.values() for bookmaker in frame["Bookmaker"].astype(str).unique()}
    )
    league_universe = sorted(metadata["league"].unique().tolist())
    rows: list[dict[str, Any]] = []
    missing_state_counts: dict[str, int] = {"target": 0, "consensus": 0}

    metadata_index = metadata.set_index("match_id")
    for match_id, frame in matches.items():
        meta = metadata_index.loc[match_id]
        close_marker = pd.Timestamp(meta["close_marker"]).as_unit("ns")
        histories = {
            bookmaker: group.sort_values("Timestamp", kind="mergesort").reset_index(drop=True)
            for bookmaker, group in frame.groupby("Bookmaker", sort=True)
        }
        for hours in SIGNAL_HOURS:
            prior_t = close_marker - pd.Timedelta(hours=hours + 1)
            current_t = close_marker - pd.Timedelta(hours=hours)
            observation_t = close_marker - pd.Timedelta(hours=hours - 1)
            future_t = close_marker - pd.Timedelta(hours=max(hours - 4, 0))
            for bookmaker, history in histories.items():
                prior = state_at(history, prior_t)
                current = state_at(history, current_t)
                observation = state_at(history, observation_t)
                future = state_at(history, future_t)
                if prior is None or current is None or observation is None or future is None:
                    missing_state_counts["target"] += 1
                    continue
                consensus = summarize_other_books(histories, bookmaker, prior_t, current_t)
                if consensus is None:
                    missing_state_counts["consensus"] += 1
                    continue
                actual_move = quote_moved(current, observation)
                future_move = quote_moved(observation, future)
                row: dict[str, Any] = {
                    "match_id": str(match_id),
                    "league": str(meta["league"]),
                    "split": str(meta["split"]),
                    "bookmaker": str(bookmaker),
                    "hours_to_close": int(hours),
                    "close_marker": close_marker,
                    "own_current_line": current["line"],
                    "own_current_home": current["home_share"],
                    "own_current_over": current["overround"],
                    "own_prior_line": prior["line"],
                    "own_prior_home": prior["home_share"],
                    "own_prior_over": prior["overround"],
                    "own_prior_delta_line": current["line"] - prior["line"],
                    "own_prior_delta_home": current["home_share"] - prior["home_share"],
                    "own_prior_delta_over": current["overround"] - prior["overround"],
                    **consensus,
                    "consensus_delta_line": consensus["consensus_current_line"] - consensus["consensus_prior_line"],
                    "consensus_delta_home": consensus["consensus_current_home"] - consensus["consensus_prior_home"],
                    "consensus_delta_over": consensus["consensus_current_over"] - consensus["consensus_prior_over"],
                    "own_vs_consensus_line": current["line"] - consensus["consensus_current_line"],
                    "own_vs_consensus_home": current["home_share"] - consensus["consensus_current_home"],
                    "hours_scaled": hours / 24.0,
                    "actual_move": actual_move,
                    "actual_delta_line": observation["line"] - current["line"],
                    "actual_delta_home": observation["home_share"] - current["home_share"],
                    "observation_line": observation["line"],
                    "observation_home": observation["home_share"],
                    "observation_over": observation["overround"],
                    "future_move": future_move,
                    "future_delta_line": future["line"] - observation["line"],
                    "future_delta_home": future["home_share"] - observation["home_share"],
                    "future_line": future["line"],
                    "future_home": future["home_share"],
                }
                for book in bookmaker_universe:
                    row[f"book__{book}"] = float(book == bookmaker)
                for league in league_universe:
                    row[f"league__{league}"] = float(league == meta["league"])
                for cutoff in SIGNAL_HOURS:
                    row[f"cutoff__{cutoff}"] = float(cutoff == hours)
                rows.append(row)

    states = pd.DataFrame.from_records(rows)
    if states.empty:
        raise RuntimeError("no eligible AH states")
    keys = ["match_id", "bookmaker", "hours_to_close"]
    if states.duplicated(keys).any():
        raise RuntimeError("duplicate AH match/book/cutoff states")
    feature_columns = [
        "own_current_line", "own_current_home", "own_current_over",
        "own_prior_line", "own_prior_home", "own_prior_over",
        "own_prior_delta_line", "own_prior_delta_home", "own_prior_delta_over",
        "consensus_current_line", "consensus_current_home", "consensus_current_over",
        "consensus_prior_line", "consensus_prior_home", "consensus_prior_over",
        "dispersion_current_line", "dispersion_current_home", "dispersion_current_over",
        "other_move_fraction", "other_current_coverage", "other_prior_coverage",
        "consensus_delta_line", "consensus_delta_home", "consensus_delta_over",
        "own_vs_consensus_line", "own_vs_consensus_home", "hours_scaled",
        *[f"book__{book}" for book in bookmaker_universe],
        *[f"league__{league}" for league in league_universe],
        *[f"cutoff__{cutoff}" for cutoff in SIGNAL_HOURS],
    ]
    numeric = states[feature_columns + [
        "actual_delta_line", "actual_delta_home", "observation_line", "observation_home",
        "observation_over", "future_delta_line", "future_delta_home",
    ]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("non-finite AH model values")
    profile = {
        "rows": int(len(states)),
        "matches": int(states["match_id"].nunique()),
        "bookmakers": bookmaker_universe,
        "leagues": league_universe,
        "missing_state_counts": missing_state_counts,
        "rows_by_split": {str(k): int(v) for k, v in states["split"].value_counts().sort_index().items()},
        "rows_by_cutoff": {str(int(k)): int(v) for k, v in states["hours_to_close"].value_counts().sort_index().items()},
        "move_rate": float(states["actual_move"].mean()),
        "future_move_rate": float(states["future_move"].mean()),
    }
    return states, feature_columns, profile


def fixed_classifier(*, leaves: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=leaves,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )


def fixed_regressor(*, leaves: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.08,
        max_leaf_nodes=leaves,
        l2_regularization=1.0,
        random_state=RANDOM_SEED,
    )


def bootstrap_match(
    match_ids: np.ndarray,
    row_improvement: np.ndarray,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    frame = pd.DataFrame({"match_id": match_ids.astype(str), "improvement": row_improvement})
    grouped = frame.groupby("match_id", sort=False)["improvement"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(dtype=float)
    counts = grouped["count"].to_numpy(dtype=int)
    rng = np.random.default_rng(RANDOM_SEED)
    draws = np.empty(replicates, dtype=float)
    for index in range(replicates):
        sample = rng.integers(0, len(sums), size=len(sums))
        draws[index] = sums[sample].sum() / counts[sample].sum()
    low, high = np.quantile(draws, [0.025, 0.975])
    return {
        "matches": int(len(sums)),
        "replicates": int(replicates),
        "mean_improvement": float(sums.sum() / counts.sum()),
        "ci95_low": float(low),
        "ci95_high": float(high),
    }


def train_normal_models(
    train: pd.DataFrame,
    features: list[str],
) -> tuple[HistGradientBoostingClassifier, list[HistGradientBoostingRegressor], dict[str, Any]]:
    hazard = fixed_classifier(leaves=31)
    hazard.fit(train[features], train["actual_move"])
    movers = train[train["actual_move"] == 1].copy()
    if movers.empty:
        raise RuntimeError("no training mover states")
    regressors = []
    for target in ("actual_delta_line", "actual_delta_home"):
        model = fixed_regressor(leaves=31)
        model.fit(movers[features], movers[target])
        regressors.append(model)
    return hazard, regressors, {
        "train_rows": int(len(train)),
        "train_matches": int(train["match_id"].nunique()),
        "train_movers": int(len(movers)),
        "train_move_rate": float(train["actual_move"].mean()),
    }


def generate_residuals(
    frame: pd.DataFrame,
    features: list[str],
    hazard: HistGradientBoostingClassifier,
    movement_models: list[HistGradientBoostingRegressor],
) -> pd.DataFrame:
    output = frame.copy()
    p_move = hazard.predict_proba(output[features])[:, 1]
    predicted_delta = np.column_stack([model.predict(output[features]) for model in movement_models])
    actual_delta = output[["actual_delta_line", "actual_delta_home"]].to_numpy(dtype=float)
    actual_move = output["actual_move"].to_numpy(dtype=float)
    conditional = actual_delta - predicted_delta
    conditional[actual_move == 0.0, :] = 0.0
    action = actual_delta - p_move[:, None] * predicted_delta
    output["predicted_move_probability"] = p_move
    output["move_surprise"] = actual_move - p_move
    output["move_surprise_abs"] = np.abs(output["move_surprise"].to_numpy(dtype=float))
    output["conditional_residual_line"] = conditional[:, 0]
    output["conditional_residual_home"] = conditional[:, 1]
    output["conditional_residual_l2"] = np.sqrt((conditional[:, 0] / LINE_UNIT) ** 2 + (conditional[:, 1] / PROBABILITY_UNIT) ** 2)
    output["action_residual_line"] = action[:, 0]
    output["action_residual_home"] = action[:, 1]
    output["action_residual_l2"] = np.sqrt((action[:, 0] / LINE_UNIT) ** 2 + (action[:, 1] / PROBABILITY_UNIT) ** 2)

    output["prior_residual_cutoffs"] = 0.0
    output["prior_move_surprise_mean"] = 0.0
    output["prior_abs_move_surprise_mean"] = 0.0
    output["prior_action_residual_l2_mean"] = 0.0
    output["prior_action_residual_line_sum"] = 0.0
    output["prior_action_residual_home_sum"] = 0.0
    rank = {hours: index for index, hours in enumerate(SIGNAL_HOURS)}
    output["_rank"] = output["hours_to_close"].map(rank).astype(int)
    output.sort_values(["match_id", "bookmaker", "_rank"], inplace=True)
    for (_match_id, _bookmaker), group in output.groupby(["match_id", "bookmaker"], sort=False):
        move_values: list[float] = []
        abs_move_values: list[float] = []
        l2_values: list[float] = []
        cumulative_line = 0.0
        cumulative_home = 0.0
        for index in group.sort_values("_rank").index:
            output.at[index, "prior_residual_cutoffs"] = float(len(move_values))
            if move_values:
                output.at[index, "prior_move_surprise_mean"] = float(np.mean(move_values))
                output.at[index, "prior_abs_move_surprise_mean"] = float(np.mean(abs_move_values))
                output.at[index, "prior_action_residual_l2_mean"] = float(np.mean(l2_values))
                output.at[index, "prior_action_residual_line_sum"] = cumulative_line
                output.at[index, "prior_action_residual_home_sum"] = cumulative_home
            move_value = float(output.at[index, "move_surprise"])
            action_l2 = float(output.at[index, "action_residual_l2"])
            move_values.append(move_value)
            abs_move_values.append(abs(move_value))
            l2_values.append(action_l2)
            cumulative_line += float(output.at[index, "action_residual_line"])
            cumulative_home += float(output.at[index, "action_residual_home"])
    output.drop(columns=["_rank"], inplace=True)
    return output


def evaluate_normal_layers(
    test: pd.DataFrame,
    features: list[str],
    hazard: HistGradientBoostingClassifier,
    movement_models: list[HistGradientBoostingRegressor],
) -> dict[str, Any]:
    y = test["actual_move"].to_numpy(dtype=float)
    p = hazard.predict_proba(test[features])[:, 1]
    hazard_brier = float(np.mean((y - p) ** 2))
    movers = test["actual_move"].to_numpy(dtype=int) == 1
    actual = test.loc[movers, ["actual_delta_line", "actual_delta_home"]].to_numpy(dtype=float)
    predicted = np.column_stack([model.predict(test.loc[movers, features]) for model in movement_models])
    return {
        "test_rows": int(len(test)),
        "test_matches": int(test["match_id"].nunique()),
        "move_rate": float(y.mean()),
        "hazard_brier": hazard_brier,
        "mover_rows": int(movers.sum()),
        "conditional_line_mae": float(np.mean(np.abs(actual[:, 0] - predicted[:, 0]))),
        "conditional_home_share_mae": float(np.mean(np.abs(actual[:, 1] - predicted[:, 1]))),
    }


def future_model_features(
    frame: pd.DataFrame,
    normal_features: list[str],
) -> tuple[list[str], list[str]]:
    baseline = [
        *normal_features,
        "actual_move", "actual_delta_line", "actual_delta_home",
        "observation_line", "observation_home", "observation_over",
    ]
    residual = [
        "predicted_move_probability", "move_surprise", "move_surprise_abs",
        "conditional_residual_line", "conditional_residual_home", "conditional_residual_l2",
        "action_residual_line", "action_residual_home", "action_residual_l2",
        "prior_residual_cutoffs", "prior_move_surprise_mean", "prior_abs_move_surprise_mean",
        "prior_action_residual_l2_mean", "prior_action_residual_line_sum", "prior_action_residual_home_sum",
    ]
    augmented = baseline + residual
    for name, columns in (("baseline", baseline), ("augmented", augmented)):
        values = frame[columns].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            bad = np.asarray(columns)[~np.isfinite(values).all(axis=0)].tolist()
            raise ValueError(f"non-finite {name} features: {bad}")
    return baseline, augmented


def evaluate_future_hazard(
    test: pd.DataFrame,
    baseline_probability: np.ndarray,
    augmented_probability: np.ndarray,
) -> dict[str, Any]:
    y = test["future_move"].to_numpy(dtype=float)
    baseline_error = (y - baseline_probability) ** 2
    augmented_error = (y - augmented_probability) ** 2
    improvement = baseline_error - augmented_error
    bootstrap = bootstrap_match(test["match_id"].to_numpy(), improvement)
    by_cutoff = {}
    improved = 0
    for hours in SIGNAL_HOURS:
        mask = test["hours_to_close"].to_numpy(dtype=int) == hours
        base = float(baseline_error[mask].mean())
        aug = float(augmented_error[mask].mean())
        diff = base - aug
        by_cutoff[f"C-{hours}h"] = {
            "rows": int(mask.sum()),
            "baseline_brier": base,
            "augmented_brier": aug,
            "improvement": float(diff),
        }
        improved += int(diff > 0.0)
    baseline = float(baseline_error.mean())
    augmented = float(augmented_error.mean())
    checks = {
        "augmented_brier_lower": augmented < baseline,
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "improves_at_least_3_of_4_cutoffs": improved >= 3,
    }
    return {
        "baseline_brier": baseline,
        "augmented_brier": augmented,
        "improvement": float(baseline - augmented),
        "relative_improvement": float((baseline - augmented) / baseline),
        "paired_match_bootstrap": bootstrap,
        "by_cutoff": by_cutoff,
        "improved_cutoffs": improved,
        "checks": checks,
        "promoted": all(checks.values()),
    }


def evaluate_future_conditional(
    test_movers: pd.DataFrame,
    baseline_prediction: np.ndarray,
    augmented_prediction: np.ndarray,
) -> dict[str, Any]:
    actual = test_movers[["future_delta_line", "future_delta_home"]].to_numpy(dtype=float)
    baseline_line_error = np.abs(actual[:, 0] - baseline_prediction[:, 0])
    augmented_line_error = np.abs(actual[:, 0] - augmented_prediction[:, 0])
    baseline_home_error = np.abs(actual[:, 1] - baseline_prediction[:, 1])
    augmented_home_error = np.abs(actual[:, 1] - augmented_prediction[:, 1])
    baseline_composite = 0.5 * (
        baseline_line_error / LINE_UNIT + baseline_home_error / PROBABILITY_UNIT
    )
    augmented_composite = 0.5 * (
        augmented_line_error / LINE_UNIT + augmented_home_error / PROBABILITY_UNIT
    )
    improvement = baseline_composite - augmented_composite
    bootstrap = bootstrap_match(test_movers["match_id"].to_numpy(), improvement)
    by_cutoff = {}
    improved = 0
    for hours in SIGNAL_HOURS:
        mask = test_movers["hours_to_close"].to_numpy(dtype=int) == hours
        base = float(baseline_composite[mask].mean())
        aug = float(augmented_composite[mask].mean())
        diff = base - aug
        by_cutoff[f"C-{hours}h"] = {
            "mover_rows": int(mask.sum()),
            "baseline_composite_mae": base,
            "augmented_composite_mae": aug,
            "improvement": float(diff),
            "baseline_line_mae": float(baseline_line_error[mask].mean()),
            "augmented_line_mae": float(augmented_line_error[mask].mean()),
            "baseline_home_share_mae": float(baseline_home_error[mask].mean()),
            "augmented_home_share_mae": float(augmented_home_error[mask].mean()),
        }
        improved += int(diff > 0.0)
    baseline_composite_mean = float(baseline_composite.mean())
    augmented_composite_mean = float(augmented_composite.mean())
    baseline_line_mae = float(baseline_line_error.mean())
    augmented_line_mae = float(augmented_line_error.mean())
    baseline_home_mae = float(baseline_home_error.mean())
    augmented_home_mae = float(augmented_home_error.mean())
    line_ratio = augmented_line_mae / baseline_line_mae if baseline_line_mae > 0 else 1.0
    home_ratio = augmented_home_mae / baseline_home_mae if baseline_home_mae > 0 else 1.0
    checks = {
        "augmented_composite_lower": augmented_composite_mean < baseline_composite_mean,
        "bootstrap_ci_above_zero": bootstrap["ci95_low"] > 0.0,
        "improves_at_least_3_of_4_cutoffs": improved >= 3,
        "line_mae_not_worse_by_more_than_2pct": line_ratio <= 1.02,
        "home_share_mae_not_worse_by_more_than_2pct": home_ratio <= 1.02,
    }
    return {
        "mover_rows": int(len(test_movers)),
        "mover_matches": int(test_movers["match_id"].nunique()),
        "baseline_composite_mae": baseline_composite_mean,
        "augmented_composite_mae": augmented_composite_mean,
        "composite_improvement": float(baseline_composite_mean - augmented_composite_mean),
        "relative_composite_improvement": float(
            (baseline_composite_mean - augmented_composite_mean) / baseline_composite_mean
        ),
        "baseline_line_mae": baseline_line_mae,
        "augmented_line_mae": augmented_line_mae,
        "line_mae_ratio": float(line_ratio),
        "baseline_home_share_mae": baseline_home_mae,
        "augmented_home_share_mae": augmented_home_mae,
        "home_share_mae_ratio": float(home_ratio),
        "paired_match_bootstrap": bootstrap,
        "by_cutoff": by_cutoff,
        "improved_cutoffs": improved,
        "checks": checks,
        "promoted": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run modern Asian Handicap abnormal-residual repricing test.")
    parser.add_argument("--output-root", default="artifacts/experiment-010")
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    failure_path = root / "failure.json"
    progress_path = root / "progress.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True), encoding="utf-8")

    try:
        progress("acquiring_source")
        archive = root / "raw" / "dataset.zip"
        archive_meta = download(DOWNLOAD_URL, archive)
        if not zipfile.is_zipfile(archive):
            raise ValueError("downloaded dataset is not a ZIP archive")

        progress("loading_modern_ah_sample")
        matches, metadata, source_profile = load_matches(archive, root / "extracted")
        metadata, split_definition = assign_splits(metadata)
        progress("building_cross_book_states")
        states, normal_features, state_profile = build_state_records(matches, metadata)
        train = states[states["split"] == "train"].copy()
        validation = states[states["split"] == "validation"].copy()
        test = states[states["split"] == "test"].copy()
        for label, frame in (("train", train), ("validation", validation), ("test", test)):
            if frame.empty:
                raise RuntimeError(f"empty {label} state split")
            if len(np.unique(frame["actual_move"].to_numpy(dtype=int))) < 2:
                raise RuntimeError(f"{label} contains one normal-move class")
            if len(np.unique(frame["future_move"].to_numpy(dtype=int))) < 2:
                raise RuntimeError(f"{label} contains one future-move class")

        progress("training_normal_models")
        hazard, movement_models, normal_training = train_normal_models(train, normal_features)
        normal_test = evaluate_normal_layers(test, normal_features, hazard, movement_models)
        validation_residuals = generate_residuals(validation, normal_features, hazard, movement_models)
        test_residuals = generate_residuals(test, normal_features, hazard, movement_models)
        baseline_features, augmented_features = future_model_features(validation_residuals, normal_features)
        baseline_test, augmented_test = future_model_features(test_residuals, normal_features)
        if baseline_features != baseline_test or augmented_features != augmented_test:
            raise RuntimeError("validation/test future feature schemas differ")

        progress("training_future_repricing_models")
        baseline_hazard = fixed_classifier(leaves=15)
        augmented_hazard = fixed_classifier(leaves=15)
        baseline_hazard.fit(validation_residuals[baseline_features], validation_residuals["future_move"])
        augmented_hazard.fit(validation_residuals[augmented_features], validation_residuals["future_move"])
        baseline_probability = baseline_hazard.predict_proba(test_residuals[baseline_features])[:, 1]
        augmented_probability = augmented_hazard.predict_proba(test_residuals[augmented_features])[:, 1]
        future_hazard = evaluate_future_hazard(test_residuals, baseline_probability, augmented_probability)

        validation_movers = validation_residuals[validation_residuals["future_move"] == 1].copy()
        test_movers = test_residuals[test_residuals["future_move"] == 1].copy()
        if validation_movers.empty or test_movers.empty:
            raise RuntimeError("empty validation/test future mover set")
        baseline_prediction = np.empty((len(test_movers), 2), dtype=float)
        augmented_prediction = np.empty((len(test_movers), 2), dtype=float)
        for target_index, target in enumerate(("future_delta_line", "future_delta_home")):
            baseline_model = fixed_regressor(leaves=15)
            augmented_model = fixed_regressor(leaves=15)
            baseline_model.fit(validation_movers[baseline_features], validation_movers[target])
            augmented_model.fit(validation_movers[augmented_features], validation_movers[target])
            baseline_prediction[:, target_index] = baseline_model.predict(test_movers[baseline_features])
            augmented_prediction[:, target_index] = augmented_model.predict(test_movers[augmented_features])
        future_conditional = evaluate_future_conditional(
            test_movers, baseline_prediction, augmented_prediction
        )

        promotion_checks = {
            "future_move_hazard_promoted": future_hazard["promoted"],
            "conditional_future_repricing_promoted": future_conditional["promoted"],
        }
        report = {
            "experiment": "010_modern_asian_handicap_residual_repricing",
            "status": "completed",
            "archive": archive_meta,
            "source_profile": source_profile,
            "split_definition": split_definition,
            "state_profile": state_profile,
            "normal_training": normal_training,
            "normal_test": normal_test,
            "validation_rows": int(len(validation_residuals)),
            "validation_matches": int(validation_residuals["match_id"].nunique()),
            "test_rows": int(len(test_residuals)),
            "test_matches": int(test_residuals["match_id"].nunique()),
            "future_move_hazard": future_hazard,
            "conditional_future_repricing": future_conditional,
            "promotion_checks": promotion_checks,
            "modern_ah_residual_repricing_promoted": all(promotion_checks.values()),
            "timing_warning": "C is the provider's maximum recorded timestamp, not independently verified kickoff.",
            "handicap_warning": "absolute handicap magnitude is used because source sign orientation is not independently verified as home-oriented.",
        }
        (root / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        validation_residuals.to_csv(root / "validation_residuals.csv.gz", index=False, compression="gzip")
        test_residuals.to_csv(root / "test_residuals.csv.gz", index=False, compression="gzip")
        print(json.dumps(report, indent=2, sort_keys=True))
        failure_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "progress": json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else None,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
