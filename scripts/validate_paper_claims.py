from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_LEVELS = {
    "implemented",
    "executed_infrastructure",
    "executed_outcome_blind_audit",
    "historical_diagnostic",
    "post_hoc_historical_diagnostic",
    "replicated_historical",
    "validated_prospective",
}


def validate_registry(repo_root: Path, registry_path: Path, manuscript_path: Path) -> dict[str, object]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    claims = registry.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("registry must contain a non-empty claims list")

    manuscript = manuscript_path.read_text(encoding="utf-8")
    seen: set[str] = set()
    checked_sources: set[str] = set()
    failures: list[str] = []

    for claim in claims:
        claim_id = str(claim.get("id", ""))
        if not claim_id:
            failures.append("claim_without_id")
            continue
        if claim_id in seen:
            failures.append(f"duplicate_claim_id:{claim_id}")
        seen.add(claim_id)

        level = claim.get("evidence_level")
        if level not in ALLOWED_LEVELS:
            failures.append(f"invalid_evidence_level:{claim_id}:{level}")

        marker = f"[{claim_id}]"
        if marker not in manuscript:
            failures.append(f"claim_missing_from_manuscript:{claim_id}")

        source = str(claim.get("source", ""))
        source_path = (repo_root / source).resolve()
        if repo_root.resolve() not in source_path.parents:
            failures.append(f"source_outside_repo:{claim_id}:{source}")
            continue
        if not source_path.is_file():
            failures.append(f"source_missing:{claim_id}:{source}")
            continue
        checked_sources.add(source)
        source_text = source_path.read_text(encoding="utf-8")
        for literal in claim.get("required_literals", []):
            if str(literal) not in source_text:
                failures.append(f"literal_missing:{claim_id}:{literal}")

    prohibited = registry.get("prohibited_claims_until_new_evidence", [])
    if not isinstance(prohibited, list) or not prohibited:
        failures.append("prohibited_claims_list_missing")

    report = {
        "schema_version": 1,
        "claims_checked": len(claims),
        "sources_checked": len(checked_sources),
        "manuscript": str(manuscript_path.relative_to(repo_root)),
        "registry": str(registry_path.relative_to(repo_root)),
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }
    if failures:
        raise RuntimeError(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry", default="paper/claim_evidence_registry.json")
    parser.add_argument("--manuscript", default="paper/manuscript.md")
    parser.add_argument("--output")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = validate_registry(
        repo_root,
        (repo_root / args.registry).resolve(),
        (repo_root / args.manuscript).resolve(),
    )
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output = (repo_root / args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
