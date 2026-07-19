from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_methods_note import validate_methods_note


def test_methods_note_is_complete_and_grounded() -> None:
    report = validate_methods_note(
        ROOT,
        ROOT / "paper" / "methods_claim_registry.json",
        ROOT / "paper" / "methods_note.md",
    )
    assert report["status"] == "passed"
    assert report["claims_checked"] == 7
    assert report["sources_checked"] == 7
    assert report["manuscript_words"] >= 1800


def test_methods_note_preserves_claim_boundaries() -> None:
    registry = json.loads(
        (ROOT / "paper" / "methods_claim_registry.json").read_text(encoding="utf-8")
    )
    prohibited = set(registry["prohibited_claims"])
    assert "stable realized profit" in prohibited
    assert "validated cross-domain empirical transfer" in prohibited
    assert "operational candidate status" in prohibited
