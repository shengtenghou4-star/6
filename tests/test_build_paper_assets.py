from __future__ import annotations

import json
from pathlib import Path

from scripts.build_paper_assets import build_assets


def test_build_paper_assets(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    registry = json.loads(
        (root / "paper" / "claim_evidence_registry.json").read_text(encoding="utf-8")
    )
    reference = json.loads(
        (root / "benchmark" / "reference_submission.json").read_text(encoding="utf-8")
    )
    report = build_assets(registry, reference, tmp_path)
    assert report["status"] == "completed"
    assert report["claim_count"] == 10
    markdown = (tmp_path / "main-results-table.md").read_text(encoding="utf-8")
    assert "4000 replicates" in markdown
    assert "0.004430" in markdown
    assert "60/64" in markdown
    assert "in_progress" in markdown
    latex = (tmp_path / "main-results-table.tex").read_text(encoding="utf-8")
    assert "\\begin{tabular}" in latex
    assert "raw -0.747\\%; residual 0.565\\%" in latex
