# Experiment 021 Protocol — Threshold-free residual dose-response audit

Status: **frozen before the first successful workflow reads and evaluates the Experiment 017 settled ledger**.

The initial implementation attempted 20 baseline-score bins but stopped before producing any statistic because one bookmaker/cutoff stratum contained only nine rows and could not populate ten dose bins. Before any result was generated, the baseline partition was reduced to 15 bins; the smallest frozen stratum then contains at least ten rows. No outcome, CLV or return statistic informed this amendment.

## Question

Does match-specific residual uplift improve subsequent same-book closing-price quality continuously after conditioning on the raw baseline score, or is the historical result confined to an arbitrarily selected top-5% threshold?

## Frozen source

- Experiment 017 artifact ID: `8439484047`;
- artifact ZIP SHA-256: `15bc79ca3011a65f8347d2e0569b93268d76343a85cbd1f3c7e9ede245ad2554`;
- all 59,816 raw-model-selected opportunities;
- raw candidate bookmaker and outcome identity remain unchanged;
- no model refit, feature deletion, bookmaker deletion, cutoff deletion or policy retuning.

## Dose construction

1. Split the raw baseline score into 15 deterministic equal-count bins separately within T-48, T-24, T-12 and T-6.
2. Define adjustment strata as bookmaker × cutoff × baseline-score bin.
3. Standardize residual uplift within each stratum.
4. Assign ten deterministic equal-count residual-uplift dose bins within each stratum.
5. Report closing log-CLV, fair-probability CLV and one-unit realized return for all ten bins and by cutoff.

This construction tests residual information conditional on a narrow raw-score band and fixed candidate identity.

## Primary statistics

- within-stratum standardized residual-uplift slope for same-book closing log-CLV;
- top dose minus bottom dose mean closing log-CLV;
- the same statistics for one-unit realized return as secondary economic diagnostics.

## Falsification and uncertainty

For 4,000 fixed-seed null replicates, circularly shift the uplift z-score and dose labels in chronological order within each frozen stratum. This preserves baseline-score bands, bookmaker, cutoff, uplift distribution and dose capacity while breaking match-specific alignment.

Event-cluster bootstraps use 4,000 replicates. Cutoff consistency requires positive top-minus-bottom closing log-CLV in at least three of four cutoffs.

## Frozen gates

`dose_response_mechanism_passed` requires:

- CLV slope placebo upper-tail p ≤ 0.01;
- CLV top-minus-bottom placebo p ≤ 0.01;
- event-cluster 95% lower bounds above zero for both CLV statistics;
- positive top-minus-bottom CLV in at least three cutoffs.

`realized_profit_validation_passed` requires:

- realized-return slope placebo p ≤ 0.05;
- event-cluster 95% lower bound above zero for the return slope.

The historical test period is already opened. This experiment is a falsification and mechanism diagnostic, not confirmatory evidence and not authorization for live execution or a profit claim.