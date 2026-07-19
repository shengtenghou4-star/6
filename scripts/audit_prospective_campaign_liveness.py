from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.prospective_campaign_liveness import audit_campaign_liveness


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def optional_json(path_value: str | None) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    return read_json(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit freshness and hash alignment of prospective campaign state."
    )
    parser.add_argument("--sequence-manifest", required=True)
    parser.add_argument("--shadow-manifest", required=True)
    parser.add_argument("--support-repaired-manifest")
    parser.add_argument("--canonical-timing-manifest")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--now-utc")
    parser.add_argument("--campaign-start-utc", required=True)
    parser.add_argument("--campaign-end-utc", required=True)
    parser.add_argument("--stale-after-hours", type=float, default=4.5)
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    now_utc = args.now_utc or datetime.now(UTC).isoformat()
    result = audit_campaign_liveness(
        read_json(Path(args.sequence_manifest)),
        read_json(Path(args.shadow_manifest)),
        now_utc=now_utc,
        campaign_start_utc=args.campaign_start_utc,
        campaign_end_utc=args.campaign_end_utc,
        stale_after_hours=args.stale_after_hours,
        support_repaired=optional_json(args.support_repaired_manifest),
        canonical_timing=optional_json(args.canonical_timing_manifest),
    )
    result["inputs"] = {
        "sequence_manifest": args.sequence_manifest,
        "shadow_manifest": args.shadow_manifest,
        "support_repaired_manifest": args.support_repaired_manifest,
        "canonical_timing_manifest": args.canonical_timing_manifest,
    }
    (output_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_root / "status.txt").write_text(
        str(result["status"]) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
