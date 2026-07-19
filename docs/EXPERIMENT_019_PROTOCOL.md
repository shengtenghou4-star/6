# Experiment 019 Protocol — Temporal stability and residual-uplift placebo audit

Status: **frozen before the repository workflow reads the Experiment 017 artifact**.

## Question

Does the matched-budget residual ranker's historical advantage depend on the residual uplift being attached to the correct match, and is the advantage stable to calendar blocking?

## Frozen source

- Experiment 017 artifact ID: `8439484047`;
- artifact ZIP SHA-256: `15bc79ca3011a65f8347d2e0569b93268d76343a85cbd1f3c7e9ede245ad2554`;
- fixed raw and residual settled ledgers;
- 59,816 opportunities and 2,988 selections per policy;
- raw model candidate bookmaker/outcome identity remains unchanged.

No model is refit. No bookmaker, outcome, cutoff or calendar block may be deleted.

## Residual-uplift placebo

For 4,000 fixed-seed replicates:

1. preserve every baseline score and candidate identity;
2. sort candidates chronologically within bookmaker × cutoff;
3. circularly shift `residual_uplift` by a nonzero random offset within each group;
4. reconstruct placebo score as `baseline_score + shifted_residual_uplift`;
5. require positive placebo score and reselect the exact historical 5% capacity within each cutoff;
6. compare placebo closing log-CLV and realized return with the observed residual policy.

This null preserves baseline information, uplift marginal distributions, bookmaker/cutoff structure and local temporal ordering while breaking the match-specific residual alignment.

## Temporal stability

- report all calendar-week point results;
- perform leave-one-week-out influence analysis;
- calculate paired uncertainty using match-, calendar-day- and calendar-week-cluster bootstraps;
- use 4,000 replicates and seed `20260719`.

## Frozen interpretation gate

`mechanism_falsification_passed` requires:

- observed residual selected log-CLV exceeds the circular-shift null with empirical upper-tail p ≤ 0.01;
- observed residual-minus-raw log-CLV exceeds the null with p ≤ 0.01;
- residual-minus-raw log-CLV remains positive after omitting any single calendar week.

`profit_validation_passed` additionally requires:

- residual-minus-raw realized return beats the placebo with p ≤ 0.05;
- the calendar-week cluster-bootstrap 95% lower bound for incremental return is above zero.

This test uses an already opened historical period. It is diagnostic, cannot become confirmatory, and cannot authorize live execution or a profit claim.