# Experiment 015 — Rank-only execution-friction stress protocol

Status: **frozen before results**.

## Question

Does the historically strongest action-residual architecture retain economic value after conservative delays, adverse price movement, slippage and missed fills?

## Frozen architecture

- reconstruct the Experiment 013 raw baseline and rank-only overlay;
- the raw model fixes bookmaker and H/D/A candidate identity;
- action residuals may only rerank those fixed identities;
- exact top-20% trade fraction at T-48h, T-24h, T-12h and T-6h;
- one-unit flat stakes;
- no post-result removal of draws, bookmakers or cutoffs.

## Actual historical execution prices

For each fixed candidate identity, extract the same bookmaker's selected-outcome decimal quote at:

- signal time;
- one hour later;
- two hours later;
- three hours later.

Missing later quotes remain missing and cannot be filled. Delay zero must exactly reproduce the frozen observation quote.

## Frozen friction grid

Cartesian grid:

- delay: 0, 1, 2 or 3 hours;
- additional adverse log-odds haircut: 0, 25, 50 or 100 basis points;
- base fill rate: 100%, 90%, 75% or 50%.

This creates 64 scenarios.

Fill draws are deterministic SHA-256 values keyed by match, cutoff, bookmaker, outcome and scenario. They do not use match outcomes. Fill probability declines further when the same-book quote has already moved adversely:

`effective fill probability = base fill rate × exp(-20 × adverse log move)`

## Frozen metrics

For baseline and rank-only overlay:

- attempts and fills;
- realized flat-stake profit;
- ROI per fill;
- return per opportunity;
- maximum drawdown;
- match-cluster bootstrap interval;
- break-even additional slippage;
- cutoff stability.

Incremental overlay-minus-baseline metrics are computed on the exact same match/cutoff opportunity universe. Bookmaker contribution and leave-one-book-out diagnostics are mandatory.

## Four core scenarios

1. delay 0h, slippage 0bps, fill 100%;
2. delay 1h, slippage 25bps, fill 90%;
3. delay 2h, slippage 50bps, fill 75%;
4. delay 3h, slippage 100bps, fill 50%.

## Frozen promotion gate

All must pass:

1. rank-only ROI is positive under zero friction;
2. zero-friction incremental return CI is above zero;
3. rank-only ROI is positive in the practical 1h/25bps/90% scenario;
4. practical incremental return CI is above zero;
5. incremental point lift is positive in all four core scenarios;
6. no bookmaker contributes more than 40% of positive practical-scenario incremental profit.

No threshold may be changed after results are opened.

## Evidence boundary

The historical outcomes have already been opened. This is a diagnostic falsification and execution-envelope study, not a new prospective profit test. It cannot measure real account limits, bet rejection policies or guaranteed fills. Untouched prospective evidence remains necessary.
