# Canonical-timing matched-budget cohort evaluation

Status: **frozen before production activation and before campaign outcomes mature**.

## Scope

This evaluator is exclusively for the separately activated `canonical_cutoff_coverage_normalized_v1` challenger. It cannot read the original v2 or support-repaired candidate ledgers as substitutes and cannot overwrite either existing final evaluation.

## Frozen boundaries

- adapter activation: `2026-07-19T15:00:00Z`;
- campaign end: `2026-07-26T06:30:00Z`;
- latest eligible collection time: `2026-07-26T03:15:00Z`, enforced through a minimum 3.25-hour collection lead;
- evaluation window: `2026-07-26T07:30:00Z` through `2026-07-27T07:30:00Z`;
- cutoffs: T-48, T-24, T-12 and T-6;
- selection fraction: exact `floor(n × 0.05)` within each cutoff for both policies.

The raw policy selects positive raw-score candidates. The residual policy selects positive action-rank candidates. Candidate ledgers are completely written and hashed before the closing-target file is read.

## Frozen evidence gates

The result is decision-eligible only when the matured cohort contains at least:

- 300 candidate rows;
- 75 unique events;
- 15 selected rows per policy;
- three cutoffs with at least 40 candidate rows each.

Promotion additionally requires:

- residual log-CLV event-bootstrap lower 95% bound above zero;
- paired residual-minus-raw log-CLV lower 95% bound above zero;
- positive residual fair-probability CLV;
- positive residual lift in at least three of four cutoffs;
- no bookmaker supplies more than 50% of positive residual contribution.

Bootstrap uses 4,000 event-cluster replicates with seed `20260727`.

## Fail-closed validation

The evaluator rejects:

- missing or mixed adapter IDs;
- mixed or incorrect activation boundaries;
- false research-only, unvalidated-transfer or no-execution flags;
- premature execution before campaign end;
- duplicate or inexact same-book closing joins;
- any attempt to replace existing prospective evaluations.

Match outcomes are never read. The evaluator measures same-book closing-price transfer, not realized betting profit.
