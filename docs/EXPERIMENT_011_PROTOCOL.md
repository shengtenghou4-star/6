# Experiment 011 Protocol — Abnormal Residuals and Same-Book Closing-Line Movement

Status: **preregistered before execution**.

## Purpose

Determine whether the promoted abnormal-residual repricing signal predicts durable movement to the same bookmaker's final pre-match tensor state, rather than only temporary three-hour drift.

No match outcomes are used.

## Source, books and split

Source: Beat The Bookie hourly 32-bookmaker × 3-outcome × 72-index tensor.

Frozen books and chronological split are identical to Experiments 008/009:

- ComeOn, bet-at-home, bet365, 10Bet, BetVictor, Betclic, Expekt and Tipico
- normal-action training through 2016-06-30
- closing-repricing model training from 2016-07-01 through 2016-08-31
- locked test from 2016-09-01 onward

## Timing

Signals: T-48h, T-24h, T-12h and T-6h.

For each signal:

- current state: frozen cutoff tensor index
- residual observation: current index + 1
- closing benchmark: tensor index 71

The observation and closing states must both contain complete valid decimal H/D/A odds for the same bookmaker.

Index 71 is the source's final hourly/kickoff state. It is treated as the same-book closing benchmark in this source, not a guarantee that a real wager was fillable at every historical observation price.

## Normal residual architecture

Regenerate Phase 19 exactly:

- same normal features and fixed HGB models
- training-only normal models
- hazard training cap 500,000 states
- conditional movement cap 400,000 mover states
- outcome-blind validation/test residuals

## Fair raw-market baseline

The closing-repricing baseline receives:

- every original normal-model `X` feature
- actual latest move flag
- actual latest H/D/A probability delta
- complete contemporaneous observation H/D/A state and overround
- hours remaining to the closing benchmark

The augmented model receives exactly the same information plus:

- move surprise
- conditional H/D/A movement residual
- unconditional H/D/A expected-action residual
- residual magnitudes
- prior-cutoff residual persistence and cumulative components

## Closing-repricing tasks

### A. Same-book close-move hazard

Target: whether the same bookmaker's raw H/D/A quote changes at all between residual observation and tensor index 71.

Primary metric: Brier score.

### B. Conditional same-book closing delta

Eligibility: rows whose same-book quote changes before close.

Target: de-vigged H/D/A probability delta from observation to close.

Primary metric: row MAE averaged across H/D/A.

Baseline and augmented models use identical fixed HGB architectures:

- `max_iter=120`
- `learning_rate=0.08`
- `max_leaf_nodes=15`
- `l2_regularization=1.0`
- `random_state=20260718`

No locked-test tuning.

Each repricing task passes only with paired match-bootstrap CI entirely above zero and improvement in at least 3/4 cutoffs.

## Frozen closing-CLV strategy

For baseline and augmented models separately:

1. expected closing H/D/A delta = predicted close-move probability × predicted conditional closing delta;
2. choose the outcome with the largest expected probability increase per bookmaker row;
3. keep the single largest-confidence bookmaker/outcome per match × cutoff;
4. within each cutoff select exactly the top 20% of match signals with deterministic tie-breaking.

Metrics:

- closing log-odds CLV = `log(observation decimal odds / closing decimal odds)`
- closing fair-probability CLV = closing de-vigged probability minus observation probability
- per-trade and per-opportunity CLV
- paired match bootstrap

## Promotion

All conditions are required:

1. augmented close-move Brier improves with CI above zero and at least 3/4 cutoffs;
2. augmented conditional close-delta MAE improves with CI above zero and at least 3/4 cutoffs;
3. augmented strategy mean closing log-CLV is positive with CI above zero;
4. augmented per-opportunity closing log-CLV exceeds raw-market strategy with paired CI above zero;
5. augmented fair-probability closing CLV is positive;
6. augmented trade log-CLV is positive in at least 3/4 cutoffs.

Passing supports a durable historical same-book price-quality signal. It does not establish fills, limits, latency feasibility, realized profit or subjective bookmaker intent.
