# Experiment 009 Protocol — Realized-Return Audit of Frozen Named-Book CLV Strategies

Status: **frozen diagnostic audit before execution**.

## Purpose and evidentiary status

Measure realized historical flat-stake returns of the exact Experiment 008 raw-market and residual-augmented top-20% named-book CLV strategies.

This is not an untouched confirmatory profit test because the same historical outcome period has been opened in earlier experiments. It is a practical diagnostic of whether the frozen price advantage translated into realized returns in this sample.

No strategy rule may change.

## Frozen strategy reconstruction

Experiment 008 is rerun exactly:

- Beat The Bookie hourly tensor
- eight frozen bookmaker slots
- T-48h, T-24h, T-12h and T-6h signals
- same normal-action residual architecture and training caps
- same fixed repricing models
- expected future delta = predicted future-move probability × predicted conditional delta
- one maximum-confidence bookmaker/outcome row per match × cutoff
- exactly the top 20% of match signals within each cutoff
- deterministic tie-breaking

The raw-market and residual strategies are reconstructed independently according to their own frozen predictions.

## Price and settlement

Execution-price proxy: the selected bookmaker's decimal odds at the residual-observation timestamp (`current tensor index + 1`).

Settlement:

- home selection wins when `score_home > score_away`
- draw selection wins when scores are equal
- away selection wins when `score_away > score_home`
- one-unit flat stake per trade
- winning net return = decimal odds minus 1
- losing net return = -1
- no-trade opportunity return = 0

No commission, tax, rejected bet, stake limit, latency, account restriction or price slippage is modeled.

## Required integrity checks

- strategy selection is completed before score fields are joined
- selected observation odds are finite and greater than 1
- one strategy opportunity per match × cutoff
- no duplicate trade key
- final scores are consistent for each match ID
- baseline and residual opportunities reconcile on the same match × cutoff universe

## Metrics

For each strategy:

- opportunities, trades and unique matches
- hit rate
- mean selected decimal odds
- total flat-stake profit
- ROI per trade
- mean return per opportunity
- match-bootstrap 95% confidence intervals for ROI and per-opportunity return
- ROI by cutoff, bookmaker and selected outcome
- chronological cumulative profit and maximum drawdown
- concentration share of trades/profit by bookmaker and outcome

Comparison:

- residual-minus-baseline per-opportunity return on the common match × cutoff universe
- paired match-bootstrap confidence interval by match
- overlap of selected trades and selections

## Interpretation

Results are descriptive/diagnostic only.

A positive return cannot establish future profitability because the outcome period was not untouched and executability is not modeled. A negative return does not negate the Experiment 008 CLV result; CLV is a lower-variance price-quality metric and can diverge from finite-sample realized outcomes.

No rule may be altered after the result is viewed.
