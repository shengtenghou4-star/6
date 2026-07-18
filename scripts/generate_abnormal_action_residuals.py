from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from experiment_002_move_hazard import (
    BOOKMAKER_NAMES,
    BOOKS,
    CUTOFFS,
    DOWNLOAD_URL,
    RANDOM_SEED,
    SELECTED_BOOKS,
    SERIES_FILES,
    consensus_excluding_target,
    download,
    extract_required,
    other_move_fraction,
    raw_and_devig,
    split_names,
)


OUTCOMES = ("home", "draw", "away")


def state_columns(books: tuple[int, ...], index: int) -> list[str]:
    return [f"{outcome}_b{book}_{index}" for book in books for outcome in OUTCOMES]


def build_all_state_records(paths: list[Path], *, chunksize: int) -> dict[str, dict[str, Any]]:
    all_indices = {idx for current in CUTOFFS.values() for idx in (current - 1, current, current + 1)}
    usecols = ["match_id", "match_date"] + [
        f"{outcome}_b{book}_{idx}"
        for book in BOOKS
        for outcome in OUTCOMES
        for idx in sorted(all_indices)
    ]
    buffers: dict[str, dict[str, list[np.ndarray]]] = {
        split: {
            "X": [], "y_move": [], "current": [], "actual_delta": [], "consensus": [],
            "match_id": [], "book": [], "hours": [],
        }
        for split in ("train", "validation", "test")
    }
    diagnostics = {"candidate_states": 0, "eligible_states": 0, "eligible_movers": 0}

    for path in paths:
        for frame in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
            dates = pd.to_datetime(frame["match_date"], errors="coerce")
            if dates.isna().any():
                raise ValueError(f"unparsed match dates in {path.name}")
            splits = split_names(dates)
            match_ids = frame["match_id"].astype(str).to_numpy()
            cache = {idx: raw_and_devig(frame, BOOKS, idx) for idx in sorted(all_indices)}

            for hours, current_idx in CUTOFFS.items():
                prior_idx, next_idx = current_idx - 1, current_idx + 1
                raw_prior, p_prior, over_prior, complete_prior = cache[prior_idx]
                raw_current, p_current, over_current, complete_current = cache[current_idx]
                raw_next, p_next, _, complete_next = cache[next_idx]

                for book_position, book in enumerate(SELECTED_BOOKS):
                    axis = book - 1
                    own_valid = complete_prior[:, axis] & complete_current[:, axis] & complete_next[:, axis]
                    consensus_current, dispersion_current, active_current = consensus_excluding_target(p_current, complete_current, axis)
                    consensus_prior, _, active_prior = consensus_excluding_target(p_prior, complete_prior, axis)
                    other_fraction, other_valid = other_move_fraction(raw_prior, raw_current, complete_prior, complete_current, axis)
                    market_valid = (active_current >= 3) & (active_prior >= 3) & (other_valid >= 3) & np.isfinite(other_fraction)
                    eligible = own_valid & market_valid
                    moved_next = np.any(np.abs(raw_next[:, axis, :] - raw_current[:, axis, :]) > 1e-12, axis=1)

                    diagnostics["candidate_states"] += len(frame)
                    diagnostics["eligible_states"] += int(eligible.sum())
                    diagnostics["eligible_movers"] += int((eligible & moved_next).sum())
                    if not eligible.any():
                        continue

                    own_current = p_current[:, axis, :]
                    own_prior = p_prior[:, axis, :]
                    own_next = p_next[:, axis, :]
                    own_delta_prior = own_current - own_prior
                    over_cur = over_current[:, axis][:, None]
                    over_prev = over_prior[:, axis][:, None]
                    over_delta = over_cur - over_prev
                    consensus_delta = consensus_current - consensus_prior
                    deviation_current = own_current - consensus_current
                    active_scaled = active_current.astype(np.float64)[:, None] / 31.0
                    other_fraction_col = other_fraction[:, None]
                    hours_scaled = np.full((len(frame), 1), hours / 71.0, dtype=np.float64)
                    book_onehot = np.zeros((len(frame), len(SELECTED_BOOKS)), dtype=np.float64)
                    book_onehot[:, book_position] = 1.0

                    X = np.concatenate(
                        [
                            own_current, own_prior, own_delta_prior,
                            over_cur, over_prev, over_delta,
                            consensus_current, consensus_prior, consensus_delta,
                            deviation_current, dispersion_current,
                            active_scaled, other_fraction_col, hours_scaled, book_onehot,
                        ],
                        axis=1,
                    )
                    actual_delta = own_next - own_current

                    for split in ("train", "validation", "test"):
                        mask = eligible & (splits == split)
                        if not mask.any():
                            continue
                        buf = buffers[split]
                        buf["X"].append(X[mask].astype(np.float32, copy=False))
                        buf["y_move"].append(moved_next[mask].astype(np.int8, copy=False))
                        buf["current"].append(own_current[mask].astype(np.float32, copy=False))
                        buf["actual_delta"].append(actual_delta[mask].astype(np.float32, copy=False))
                        buf["consensus"].append(consensus_current[mask].astype(np.float32, copy=False))
                        buf["match_id"].append(match_ids[mask])
                        buf["book"].append(np.full(int(mask.sum()), book, dtype=np.int16))
                        buf["hours"].append(np.full(int(mask.sum()), hours, dtype=np.int16))

    result: dict[str, dict[str, Any]] = {}
    for split, buf in buffers.items():
        if not buf["X"]:
            raise RuntimeError(f"no eligible records for {split}")
        result[split] = {key: np.concatenate(parts) for key, parts in buf.items()}
    result["diagnostics"] = diagnostics
    return result


