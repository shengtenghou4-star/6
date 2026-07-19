# Prospective matched-budget campaign-cohort evaluation

Status: **frozen before campaign completion**.

This protocol evaluates whether the residual ranker improves untouched same-book closing-price quality over a matched raw-score reference. It is outcome-blind and cannot establish realized profit, fills, account limits or scale.

## Frozen time boundaries

- candidate activation: `2026-07-19T11:00:00Z`;
- campaign end: `2026-07-26T06:30:00Z`;
- latest eligible candidate observation: `2026-07-26T03:15:00Z`;
- scheduled evaluation window: `2026-07-26T07:00:00Z` through `2026-07-27T07:00:00Z`.

The 3 hour 15 minute tail exclusion guarantees at least one scheduled collection opportunity after every eligible observation. Only events commencing by campaign end enter the cohort. Invalid or post-commence candidate chronology is a hard failure.

## Frozen cohort

The source is the cumulative prospectively scored `event-shadow-candidates.csv.gz` ledger. The cohort keeps every candidate that:

1. was ingested at or after activation;
2. was ingested no later than the frozen latest-observation boundary;
3. belongs to an event commencing no later than campaign end;
4. lies in a historically supported T-48, T-24, T-12 or T-6 bucket;
5. retains the research-only, no-execution and unvalidated-transfer flags;
6. uses the single frozen generic action-shadow bundle.

No bookmaker, candidate outcome or supported cutoff may be deleted after inspection.

## Matched 5% policies

Selection is performed across the **full matured campaign cohort within each cutoff**, rather than within tiny per-sport snapshots.

For every cutoff with `n` candidates:

- raw reference: require `raw_candidate_score > 0`, rank by raw score and select `floor(n × 0.05)`;
- residual challenger: require `action_rank_score_for_raw_candidate > 0`, rank by action score and select `floor(n × 0.05)`.

Ties are broken deterministically by event ID, realized snapshot ID and bookmaker key. If either policy lacks enough positive-score candidates to fill a quota, the shortfall is retained and the exact-capacity evidence gate fails. Nonpositive candidates are never used as backfill.

Policy IDs:

- `raw_positive_top_5pct_campaign_cohort_v1`;
- `residual_positive_top_5pct_campaign_cohort_v1`.

Both full policy ledgers are written and SHA-256 hashed before the closing-target file is read. Later evaluation re-derives every selected identity from the frozen scores and rejects changed flags, candidate identities or policy IDs.

## Closing target attachment

Each cohort row must have one exact target matching:

`event_id × bookmaker_key × market_key × realized_snapshot_id`.

The target snapshot must be later than the candidate observation and earlier than kickoff. Candidate and target kickoff timestamps must agree. Missing, duplicate, non-finite or chronologically invalid targets cause a hard failure; rows are not silently dropped.

The candidate outcome remains the raw model's prospectively fixed bookmaker/outcome identity. Closing log-odds CLV and fair-probability CLV are read only for that outcome.

## Frozen evidence gates

Minimum volume:

- at least 300 matured candidate opportunities;
- at least 75 unique events;
- at least 15 selections for each policy;
- at least three cutoffs with 40 or more candidates;
- both policies fill every exact 5% quota from positive-score candidates.

Promotion additionally requires all of the following:

- residual selected-trade log-CLV event-cluster bootstrap 95% lower bound above zero;
- residual-minus-raw opportunity log-CLV paired event-cluster bootstrap 95% lower bound above zero;
- positive residual selected fair-probability CLV;
- positive incremental point lift in at least three of four cutoffs;
- no single bookmaker contributes more than 50% of positive residual log-CLV.

Bootstrap settings are 4,000 event-cluster replicates with seed `20260726`. Thresholds are not changed when the result is known. Failure to meet volume is recorded as insufficient evidence, not repaired by lowering the gates.

## Execution

The one-window scheduled workflow verifies the frozen evaluator source hashes, checks out the cumulative `prospective-data` state, creates immutable freeze evidence, evaluates exact closing targets and commits the result under:

`data/evaluations/matched-budget-cohort-v1/`

The directory is write-once. A second attempt cannot overwrite it. Match results and settlement data are forbidden throughout.
