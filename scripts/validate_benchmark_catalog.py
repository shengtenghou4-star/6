from __future__ import annotations

import argparse
import json
from pathlib import Path

TIERS = {
    "implemented": 0,
    "executed": 1,
    "replicated_historical": 2,
    "validated_prospective": 3,
    "operational_candidate": 4,
}


def validate_catalog(repo_root: Path, catalog_path: Path) -> dict[str, object]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    profile_ids: set[str] = set()
    profiles = catalog.get("profiles", [])

    if catalog.get("schema_version") != 1:
        failures.append("unsupported_schema_version")
    if not profiles:
        failures.append("catalog_has_no_profiles")

    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        if not profile_id:
            failures.append("profile_without_id")
            continue
        if profile_id in profile_ids:
            failures.append(f"duplicate_profile:{profile_id}")
        profile_ids.add(profile_id)

        tier = profile.get("maximum_supported_tier")
        if tier not in TIERS:
            failures.append(f"invalid_tier:{profile_id}:{tier}")

        for field in ("specification", "result"):
            value = str(profile.get(field, ""))
            path = (repo_root / value).resolve()
            if repo_root.resolve() not in path.parents or not path.is_file():
                failures.append(f"missing_path:{profile_id}:{field}:{value}")

        submission = str(profile.get("submission", ""))
        if submission != "generated_by_workflow":
            path = (repo_root / submission).resolve()
            if repo_root.resolve() not in path.parents or not path.is_file():
                failures.append(f"missing_submission:{profile_id}:{submission}")

        if profile.get("prospective_transfer_validated") is True and TIERS.get(tier, -1) < 3:
            failures.append(f"prospective_flag_exceeds_tier:{profile_id}")
        if profile.get("economic_execution_validated") is True and TIERS.get(tier, -1) < 4:
            failures.append(f"execution_flag_exceeds_tier:{profile_id}")
        if profile.get("kind") == "simulation_only" and TIERS.get(tier, -1) > 1:
            failures.append(f"simulation_profile_overpromoted:{profile_id}")

    required = {
        "football-1x2-multi-book-v1",
        "synthetic-multi-agent-pricing-v1",
    }
    missing = required - profile_ids
    for profile_id in sorted(missing):
        failures.append(f"required_profile_missing:{profile_id}")

    report: dict[str, object] = {
        "schema_version": 1,
        "status": "passed" if not failures else "failed",
        "profiles_checked": len(profiles),
        "profile_ids": sorted(profile_ids),
        "failures": failures,
    }
    if failures:
        raise RuntimeError(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--catalog", default="benchmark/catalog.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    report = validate_catalog(root, (root / args.catalog).resolve())
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output = (root / args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
