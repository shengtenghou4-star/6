from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np

import experiment_008_named_book_clv as exp8
import experiment_011_closing_line_residual as exp11
import generate_abnormal_action_residuals as residual_gen
from experiment_002_move_hazard import (
    DOWNLOAD_URL,
    SELECTED_BOOKS,
    SERIES_FILES,
    download,
    extract_required,
)
from marketlab.action_shadow_schema import (
    ACTION_RESIDUAL_FEATURES,
    CLOSING_ACTION_FEATURES,
    CLOSING_RAW_FEATURES,
    MODEL_FILES,
    NORMAL_FEATURES,
    OUTCOMES,
    sha256,
)


BOOK_ONEHOT_WIDTH = len(SELECTED_BOOKS)


def generic_data(data: dict[str, Any]) -> dict[str, Any]:
    if data["X"].shape[1] != len(NORMAL_FEATURES) + BOOK_ONEHOT_WIDTH:
        raise ValueError(
            f"unexpected historical feature width: {data['X'].shape[1]}"
        )
    output = dict(data)
    output["X"] = data["X"][:, :-BOOK_ONEHOT_WIDTH]
    return output


def dump_model(model: Any, directory: Path, name: str) -> dict[str, Any]:
    path = directory / f"{name}.joblib"
    joblib.dump(model, path, compress=3)
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "class": f"{type(model).__module__}.{type(model).__name__}",
        "parameters": model.get_params(deep=False),
    }


