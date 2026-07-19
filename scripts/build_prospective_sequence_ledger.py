from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.prospective_sequence_states import discover_snapshot_directories
from marketlab.prospective_sequences import materialize_sequence_artifacts

EXPECTED_INSUFFICIENT_MESSAGES = (
    "at least two observations per quote are required",
    "no earlier observations before closing states",
    "no pre-commence quote states",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe quote, transition and closing-target ledgers from immutable odds snapshots."
    )
    parser.add_argument("--snapshots-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--market", default="h2h")
    parser.add_argument("--minimum-other-books", type=int, default=3)
    parser.add_argument(
        "--allow-insufficient-overlap",
        action="store_true",
        help="Write an outcome-blind insufficient-overlap manifest instead of failing when accumulated snapshots do not yet share enough event/bookmaker identities.",
    )
    args = parser.parse_args()
    snapshots_root = Path(args.snapshots_root)
    output_root = Path(args.output_root)
    try:
        manifest = materialize_sequence_artifacts(
            snapshots_root=snapshots_root,
            output_root=output_root,
            market_key=args.market,
            minimum_other_books=args.minimum_other_books,
        )
        manifest["status"] = "materialized"
        (output_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except RuntimeError as exc:
        if not args.allow_insufficient_overlap or not any(
            marker in str(exc) for marker in EXPECTED_INSUFFICIENT_MESSAGES
        ):
            raise
        directories = discover_snapshot_directories(snapshots_root)
        output_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "status": "insufficient_overlap",
            "reason": str(exc),
            "market_key": args.market,
            "minimum_other_books": args.minimum_other_books,
            "snapshots_root": str(snapshots_root),
            "snapshot_directories": [path.name for path in directories],
            "snapshot_count": len(directories),
            "outcome_blind": True,
            "forbidden_fields": ["home_score", "away_score", "result", "winner"],
        }
        (output_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