def normalize_probabilities(raw: np.ndarray) -> np.ndarray:
    clipped = np.clip(raw, 1e-6, 1.0)
    return clipped / clipped.sum(axis=1, keepdims=True)


def train_frozen_models(train: dict[str, Any], *, hazard_max: int, movement_max: int) -> tuple[HistGradientBoostingClassifier, list[HistGradientBoostingRegressor], dict[str, int]]:
    rng = np.random.default_rng(RANDOM_SEED)
    X, y_move = train["X"], train["y_move"]
    if len(X) > hazard_max:
        idx = np.sort(rng.choice(len(X), size=hazard_max, replace=False))
        hazard_x, hazard_y = X[idx], y_move[idx]
    else:
        hazard_x, hazard_y = X, y_move
    hazard = HistGradientBoostingClassifier(
        max_iter=120, learning_rate=0.08, max_leaf_nodes=31,
        l2_regularization=1.0, random_state=RANDOM_SEED,
    )
    hazard.fit(hazard_x, hazard_y)

    mover_idx_all = np.flatnonzero(y_move == 1)
    if len(mover_idx_all) > movement_max:
        mover_idx = np.sort(rng.choice(mover_idx_all, size=movement_max, replace=False))
    else:
        mover_idx = mover_idx_all
    movement_x = X[mover_idx]
    movement_y = train["actual_delta"][mover_idx]
    movement_models: list[HistGradientBoostingRegressor] = []
    for outcome_idx in range(3):
        model = HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.08, max_leaf_nodes=31,
            l2_regularization=1.0, random_state=RANDOM_SEED,
        )
        model.fit(movement_x, movement_y[:, outcome_idx])
        movement_models.append(model)
    return hazard, movement_models, {
        "hazard_training_states": int(len(hazard_x)),
        "conditional_movement_training_states": int(len(movement_x)),
    }


def predict_conditional_delta(models: list[HistGradientBoostingRegressor], X: np.ndarray, current: np.ndarray) -> np.ndarray:
    raw_delta = np.column_stack([model.predict(X) for model in models])
    predicted_next = normalize_probabilities(current + raw_delta)
    return predicted_next - current


def build_residual_frame(
    split: str,
    data: dict[str, Any],
    hazard: HistGradientBoostingClassifier,
    movement_models: list[HistGradientBoostingRegressor],
) -> pd.DataFrame:
    hazard_p = hazard.predict_proba(data["X"])[:, 1].astype(np.float64)
    conditional_delta = predict_conditional_delta(movement_models, data["X"], data["current"].astype(np.float64))
    actual_delta = data["actual_delta"].astype(np.float64)
    y_move = data["y_move"].astype(np.int8)
    expected_unconditional = hazard_p[:, None] * conditional_delta
    action_residual = actual_delta - expected_unconditional
    conditional_residual = actual_delta - conditional_delta
    conditional_residual[y_move == 0] = np.nan

    frame = pd.DataFrame({
        "match_id": data["match_id"],
        "split": split,
        "book_slot": [f"b{int(book)}" for book in data["book"]],
        "bookmaker_name": [BOOKMAKER_NAMES[int(book)] for book in data["book"]],
        "hours_before_kickoff": data["hours"].astype(np.int16),
        "actual_move": y_move,
        "predicted_move_probability": hazard_p,
        "move_surprise_signed": y_move.astype(np.float64) - hazard_p,
        "no_move_surprise": np.where(y_move == 0, hazard_p, 0.0),
        "unexpected_move_surprise": np.where(y_move == 1, 1.0 - hazard_p, 0.0),
    })
    for idx, outcome in enumerate(OUTCOMES):
        frame[f"target_current_{outcome}_p"] = data["current"][:, idx]
        frame[f"market_consensus_{outcome}_p"] = data["consensus"][:, idx]
        frame[f"actual_delta_{outcome}"] = actual_delta[:, idx]
        frame[f"predicted_conditional_delta_{outcome}"] = conditional_delta[:, idx]
        frame[f"conditional_residual_{outcome}"] = conditional_residual[:, idx]
        frame[f"expected_unconditional_delta_{outcome}"] = expected_unconditional[:, idx]
        frame[f"action_residual_{outcome}"] = action_residual[:, idx]

    frame["conditional_residual_l2"] = np.where(
        y_move == 1,
        np.linalg.norm(np.nan_to_num(conditional_residual, nan=0.0), axis=1),
        np.nan,
    )
    frame["action_residual_l2"] = np.linalg.norm(action_residual, axis=1)
    frame["consensus_gap_l2"] = np.linalg.norm(data["consensus"].astype(np.float64) - data["current"].astype(np.float64), axis=1)
    return add_sequential_features(frame)


