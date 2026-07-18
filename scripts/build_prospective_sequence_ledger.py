from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.prospective_sequences import materialize_sequence_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe quote, transition and closing-target ledgers from immutable odds snapshots."
    )
    parser.add_argument("--snapshots-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--market", default="h2h")
    parser.add_argument("--minimum-other-books", type=int, default=3)
    args = parser.parse_args()
    manifest = materialize_sequence_artifacts(
        snapshots_root=Path(args.snapshots_root),
        output_root=Path(args.output_root),
        market_key=args.market,
        minimum_other_books=args.minimum_other_books,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
