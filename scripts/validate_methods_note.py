from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_LEVELS = {
    "replicated_historical",
    "historical_diagnostic",
    "executed_outcome_blind_audit",
    "executed_synthetic_contract_test",
}


def validate_methods_note(
    repo_root: Path,
    registry_path: Path,
    manuscript_path: Path,
) -> dict[str, object]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    manuscript = manuscript_path.read_text(encoding="utf-8")
    claims = registry.get("claims", [])
    failures: list[str] = []
    sources: set[str] = set()
    seen: set[str] = set()

    if not claims:
        failures.append("missing_claims")

    for claim in claims:
        claim_id = str(claim.get("id", ""))
        if not claim_id:
            failures.append("claim_without_id")
            continue
        if claim_id in seen:
            failures.append(f"duplicate_claim:{claim_id}")
        seen.add(claim_id)

        if manuscript.count(f"[{claim_id}]") < 1:
            failures.append(f"marker_missing:{claim_id}")
        if claim.get("evidence_level") not in ALLOWED_LEVELS:
            failures.append(f"invalid_level:{claim_id}")

        source = str(claim.get("source", ""))
        source_path = (repo_root / source).resolve()
        if repo_root.resolve() not in source_path.parents:
            failures.append(f"source_outside_repo:{claim_id}")
            continue
        if not source_path.is_file():
            failures.append(f"source_missing:{claim_id}:{source}")
            continue
        sources.add(source)
        source_text = source_path.read_text(encoding="utf-8")
        for literal in claim.get("required_literals", []):
            if str(literal) not in source_text:
                failures.append(f"literal_missing:{claim_id}:{literal}")

    prohibited = registry.get("prohibited_claims", [])
    if len(prohibited) < 4:
        failures.append("prohibited_claim_boundary_incomplete")

    required_sections = (
        "## Abstract",
        "## 2. Six evidence layers",
        "## 3. Structure-preserving falsification",
        "## 6. Deployment support and parallel repair",
        "## 8. Machine-checkable claim governance",
        "## 12. Limitations",
        "## 13. Conclusion",
    )
    for section in required_sections:
        if section not in manuscript:
            failures.append(f"section_missing:{section}")

    report: dict[str, object] = {
        "schema_version": 1,
        "status": "passed" if not failures else "failed",
        "claims_checked": len(claims),
        "sources_checked": len(sources),
        "manuscript_words": len(manuscript.split()),
        "failures": failures,
    }
    if failures:
        raise RuntimeError(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry", default="paper/methods_claim_registry.json")
    parser.add_argument("--manuscript", default="paper/methods_note.md")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    report = validate_methods_note(
        root,
        (root / args.registry).resolve(),
        (root / args.manuscript).resolve(),
    )
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output = (root / args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