def add_sequential_features(frame: pd.DataFrame) -> pd.DataFrame:
    # Chronological pre-match order: 48h -> 24h -> 12h -> 6h -> 3h -> 1h.
    order = {48: 0, 24: 1, 12: 2, 6: 3, 3: 4, 1: 5}
    out = frame.copy()
    out["_order"] = out["hours_before_kickoff"].map(order).astype(int)
    out.sort_values(["match_id", "book_slot", "_order"], inplace=True, kind="mergesort")
    group = out.groupby(["match_id", "book_slot"], sort=False, group_keys=False)

    out["prior_residual_cutoffs"] = group.cumcount()
    for source, target in (
        ("move_surprise_signed", "prior_move_surprise_mean"),
        ("action_residual_l2", "prior_action_residual_l2_mean"),
    ):
        cumulative = group[source].cumsum() - out[source]
        counts = out["prior_residual_cutoffs"].replace(0, np.nan)
        out[target] = cumulative / counts
    abs_surprise = out["move_surprise_signed"].abs()
    abs_cumsum = abs_surprise.groupby([out["match_id"], out["book_slot"]], sort=False).cumsum() - abs_surprise
    out["prior_abs_move_surprise_mean"] = abs_cumsum / out["prior_residual_cutoffs"].replace(0, np.nan)

    for outcome in OUTCOMES:
        source = f"action_residual_{outcome}"
        out[f"prior_action_residual_{outcome}_sum"] = group[source].cumsum() - out[source]

    out["prior_abnormality_mean"] = (
        out["prior_abs_move_surprise_mean"].fillna(0.0)
        + out["prior_action_residual_l2_mean"].fillna(0.0)
    )
    out.drop(columns=["_order"], inplace=True)
    return out


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_frame(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, compression="gzip")
    return {"path": str(path), "rows": int(len(frame)), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate outcome-blind abnormal-action residuals from frozen normal-bookmaker architectures.")
    parser.add_argument("--output-root", default="artifacts/abnormal-action-residuals")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "raw" / "dataset.zip"
    extracted = root / "extracted"
    archive_meta = download(DOWNLOAD_URL, archive)
    paths = extract_required(archive, extracted)
    datasets = build_all_state_records([paths[name] for name in SERIES_FILES], chunksize=args.chunksize)
    diagnostics = datasets.pop("diagnostics")
    hazard, movement_models, training_counts = train_frozen_models(
        datasets["train"], hazard_max=args.hazard_max_train, movement_max=args.movement_max_train
    )

    outputs: dict[str, Any] = {}
    residual_profiles: dict[str, Any] = {}
    for split in ("validation", "test"):
        frame = build_residual_frame(split, datasets[split], hazard, movement_models)
        path = root / f"residuals_{split}.csv.gz"
        outputs[split] = write_frame(frame, path)
        residual_profiles[split] = {
            "rows": int(len(frame)),
            "unique_matches": int(frame["match_id"].nunique()),
            "move_rate": float(frame["actual_move"].mean()),
            "mean_predicted_move_probability": float(frame["predicted_move_probability"].mean()),
            "mean_abs_move_surprise": float(frame["move_surprise_signed"].abs().mean()),
            "mean_action_residual_l2": float(frame["action_residual_l2"].mean()),
            "missing_conditional_residual_l2": int(frame["conditional_residual_l2"].isna().sum()),
            "rows_by_book": {str(k): int(v) for k, v in frame["book_slot"].value_counts().sort_index().items()},
            "rows_by_cutoff": {str(k): int(v) for k, v in frame["hours_before_kickoff"].value_counts().sort_index().items()},
        }

    manifest = {
        "source": "Beat The Bookie hourly tensor",
        "outcome_blind": True,
        "forbidden_source_fields": ["score_home", "score_away", "match result/outcome labels"],
        "model_policy": {
            "hazard": "Experiment 002 fixed HistGradientBoostingClassifier architecture",
            "conditional_movement": "Experiment 003 fixed three-HistGradientBoostingRegressor architecture",
            "training_only": "models fit only on chronological train split; residuals emitted only for validation/test",
        },
        "training_counts": training_counts,
        "diagnostics": diagnostics,
        "outputs": outputs,
        "profiles": residual_profiles,
        "residual_definitions": {
            "move_surprise_signed": "actual_move - predicted_move_probability",
            "no_move_surprise": "predicted_move_probability when no move else 0",
            "unexpected_move_surprise": "1-predicted_move_probability when move else 0",
            "conditional_residual": "actual_delta - predicted_conditional_delta when move",
            "action_residual": "actual_delta - p(move)*predicted_conditional_delta",
            "sequential_features": "computed only from earlier frozen cutoffs for same match/book",
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"training_counts": training_counts, "profiles": residual_profiles, "outputs": outputs}, indent=2))


if __name__ == "__main__":
    main()
