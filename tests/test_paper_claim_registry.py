from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_paper_claims import validate_registry


def test_paper_claim_registry_matches_sources() -> None:
    report = validate_registry(
        ROOT,
        ROOT / "paper" / "claim_evidence_registry.json",
        ROOT / "paper" / "manuscript.md",
    )
    assert report["status"] == "passed"
    assert report["claims_checked"] == 10
    assert report["sources_checked"] >= 8


def test_registry_preserves_prohibited_claim_boundary() -> None:
    registry = json.loads(
        (ROOT / "paper" / "claim_evidence_registry.json").read_text(
            encoding="utf-8"
        )
    )
    prohibited = set(registry["prohibited_claims_until_new_evidence"])
    assert "stable realized profit" in prohibited
    assert "live execution readiness" in prohibited
    assert "prospective transfer validated" in prohibited
