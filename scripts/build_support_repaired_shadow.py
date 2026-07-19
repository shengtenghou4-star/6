from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from marketlab.action_shadow import (
    load_shadow_bundle,
    score_shadow_records,
    select_event_shadow_candidates,
)
from marketlab.action_shadow_schema import sha256
from marketlab.support_repaired_shadow import (
    SupportRepairPolicy,
    prepare_support_repaired_records,
)


def correlation(left: pd.Series, right: pd.Series, method: str) -> float | None:
    if len(left) < 2 or left.nunique() < 2 or right.nunique() < 2:
        return None
    value = left.corr(right, method=method)
    return float(value) if np.isfinite(value) else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an outcome-blind support-constrained coverage-normalized shadow."
    )
    parser.add_argument("--per-book-scores", required=True)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--activation-utc", required=True)
    parser.add_argument("--cutoff-tolerance-hours", type=float, default=1.75)
    parser.add_argument(
        "--adapter-id", default="support_constrained_coverage_normalized_v1"
    )
    args = parser.parse_args()

    source_path = Path(args.per_book_scores)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(source_path, low_memory=False)
    policy = SupportRepairPolicy(
        activation_utc=args.activation_utc,
        cutoff_tolerance_hours=args.cutoff_tolerance_hours,
        adapter_id=args.adapter_id,
    )
    prepared, diagnostics = prepare_support_repaired_records(source, policy)
    bundle = load_shadow_bundle(Path(args.bundle_root))

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "adapter_id": policy.adapter_id,
        "status": diagnostics["status"],
        "source": {
            "per_book_scores": {
                "path": str(source_path),
                "sha256": sha256(source_path),
                "rows": int(len(source)),
            },
            "bundle": {
                "bundle_id": bundle.bundle_id,
                "manifest_sha256": bundle.manifest_sha256,
            },
        },
        "diagnostics": diagnostics,
        "policy": {
            "research_only": True,
            "no_execution": True,
            "match_outcomes_used": False,
            "closing_targets_used": False,
            "original_v2_shadow_replaced": False,
            "parallel_unvalidated_transfer": True,
        },
        "outputs": {
            "per_book_scores": {"rows": 0},
            "event_candidates": {"rows": 0},
        },
    }
    if prepared.empty:
        (output_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return

    repaired = score_shadow_records(prepared, bundle)
    repaired["support_repair_unvalidated_transfer"] = True
    repaired["support_repair_research_only"] = True
    repaired["support_repair_no_execution"] = True
    candidates = select_event_shadow_candidates(repaired)
    candidates["support_repair_unvalidated_transfer"] = True
    candidates["support_repair_research_only"] = True
    candidates["support_repair_no_execution"] = True

    per_book_path = output_root / "support-repaired-per-book-scores.csv.gz"
    candidate_path = output_root / "support-repaired-event-candidates.csv.gz"
    repaired.to_csv(per_book_path, index=False, compression="gzip")
    candidates.to_csv(candidate_path, index=False, compression="gzip")

    manifest["status"] = "scored"
    manifest["diagnostics"]["repaired_event_candidates"] = int(len(candidates))
    manifest["diagnostics"]["repaired_candidate_events"] = int(
        candidates["event_id"].nunique()
    )
    manifest["diagnostics"]["score_change"] = {
        "raw_mean_absolute_change": float(
            np.mean(
                np.abs(
                    repaired["raw_candidate_score"].to_numpy(float)
                    - repaired["original_raw_candidate_score"].to_numpy(float)
                )
            )
        ),
        "action_mean_absolute_change": float(
            np.mean(
                np.abs(
                    repaired["action_rank_score_for_raw_candidate"].to_numpy(float)
                    - repaired[
                        "original_action_rank_score_for_raw_candidate"
                    ].to_numpy(float)
                )
            )
        ),
        "raw_pearson": correlation(
            repaired["original_raw_candidate_score"],
            repaired["raw_candidate_score"],
            "pearson",
        ),
        "raw_spearman": correlation(
            repaired["original_raw_candidate_score"],
            repaired["raw_candidate_score"],
            "spearman",
        ),
        "action_pearson": correlation(
            repaired["original_action_rank_score_for_raw_candidate"],
            repaired["action_rank_score_for_raw_candidate"],
            "pearson",
        ),
        "action_spearman": correlation(
            repaired["original_action_rank_score_for_raw_candidate"],
            repaired["action_rank_score_for_raw_candidate"],
            "spearman",
        ),
    }
    manifest["outputs"] = {
        "per_book_scores": {
            "path": per_book_path.name,
            "sha256": sha256(per_book_path),
            "rows": int(len(repaired)),
        },
        "event_candidates": {
            "path": candidate_path.name,
            "sha256": sha256(candidate_path),
            "rows": int(len(candidates)),
        },
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
