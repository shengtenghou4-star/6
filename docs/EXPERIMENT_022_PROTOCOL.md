# Experiment 022 Protocol — Residual dose-response heterogeneity audit

Status: **frozen before the workflow reads the Experiment 017 settled ledger**.

## Question

Is the threshold-free residual-uplift relationship from Experiment 021 broadly distributed across bookmakers, selected outcomes and cutoffs, or is it driven by one source or market segment?

## Frozen source and construction

- Experiment 017 artifact ID: `8439484047`;
- artifact ZIP SHA-256: `15bc79ca3011a65f8347d2e0569b93268d76343a85cbd1f3c7e9ede245ad2554`;
- all 59,816 raw-model-selected opportunities;
- fixed bookmaker/outcome candidate identity;
- reuse Experiment 021 exactly: 15 baseline-score bins within cutoff, ten residual-uplift dose bins within bookmaker × cutoff × baseline bin;
- no model refit, subgroup threshold search, bookmaker deletion, outcome deletion or cutoff deletion.

## Frozen groups

Bookmakers:

- ComeOn (`b30`);
- bet-at-home (`b3`);
- bet365 (`b9`);
- 10Bet (`b7`);
- BetVictor (`b26`);
- Betclic (`b16`);
- Expekt (`b6`);
- Tipico (`b23`).

Selected outcomes are home, draw and away. Cutoffs are T-48, T-24, T-12 and T-6.

## Diagnostics

For every frozen group, report:

- within-stratum residual-uplift slope for same-book closing log-CLV;
- highest-dose minus lowest-dose closing log-CLV;
- the same two point statistics for one-unit realized return;
- opportunities and unique matches.

For each bookmaker omission, event-cluster bootstrap the global CLV and return slopes with 4,000 replicates. Positive CLV slope-numerator contribution is also decomposed by bookmaker.

## Frozen gates

`mechanism_heterogeneity_passed` requires:

- positive CLV slope in at least six of eight bookmakers;
- positive CLV slope for home, draw and away identities;
- positive CLV slope at all four cutoffs;
- every leave-one-book-out CLV slope 95% lower bound above zero;
- no bookmaker contributes more than 50% of total positive CLV slope numerator.

`profit_heterogeneity_passed` requires every leave-one-book-out realized-return slope 95% lower bound above zero.

The historical test period is already opened. This audit is diagnostic and cannot authorize a profit claim, live execution or any modification of the untouched prospective campaign.