def fit_closing_models(
    validation,
    columns: list[str],
) -> tuple[Any, list[Any], dict[str, int]]:
    hazard = exp8.fixed_classifier()
    hazard.fit(validation[columns], validation["future_move"])
    movers = validation[validation["future_move"] == 1]
    if movers.empty:
        raise RuntimeError("no validation closing movers")
    movement_models = []
    for target in exp8.TARGET_DELTA_COLUMNS:
        model = exp8.fixed_regressor()
        model.fit(movers[columns], movers[target])
        movement_models.append(model)
    return hazard, movement_models, {
        "hazard_rows": int(len(validation)),
        "conditional_delta_rows": int(len(movers)),
        "matches": int(validation["match_id"].nunique()),
        "books": int(validation["book_slot"].nunique()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the frozen generic action-residual shadow-scoring model bundle."
    )
    parser.add_argument("--output-root", default="artifacts/generic-action-shadow-bundle")
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--hazard-max-train", type=int, default=500000)
    parser.add_argument("--movement-max-train", type=int, default=400000)
    args = parser.parse_args()

    root = Path(args.output_root)
    bundle = root / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    progress_path = root / "progress.json"
    failure_path = root / "failure.json"

    def progress(stage: str, **extra: Any) -> None:
        progress_path.write_text(
            json.dumps({"stage": stage, **extra}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    try:
        progress("acquiring_historical_source")
        archive = root / "raw" / "dataset.zip"
        extracted = root / "extracted"
        archive_meta = download(DOWNLOAD_URL, archive)
        paths = extract_required(archive, extracted)
        source_paths = [paths[name] for name in SERIES_FILES]

        progress("building_generic_normal_states")
        datasets = residual_gen.build_all_state_records(
            source_paths,
            chunksize=args.chunksize,
        )
        diagnostics = datasets.pop("diagnostics")
        generic = {
            split: generic_data(datasets[split])
            for split in ("train", "validation", "test")
        }

        progress("training_generic_normal_models")
        normal_hazard, normal_delta_models, normal_counts = residual_gen.train_frozen_models(
            generic["train"],
            hazard_max=args.hazard_max_train,
            movement_max=args.movement_max_train,
        )

        progress("generating_outcome_blind_action_residuals")
        residual_frames = {
            split: residual_gen.build_residual_frame(
                split,
                generic[split],
                normal_hazard,
                normal_delta_models,
            )
            for split in ("validation", "test")
        }
        x_frames = {}
        raw_x_columns: list[str] | None = None
        for split in ("validation", "test"):
            x_frames[split], columns = exp8.x_frame(generic[split])
            if raw_x_columns is None:
                raw_x_columns = columns
            elif columns != raw_x_columns:
                raise RuntimeError("validation/test generic X schemas differ")
        assert raw_x_columns is not None
        if len(raw_x_columns) != len(NORMAL_FEATURES):
            raise RuntimeError("generic historical feature order does not match shadow schema")

        progress("extracting_same_book_closing_targets")
        closing_prices, closing_profile = exp11.build_closing_prices(
            source_paths,
            [residual_frames["validation"], residual_frames["test"]],
            chunksize=args.chunksize,
        )
        validation, baseline_columns, _ = exp8.model_frame(
            residual_frames["validation"],
            x_frames["validation"],
            closing_prices,
            raw_x_columns,
        )
        test, baseline_test, _ = exp8.model_frame(
            residual_frames["test"],
            x_frames["test"],
            closing_prices,
            raw_x_columns,
        )
        if baseline_columns != baseline_test:
            raise RuntimeError("validation/test closing feature schemas differ")
        if len(baseline_columns) != len(CLOSING_RAW_FEATURES):
            raise RuntimeError("generic closing raw feature order does not match shadow schema")
        action_columns = baseline_columns + list(ACTION_RESIDUAL_FEATURES)
        if len(action_columns) != len(CLOSING_ACTION_FEATURES):
            raise RuntimeError("action closing feature order does not match shadow schema")
        for column in ACTION_RESIDUAL_FEATURES:
            if column not in validation.columns or column not in test.columns:
                raise ValueError(f"missing action residual field: {column}")

        progress("training_generic_closing_models")
        raw_hazard, raw_delta_models, raw_counts = fit_closing_models(
            validation,
            baseline_columns,
        )
        action_hazard, action_delta_models, action_counts = fit_closing_models(
            validation,
            action_columns,
        )

        progress("serializing_bundle")
        models = {
            "normal_hazard": normal_hazard,
            **{
                f"normal_delta_{outcome}": normal_delta_models[index]
                for index, outcome in enumerate(OUTCOMES)
            },
            "closing_raw_hazard": raw_hazard,
            **{
                f"closing_raw_delta_{outcome}": raw_delta_models[index]
                for index, outcome in enumerate(OUTCOMES)
            },
            "closing_action_hazard": action_hazard,
            **{
                f"closing_action_delta_{outcome}": action_delta_models[index]
                for index, outcome in enumerate(OUTCOMES)
            },
        }
        if set(models) != set(MODEL_FILES):
            raise RuntimeError("serialized model set does not match schema")
        model_files = {
            name: dump_model(model, bundle, name)
            for name, model in models.items()
        }

        smoke = {
            "normal_move_probability_finite": bool(
                np.isfinite(normal_hazard.predict_proba(generic["test"]["X"][:1024])[:, 1]).all()
            ),
            "normal_delta_predictions_finite": bool(
                all(
                    np.isfinite(model.predict(generic["test"]["X"][:1024])).all()
                    for model in normal_delta_models
                )
            ),
            "raw_closing_predictions_finite": bool(
                np.isfinite(raw_hazard.predict_proba(test[baseline_columns].iloc[:1024])[:, 1]).all()
            ),
            "action_closing_predictions_finite": bool(
                np.isfinite(action_hazard.predict_proba(test[action_columns].iloc[:1024])[:, 1]).all()
            ),
        }
        if not all(smoke.values()):
            raise RuntimeError(f"bundle smoke check failed: {smoke}")

        bundle_id = f"generic-action-shadow-v1-{archive_meta['sha256'][:12]}"
        manifest = {
            "schema_version": 1,
            "bundle_id": bundle_id,
            "research_policy": {
                "research_only": True,
                "no_execution": True,
                "unvalidated_prospective_transfer": True,
                "match_outcomes_used": False,
                "profit_claim": False,
            },
            "source": {
                "name": "Beat The Bookie hourly 1X2 tensor",
                "download_url": DOWNLOAD_URL,
                "archive": archive_meta,
                "series_files": list(SERIES_FILES),
            },
            "chronological_policy": {
                "normal_models": "fit only on historical chronological train split",
                "closing_models": "fit only on historical chronological validation split",
                "test_usage": "finite-prediction smoke checks only; no tuning",
                "closing_target": "same bookmaker final valid tensor state at index 71",
            },
            "book_identity_policy": {
                "historical_book_onehot_width_removed": BOOK_ONEHOT_WIDTH,
                "bookmaker_identity_in_features": False,
                "training_books": int(len(SELECTED_BOOKS)),
            },
            "feature_order": {
                "normal_features": list(NORMAL_FEATURES),
                "closing_raw_features": list(CLOSING_RAW_FEATURES),
                "action_residual_features": list(ACTION_RESIDUAL_FEATURES),
                "closing_action_features": list(CLOSING_ACTION_FEATURES),
            },
            "residual_equations": {
                "conditional_residual": "actual_delta - predicted_conditional_delta when move; prospective scorer stores zero when no move",
                "action_residual": "actual_delta - predicted_move_probability * predicted_conditional_delta",
                "economic_use": "raw generic model proposes bookmaker/outcome identity; action model ranks that fixed identity",
            },
            "training_counts": {
                "normal": normal_counts,
                "closing_raw": raw_counts,
                "closing_action": action_counts,
            },
            "normal_state_diagnostics": diagnostics,
            "closing_price_profile": closing_profile,
            "model_files": model_files,
            "smoke_checks": smoke,
        }
        manifest_path = bundle / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        result = {
            "status": "completed",
            "bundle_id": bundle_id,
            "bundle_manifest": str(manifest_path),
            "bundle_manifest_sha256": sha256(manifest_path),
            "model_files": len(model_files),
            "research_only": True,
        }
        (root / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        failure_path.unlink(missing_ok=True)
        progress_path.unlink(missing_ok=True)
    except Exception as exc:
        failure_path.write_text(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "progress": json.loads(progress_path.read_text(encoding="utf-8"))
                    if progress_path.exists()
                    else None,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
