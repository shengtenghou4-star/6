# Experiment 009 Result — Realized-Return Audit of Frozen Named-Book CLV Strategies

Status: **completed; historical flat-stake returns were negative and statistically inconclusive**.

## Evidentiary status

This was a locked-rule diagnostic audit, not a fresh confirmatory profit test. The exact Experiment 008 model, cutoffs, ranking, bookmaker/outcome selection and top-20% trade fraction were reconstructed before final scores were joined. However, the historical outcome period had been opened in earlier experiments.

Execution assumptions were deliberately optimistic:

- one-unit flat stake
- selected named-book quote at the residual-observation timestamp
- zero commission and slippage
- no rejected bets, stake limits, account restrictions or latency

## Sample

Each frozen strategy produced:

- 59,895 match/cutoff opportunities
- 11,977 trades
- approximately 20.0% trade fraction
- more than 8,000 unique traded matches

## Raw-market baseline strategy

- wins: 5,325
- hit rate: `44.46%`
- total profit: `-259.20` units
- ROI per trade: **-2.164%**
- per-opportunity return: `-0.0043276` units
- trade-ROI match-bootstrap CI: `[-4.997%, 0.686%]`
- maximum drawdown: `320.57` units
- mean trade log-CLV remained positive: `0.0142539`

## Residual-augmented strategy

- wins: 5,386
- hit rate: `44.97%`
- total profit: `-250.82` units
- ROI per trade: **-2.094%**
- per-opportunity return: `-0.0041877` units
- trade-ROI match-bootstrap CI: `[-4.890%, 0.754%]`
- maximum drawdown: `287.67` units
- mean trade log-CLV remained positive: `0.0147550`

The residual strategy lost less and had a smaller drawdown, but its return was still negative and its confidence interval crossed zero.

## Residual versus baseline

- residual-minus-baseline total profit: `+8.38` units
- mean residual-minus-baseline return per opportunity: `0.0001399`
- paired match-bootstrap CI: `[-0.0040762, 0.0042459]`
- trade-opportunity Jaccard overlap: `61.15%`
- among overlapping trades, same bookmaker and outcome: `64.50%`

The incremental return difference was not statistically distinguishable from zero.

## Cutoff and selection diagnostics

Residual strategy ROI by cutoff:

- T-48h: `+0.187%`
- T-24h: `-4.496%`
- T-12h: `-1.922%`
- T-6h: `-1.521%`

Residual strategy ROI by selected outcome:

- away: `+0.147%`
- draw: `-12.626%`
- home: `-1.640%`

The draw selections were the largest realized-return drag. This is a diagnostic observation only; deleting or downweighting draws after seeing the result would be post-selection and is not permitted as a confirmatory conclusion.

## Interpretation

The audit shows why positive CLV and realized profit must remain separate claims.

Both strategies consistently selected prices that shortened over the next three hours, yet both produced approximately -2.1% flat-stake ROI in this finite outcome sample. Possible contributors include outcome variance, selection/price dependence, the short CLV benchmark rather than true market close, and the lack of execution/commission modeling. The experiment does not identify one causal explanation.

Supported conclusions:

- the historical price-drift/CLV signal remains real;
- residuals improved repricing prediction and slightly improved realized point estimates;
- neither strategy demonstrated positive realized ROI;
- residual-specific realized-return lift over the raw-market strategy was not established.

No profit claim is promoted. The next confirmatory economic step requires untouched prospective named-book data with actual timestamps, price availability, fill assumptions and limits.

Workflow artifact digest: `sha256:1977f2a27ec71b897393d2c23f513a8b1c261a5eb3c273fb9ab30a7152a1599f`.
