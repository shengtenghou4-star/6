from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_benchmark_catalog import validate_catalog


def test_catalog_passes_and_contains_two_profiles() -> None:
    report = validate_catalog(ROOT, ROOT / "benchmark" / "catalog.json")
    assert report["status"] == "passed"
    assert report["profiles_checked"] == 2
    assert "football-1x2-multi-book-v1" in report["profile_ids"]
    assert "synthetic-multi-agent-pricing-v1" in report["profile_ids"]


def test_simulation_profile_cannot_claim_historical_replication(tmp_path: Path) -> None:
    catalog = json.loads((ROOT / "benchmark" / "catalog.json").read_text(encoding="utf-8"))
    payload = copy.deepcopy(catalog)
    synthetic = next(profile for profile in payload["profiles"] if profile["kind"] == "simulation_only")
    synthetic["maximum_supported_tier"] = "replicated_historical"
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        validate_catalog(ROOT, path)
    except RuntimeError as exc:
        assert "simulation_profile_overpromoted" in str(exc)
    else:
        raise AssertionError("simulation profile tier promotion should fail")
