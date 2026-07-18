# Experiment 007 Result — Abnormal Residuals and Subsequent Market Repricing

Status: **completed; both preregistered repricing gates passed**.

## Question tested

After the one-hour abnormal-action residual became observable, did it improve prediction of the market's following three hours of repricing beyond a fair raw-market model that already saw:

- all normal-model input state;
- the actual latest move/no-move event;
- the actual latest H/D/A probability delta;
- the complete contemporaneous `t+1` market state and overround?

No match outcomes were loaded or used.

## Locked-test sample

Independent exact-timestamp source:

- 7,829 signal/target records
- 2,127 matches
- signal cutoffs T-48h, T-24h, T-12h and T-6h
- target: market repricing during the fixed three-hour window after each signal became observable
- 3,017 future-moving records; future-move rate `38.54%`

## Task A — Future move/no-move hazard

Market-only baseline:

- Brier: `0.19545429`
- log loss: `0.57794064`

Market plus frozen residuals:

- Brier: `0.19270998`
- log loss: `0.57107897`
- relative Brier improvement: **1.40%**
- improved cutoffs: **4/4**
- paired match-bootstrap Brier-improvement CI: `[0.00098947, 0.00457348]`

All hazard promotion checks passed.

## Task B — Conditional future direction/magnitude

Among 3,017 future-moving states across 1,847 matches:

- market-only H/D/A delta MAE: `0.01284065`
- market plus residual MAE: `0.01264816`
- relative MAE improvement: **1.50%**
- improved cutoffs: **4/4**
- paired match-bootstrap MAE-improvement CI: `[0.00005543, 0.00033283]`

All conditional repricing promotion checks passed.

## Interpretation

This is the first positive downstream information result from the abnormal residual architecture.

The residuals did not improve broad match-result probabilities in Experiments 005/006. They did improve prediction of what the market itself would do next, after controlling for the complete raw market state and latest observed movement.

Therefore the supported statement is:

> abnormal quote-action residuals contain a statistically stable lead/repricing signal about subsequent market movement.

The supported signal is modest rather than magical: approximately 1.4% relative improvement in future-move Brier and 1.5% relative improvement in conditional repricing MAE. But it survives a separate chronological locked test, all four cutoffs and match-level bootstrap uncertainty.

This result is consistent with the project's core mechanism: the residual captures information about quote behavior that has not yet been fully incorporated into the next market state.

It does **not** yet establish:

- executable bookmaker profit;
- match-result alpha;
- subjective bookmaker intent;
- robustness across named bookmakers or other data vendors.

The next valid gate is a frozen closing-line-value/price-capture study. Because this source is an unnamed single global feed, that study must initially be described as a market-price CLV proxy, not guaranteed executable odds.

Workflow artifact digest: `sha256:ee93588df217ca7425afa1cf63af87b07119db2c601056cb65c9ad140420367b`.
