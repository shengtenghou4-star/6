from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from marketlab.action_shadow import (
    build_shadow_feature_records,
    load_shadow_bundle,
    score_shadow_records,
    select_event_shadow_candidates,
    sha256,
)

LEDGER_DATETIMES = (
    "snapshot_ingested_at",
    "commence_time",
    "bookmaker_last_update",
    "market_last_update",
)
TRANSITION_DATETIMES = (
    "previous_snapshot_ingested_at",
    "snapshot_ingested_at",
    "commence_time",
)
EXPECTED_EMPTY_MESSAGES = (
    "no three-snapshot context/realization chains",
    "no eligible prospective shadow chains",
    "no chains in historically supported closing horizons",
)


def read_frame(path: Path, datetime_columns: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    for column in datetime_columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score outcome-blind prospective quote transitions with the generic action-residual shadow bundle."
    )
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--quote-ledger", required=True)
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--allow-no-supported-chains",
        action="store_true",
        help="Write an outcome-blind no-supported-chains manifest instead of failing when the accumulated campaign has not yet reached a valid three-snapshot supported horizon.",
    )
    args = parser.parse_args()

    bundle_root = Path(args.bundle_root)
    ledger_path = Path(args.quote_ledger)
    transitions_path = Path(args.transitions)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    bundle = load_shadow_bundle(bundle_root)
    ledger = read_frame(ledger_path, LEDGER_DATETIMES)
    transitions = read_frame(transitions_path, TRANSITION_DATETIMES)
    try:
        records, diagnostics = build_shadow_feature_records(
            ledger,
            transitions,
            strict=False,
        )
    except RuntimeError as exc:
        if not args.allow_no_supported_chains or not any(
            marker in str(exc) for marker in EXPECTED_EMPTY_MESSAGES
        ):
            raise
        manifest = {
            "schema_version": 1,
            "status": "no_supported_chains",
            "reason": str(exc),
            "bundle_id": bundle.bundle_id,
            "bundle_manifest_sha256": bundle.manifest_sha256,
            "inputs": {
                "quote_ledger": {
                    "path": str(ledger_path),
                    "sha256": sha256(ledger_path),
                    "rows": int(len(ledger)),
                },
                "transitions": {
                    "path": str(transitions_path),
                    "sha256": sha256(transitions_path),
                    "rows": int(len(transitions)),
                },
            },
            "outputs": {
                "per_book_scores": {"rows": 0},
                "event_candidates": {"rows": 0},
            },
            "policy": {
                "research_only": True,
                "no_execution": True,
                "unvalidated_prospective_transfer": True,
                "match_outcomes_used": False,
                "invalid_or_post_commence_chains_excluded": True,
            },
        }
        (output_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return

    scored = score_shadow_records(records, bundle)
    candidates = select_event_shadow_candidates(scored)

    per_book_path = output_root / "per-book-shadow-scores.csv.gz"
    candidate_path = output_root / "event-shadow-candidates.csv.gz"
    scored.to_csv(per_book_path, index=False, compression="gzip")
    candidates.to_csv(candidate_path, index=False, compression="gzip")

    manifest = {
        "schema_version": 1,
        "status": "scored",
        "bundle_id": bundle.bundle_id,
        "bundle_manifest_sha256": bundle.manifest_sha256,
        "inputs": {
            "quote_ledger": {
                "path": str(ledger_path),
                "sha256": sha256(ledger_path),
                "rows": int(len(ledger)),
            },
            "transitions": {
                "path": str(transitions_path),
                "sha256": sha256(transitions_path),
                "rows": int(len(transitions)),
            },
        },
        "chain_diagnostics": diagnostics,
        "outputs": {
            "per_book_scores": {
                "path": per_book_path.name,
                "sha256": sha256(per_book_path),
                "rows": int(len(scored)),
            },
            "event_candidates": {
                "path": candidate_path.name,
                "sha256": sha256(candidate_path),
                "rows": int(len(candidates)),
            },
        },
        "policy": {
            "research_only": True,
            "no_execution": True,
            "unvalidated_prospective_transfer": True,
            "match_outcomes_used": False,
            "invalid_or_post_commence_chains_excluded": True,
        },
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
