from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def pct(value: float, digits: int = 3) -> str:
    return f"{100.0 * value:.{digits}f}%"


def build_assets(registry: dict[str, Any], reference: dict[str, Any], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    task = reference["task_b"]
    distribution = reference["distribution"]
    economic = reference["economic_diagnostic"]

    rows = [
        (
            "Alignment placebo",
            f"{task['placebo_replicates']} replicates",
            f"p={task['placebo_upper_tail_p']:.5f}",
            "replicated historical mechanism",
        ),
        (
            "Dose response",
            f"slope={task['standardized_uplift_slope']:.6f}",
            f"95% CI [{task['cluster_ci_low']:.6f}, {task['cluster_ci_high']:.6f}]",
            "lower bound above zero",
        ),
        (
            "Distribution",
            f"{distribution['positive_agents']}/{distribution['total_agents']} agents; "
            f"{distribution['positive_instruments']}/{distribution['total_instruments']} instruments; "
            f"{distribution['positive_horizons']}/{distribution['total_horizons']} horizons",
            f"leave-one-agent min lower bound={distribution['leave_one_agent_out_min_ci_low']:.6f}",
            "broad historical support",
        ),
        (
            "Matched return",
            f"raw {pct(economic['raw_roi'])}; residual {pct(economic['residual_roi'])}",
            f"paired CI [{economic['paired_ci_low_per_opportunity']:.7f}, "
            f"{economic['paired_ci_high_per_opportunity']:.7f}] per opportunity",
            "uncertain economic conversion",
        ),
        (
            "Execution grid",
            f"{economic['positive_execution_cells']}/{economic['total_execution_cells']} positive incremental cells",
            f"validated={str(economic['execution_validated']).lower()}",
            "directional but not validated",
        ),
        (
            "Prospective transfer",
            reference["prospective_status"],
            "frozen future-only campaign",
            "pending",
        ),
    ]

    markdown = [
        "| Layer | Point result | Uncertainty / control | Status |",
        "|---|---|---|---|",
    ]
    for row in rows:
        markdown.append("| " + " | ".join(row) + " |")
    (output_root / "main-results-table.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )

    latex = [
        r"\begin{tabular}{p{0.17\linewidth}p{0.28\linewidth}p{0.30\linewidth}p{0.18\linewidth}}",
        r"\toprule",
        r"Layer & Point result & Uncertainty / control & Status \\",
        r"\midrule",
    ]
    for layer, point, control, status in rows:
        clean = [value.replace("%", r"\%").replace("_", r"\_") for value in (layer, point, control, status)]
        latex.append(" & ".join(clean) + r" \\")
    latex.extend([r"\bottomrule", r"\end{tabular}"])
    (output_root / "main-results-table.tex").write_text(
        "\n".join(latex) + "\n", encoding="utf-8"
    )

    with (output_root / "claim-matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("id", "evidence_level", "source", "claim"),
        )
        writer.writeheader()
        for claim in registry["claims"]:
            writer.writerow(
                {
                    "id": claim["id"],
                    "evidence_level": claim["evidence_level"],
                    "source": claim["source"],
                    "claim": claim["claim"],
                }
            )

    report = {
        "schema_version": 1,
        "status": "completed",
        "submission_id": reference["submission_id"],
        "claim_count": len(registry["claims"]),
        "table_rows": len(rows),
        "outputs": [
            "main-results-table.md",
            "main-results-table.tex",
            "claim-matrix.csv",
        ],
    }
    (output_root / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="paper/claim_evidence_registry.json")
    parser.add_argument("--reference", default="benchmark/reference_submission.json")
    parser.add_argument("--output-root", default="artifacts/paper-assets")
    args = parser.parse_args()

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    reference = json.loads(Path(args.reference).read_text(encoding="utf-8"))
    report = build_assets(registry, reference, Path(args.output_root))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
