from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from marketlab.prospective_shadow_evaluation import evaluate_prospective_shadow


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate untouched prospective closing CLV for the frozen action-residual ranker."
    )
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--closing-targets", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    closing_path = Path(args.closing_targets)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_csv(candidates_path, low_memory=False)
    closing = pd.read_csv(closing_path, low_memory=False)
    rows, report = evaluate_prospective_shadow(candidates, closing)

    ledger_path = output_root / "prospective-evaluation-ledger.csv.gz"
    result_path = output_root / "result.json"
    rows.to_csv(ledger_path, index=False, compression="gzip")
    result_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "inputs": {
            "event_shadow_candidates": {
                "path": str(candidates_path),
                "rows": int(len(candidates)),
                "sha256": sha256(candidates_path),
            },
            "closing_targets": {
                "path": str(closing_path),
                "rows": int(len(closing)),
                "sha256": sha256(closing_path),
            },
        },
        "outputs": {
            "evaluation_ledger": {
                "path": ledger_path.name,
                "rows": int(len(rows)),
                "sha256": sha256(ledger_path),
            },
            "result": {
                "path": result_path.name,
                "sha256": sha256(result_path),
            },
        },
        "policy": report["policy"],
        "bundle_id": report["bundle_id"],
        "bundle_manifest_sha256": report["bundle_manifest_sha256"],
        "outcome_blind": True,
        "profit_claim": False,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
