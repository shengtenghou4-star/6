from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_paper_claims import validate_registry


def test_paper_claim_registry_matches_sources() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report = validate_registry(
        repo_root,
        repo_root / "paper" / "claim_evidence_registry.json",
        repo_root / "paper" / "manuscript.md",
    )
    assert report["status"] == "passed"
    assert report["claims_checked"] == 10
    assert report["sources_checked"] >= 8


def test_registry_preserves_prohibited_claim_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    registry = json.loads(
        (repo_root / "paper" / "claim_evidence_registry.json").read_text(
            encoding="utf-8"
        )
    )
    prohibited = set(registry["prohibited_claims_until_new_evidence"])
    assert "stable realized profit" in prohibited
    assert "live execution readiness" in prohibited
    assert "prospective transfer validated" in prohibited
