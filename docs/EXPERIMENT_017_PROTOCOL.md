# Experiment 017 Protocol — Matched-budget historical return diagnostic

Status: preregistered before this script joins match outcomes.

## Question

When both policies retain 5% of the same raw-selected candidate universe, does residual ranking improve realized historical return relative to raw-score ranking?

## Frozen construction

- Reproduce the Experiment 016 deterministic 70/30 validation split.
- Fit raw and residual closing models on the 70% validation fit partition.
- Raw closing models fix bookmaker and outcome identity for every test match/cutoff.
- Raw reference: require positive raw score and rank by raw score.
- Residual policy: require positive action-rank score and rank by action-rank score.
- Each policy retains `floor(cutoff opportunities × 5%)`, with minimum one when eligible rows exist.
- Bind selected timestamp price and all policy flags before loading match outcomes.
- One-unit flat settlement; no commission, latency, rejection or account-limit assumption.

## Reporting

- standalone ROI and match-cluster bootstrap interval;
- paired residual-minus-raw return and interval on the full opportunity universe;
- maximum drawdown;
- cutoff, bookmaker and selected-outcome stability;
- trade overlap and candidate-identity invariance;
- closing log-CLV alongside return.

## Frozen diagnostic checks

The result is called economically encouraging only when all hold:

1. residual policy ROI is positive;
2. residual ROI match-bootstrap lower 95% bound is above zero;
3. residual-minus-raw paired lower 95% bound is above zero;
4. residual ROI is positive at least three of four cutoffs;
5. no single bookmaker contributes more than 50% of positive residual profit.

This historical test period was examined previously, so no result from this experiment is confirmatory and no live execution is authorized.