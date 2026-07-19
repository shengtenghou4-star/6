# Experiment 023 Protocol — Execution break-even envelope

Status: **frozen before result generation**.

## Question

Experiment 018 found a broad residual-policy ranking advantage, but practical historical return remained negative and paired uncertainty usually crossed zero. Experiment 023 measures the remaining engineering gap: how much delay, price deterioration and selective non-fill can the already-frozen residual policy tolerate before its standalone or incremental advantage disappears?

This is a historical diagnostic, not a live authorization or prospective profit test.

## Frozen source

The audit reconstructs the exact Experiment 017/018 pipeline:

- unchanged train/validation/test partitions and frozen models;
- raw-model bookmaker and outcome identity;
- positive raw-score top 5% policy by cutoff;
- positive residual action-rank top 5% policy by cutoff;
- 2,988 attempted selections per policy;
- policy flags and timestamp prices frozen before outcomes are loaded.

No model, threshold, stake, cutoff or opportunity identity may be changed after results are observed.

## Execution grid

Same-source execution prices are read at 0, 1, 2 and 3 hours after selection. Missing quotes are never imputed.

The point grid crosses four delays, four fill rates (100%, 90%, 75%, 50%) and four deterministic outcome-blind fill mechanisms:

1. `common_random`: common hashed ordering;
2. `adverse_move_rejection`: largest adverse price moves rejected first;
3. `edge_rejection`: highest frozen scores rejected first;
4. `book_clustered_outage`: whole bookmaker clusters removed first, with only the boundary cluster partially filled.

All mechanisms use exact floor quotas among execution-eligible attempted selections. Randomization is keyed by delay and mechanism so fill-rate slices are nested and comparable. The full grid contains 64 zero-added-slippage envelopes.

## Break-even frontiers

Each envelope reports:

- signed residual standalone additional slippage needed to reach zero profit;
- signed residual-only additional slippage needed to equal the raw ledger;
- raw and residual fills, profit and ROI;
- paired incremental return;
- concentration by bookmaker, cutoff and selected outcome.

Negative break-even values mean the target was already missed before any additional haircut. Positive values are tolerance estimates, not evidence that such execution is available.

Event-cluster bootstrap uses 1,000 replicates for the 90% fill slice at every delay and mechanism, producing 16 bootstrapped frontier cells. Other fill rates are point-estimate sensitivity checks.

## Preregistered practical gate

Four practical envelopes are fixed at 1-hour delay, 90% fill and 25 bps common slippage, one per fill mechanism.

An envelope passes only if residual standalone ROI is positive and the lower 95% event-cluster bound for residual-minus-raw return per opportunity is above zero. The experiment-level gate passes if at least one of the four fixed envelopes passes; all four remain visible.

## Evidence boundary

The historical test period has already been opened. This experiment can quantify or falsify execution robustness, but cannot establish real account capacity, actual rejection behavior, prospective profitability or live deployability. The running seven-day campaign and both frozen campaign-close evaluators remain untouched.
