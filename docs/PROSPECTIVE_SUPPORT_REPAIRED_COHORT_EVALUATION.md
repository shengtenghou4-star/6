# Prospective support-repaired campaign-cohort evaluation

Status: **frozen before repaired production evidence and campaign completion**.

This protocol evaluates the separately activated support-constrained coverage-normalized shadow. It does not modify, replace or reinterpret the original Phase 43 evaluation.

## Frozen identity and time boundaries

- adapter ID: `support_constrained_coverage_normalized_v1`;
- repaired candidate activation: `2026-07-19T12:00:00Z`;
- campaign end: `2026-07-26T06:30:00Z`;
- latest eligible candidate observation: `2026-07-26T03:15:00Z`;
- scheduled evaluation window: `2026-07-26T07:30:00Z` through `2026-07-27T07:30:00Z`.

Only immutable repaired event candidates generated under the production activation enter the cohort. Pull-request engineering-validation rows are excluded by their different activation timestamp and may never enter this evaluation.

## Required repaired evidence

Every candidate must carry one adapter ID, one production activation boundary and true values for:

- `support_repair_unvalidated_transfer`;
- `support_repair_research_only`;
- `support_repair_no_execution`;
- the original `research_only`, `no_execution` and `unvalidated_prospective_transfer` flags.

Mixed adapters, mixed activation boundaries or false evidence flags are hard failures.

## Matched 5% policies

Within the full matured repaired cohort at each T-48, T-24, T-12 and T-6 cutoff:

- raw reference: require positive repaired raw score and select `floor(n × 0.05)`;
- residual challenger: require positive repaired action-rank score and select `floor(n × 0.05)`;
- raw candidate bookmaker and outcome identity remain fixed for both policies;
- no nonpositive score may be used as backfill.

Both complete ledgers are written and SHA-256 hashed before the closing-target file is read.

Policy IDs:

- `raw_positive_top_5pct_support_repaired_cohort_v1`;
- `residual_positive_top_5pct_support_repaired_cohort_v1`.

## Exact closing attachment

Closing targets join exactly on:

`event_id × bookmaker_key × market_key × realized_snapshot_id`.

The same-book target must be later than the candidate observation and earlier than kickoff. Missing, duplicate, non-finite or chronologically invalid targets are hard failures; rows are not silently dropped.

No match result, score or settlement data is permitted.

## Frozen evidence gates

For direct comparability with Phase 43:

- at least 300 matured candidates;
- at least 75 unique events;
- at least 15 selections for each policy;
- at least three cutoffs with 40 or more candidates;
- both policies fill every exact quota from positive scores.

Promotion additionally requires:

- residual selected-trade log-CLV event-cluster bootstrap 95% lower bound above zero;
- residual-minus-raw opportunity log-CLV paired lower bound above zero;
- positive residual selected fair-probability CLV;
- positive incremental point lift in at least three of four cutoffs;
- no bookmaker contributes more than 50% of positive residual log-CLV.

Bootstrap settings are 4,000 event-cluster replicates with seed `20260727`. Insufficient repaired volume is recorded as insufficient evidence; thresholds are never weakened.

## Execution and immutability

The one-window workflow checks out the final `prospective-data` state, validates the repaired adapter identity, freezes and hashes policy ledgers, then attaches exact closing targets. Evidence is committed write-once under:

`data/evaluations/support-repaired-matched-budget-cohort-v1/`

A second attempt cannot overwrite the directory. This evaluation is outcome-blind, research-only and cannot establish realized profit, fills, limits or execution scale.