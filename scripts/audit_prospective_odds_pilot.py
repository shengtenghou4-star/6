from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from marketlab.prospective_pilot_audit import audit_snapshot_root


def markdown_report(report: dict) -> str:
    decisions = report["decisions"]
    coverage = report["coverage"]
    quota = report["quota"]
    lines = [
        "# Authenticated prospective odds pilot audit",
        "",
        f"- Snapshot: `{report['snapshot']['snapshot_id']}`",
        f"- Sport: `{report['snapshot']['sport']}`",
        f"- Events: `{coverage['events']}`",
        f"- Complete H/D/A bookmaker states: `{coverage['complete_h2h_quote_states']}`",
        f"- Minimum complete books per event: `{coverage['complete_books_per_event_min']}`",
        f"- Median complete books per event: `{coverage['complete_books_per_event_median']}`",
        f"- Request cost header: `{quota['last']}`",
        f"- Quota remaining: `{quota['remaining']}`",
        "",
        "## Decisions",
        "",
        f"- Authenticated source connected: **{decisions['authenticated_source_connected']}**",
        f"- Suitable for repeated snapshot pilot: **{decisions['suitable_for_repeated_snapshot_pilot']}**",
        f"- Suitable for untouched repricing/CLV now: **{decisions['suitable_for_untouched_repricing_clv_now']}**",
        "",
    ]
    if report["blocking_reasons"]:
        lines.extend(
            [
                "## Blocking checks",
                "",
                *[f"- `{reason}`" for reason in report["blocking_reasons"]],
                "",
            ]
        )
    lines.extend(
        [
            "## Evidence boundary",
            "",
            "A single snapshot can verify authentication, quota cost, bookmaker coverage, timestamps and secret safety. It cannot create quote transitions, closing targets, alpha or profit evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit the first authenticated immutable odds snapshot."
    )
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report = audit_snapshot_root(
        Path(args.snapshot_root),
        secret_value=os.environ.get("THE_ODDS_API_KEY"),
    )
    (output_root / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "audit.md").write_text(
        markdown_report(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "snapshot_id": report["snapshot"]["snapshot_id"],
                "authenticated_source_connected": report["decisions"][
                    "authenticated_source_connected"
                ],
                "suitable_for_repeated_snapshot_pilot": report["decisions"][
                    "suitable_for_repeated_snapshot_pilot"
                ],
                "blocking_reasons": report["blocking_reasons"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
