# Experiment 016 Protocol — Validation-only selective abstention

Status: preregistered before test metrics are opened by this experiment.

## Question

Can the frozen rank-only residual architecture become materially more selective without changing candidate bookmaker/outcome identity or using match outcomes to tune the rule?

## Fixed architecture

- Raw-market model fixes the bookmaker and outcome candidate for each match/cutoff.
- Action-residual model supplies ranking information only.
- No bookmaker, outcome or cutoff is deleted after observing return results.
- Policy calibration uses closing-price targets only; match outcomes are excluded from all threshold selection.

## Calibration split

Validation matches are deterministically divided by SHA-256 of `match_id`:

- 70% model-fitting partition;
- 30% policy-calibration partition.

All rows from one match remain in one partition. The historical test split remains untouched until a single policy is frozen.

## Candidate signals

For the raw-market-selected candidate:

- rank-only expected fair-probability movement;
- raw-market expected movement;
- residual uplift: rank-only minus raw-market expected movement;
- top-versus-second rank margin;
- positive-direction agreement.

## Frozen policy family

The only candidate policies are:

1. positive rank score, ranked by rank score;
2. positive rank score and positive residual uplift, ranked by rank score;
3. positive rank score and positive residual uplift, ranked by rank margin.

For each family the only allowed trade fractions are 1%, 2%, 5%, 10% and 20%, applied independently within each cutoff.

## Calibration selection rule

A policy is eligible only if the calibration partition has:

- at least 300 trades;
- positive mean same-book closing log-CLV;
- match-bootstrap 95% lower bound above zero;
- positive mean log-CLV in at least three of four cutoffs.

Among eligible policies choose the highest lower confidence bound. Ties are broken by:

1. higher mean log-CLV;
2. more trades;
3. simpler policy family order as listed above;
4. higher trade fraction.

If no policy is eligible, freeze `NO_TRADE_POLICY` and do not search further.

## Test gate

The frozen policy is evaluated once on the historical test split. Promotion to prospective shadow use requires:

- positive test mean same-book closing log-CLV;
- match-bootstrap 95% lower bound above zero;
- positive mean log-CLV in at least three of four cutoffs;
- positive incremental opportunity log-CLV over the frozen 20% raw baseline;
- no single bookmaker contributes more than 50% of positive policy CLV.

This remains a historical diagnostic because the test period was opened by earlier experiments. Any promoted policy may only enter the already-running prospective shadow campaign; it is not a profit claim.