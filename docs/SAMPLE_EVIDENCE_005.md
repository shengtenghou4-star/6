# Sample Evidence 005 — Deterministic Football-Data Entity Spine

Validated on GitHub Actions against the full Football-Data seasonal archive.

## Verified output

- 240,014 valid match rows processed end-to-end
- 809 deterministic source-level team IDs
- 240,014 deterministic match IDs
- 0 parse/identity failures after explicit source-row filtering
- 0 duplicate deterministic match IDs
- 9 legacy non-match/footer rows rejected explicitly upstream, not silently lost
- 1 harmless normalized alias group observed: `M'Gladbach` / `M'gladbach`

## Identity rule

v0 intentionally uses deterministic normalized-name identity only. It does not perform fuzzy or cross-vendor auto-merges. Raw aliases and source provenance are preserved so later cross-source mappings remain reviewable and reversible.

## Evidence

Workflow: `Entity Spine v0`

Artifact digest: `sha256:a5853ce53159a9242f63ab5e8cad251b6fdad60c2770e2666c43c647f4e1cf56`

The source archive parser was also hardened so non-match annotation/footer rows are explicitly counted and rejected before bronze match ingestion.