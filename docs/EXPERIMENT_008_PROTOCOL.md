# Experiment 008 Protocol — Named-Book Residual Repricing and CLV Proxy

Status: **preregistered before execution**.

## Purpose

Convert the promoted abnormal-residual repricing signal into a frozen market-price closing-line-value proxy on the Beat The Bookie hourly named-bookmaker tensor.

No match outcomes are used in this experiment. Positive CLV is not automatically executable profit.

## Source and frozen books

Source: acquired Beat The Bookie 32-bookmaker × 3-outcome × 72-hour tensor.

Frozen books:

- ComeOn (`b30`)
- bet-at-home (`b3`)
- bet365 (`b9`)
- 10Bet (`b7`)
- BetVictor (`b26`)
- Betclic (`b16`)
- Expekt (`b6`)
- Tipico (`b23`)

The source-code-recovered bookmaker mapping and T-71h→kickoff axis remain frozen.

## Split

- normal-action training: through 2016-06-30
- repricing-model training: 2016-07-01 through 2016-08-31
- locked test: 2016-09-01 onward

The future-price/CLV target used here was not evaluated in Experiments 005–007.

## Signal and target timing

Signal cutoffs: T-48h, T-24h, T-12h and T-6h.

At each cutoff:

- current tensor index: frozen cutoff index
- residual-observation index: current + 1
- three-hour future benchmark index: current + 4

The observation and future benchmark must contain complete, valid decimal H/D/A odds for the same frozen bookmaker.

## Normal residuals

Normal move-hazard and conditional-movement models are regenerated exactly as Phase 19:

- fixed HGB architectures
- training-period data only
- validation/test residuals only
- hazard training capped at 500,000 states
- conditional movement training capped at 400,000 mover states

Residual families remain outcome-blind.

## Fair raw-market baseline

The repricing baseline receives:

- all original normal-model `X` features
- actual latest move/no-move indicator
- actual latest de-vigged H/D/A delta
- actual contemporaneous `t+1` H/D/A state

The augmented model receives the identical raw information plus:

- signed/absolute move surprise
- conditional H/D/A residual and L2 magnitude
- unconditional action H/D/A residual and L2 magnitude
- prior-cutoff residual count, means and cumulative H/D/A action residuals

## Repricing models

Task A: future three-hour move/no-move.

Task B: conditional future de-vigged H/D/A delta among future movers.

Baseline and augmented models use identical fixed architectures:

- classifier/regressor `max_iter=120`
- `learning_rate=0.08`
- `max_leaf_nodes=15`
- `l2_regularization=1.0`
- `random_state=20260718`

No locked-test model or feature tuning.

Residual repricing passes only if both tasks improve with paired match-bootstrap CI entirely above zero and at least 3/4 cutoffs improved.

## Frozen CLV strategy

For each baseline/augmented model:

1. expected future H/D/A delta = predicted future-move probability × predicted conditional delta;
2. within each bookmaker row choose the outcome with largest expected probability increase;
3. within each match × cutoff keep the single bookmaker/outcome row with largest predicted increase;
4. within each cutoff select exactly the top 20% of match-level signals, using deterministic descending confidence and stable tie-breaking;
5. no trade is assigned zero CLV in per-opportunity comparisons.

## CLV definitions

For the selected bookmaker/outcome:

- raw log-odds CLV: `log(observation decimal odds / future decimal odds)`
- fair-probability CLV: future de-vigged probability minus observation de-vigged probability

Positive log-odds CLV means the selected price shortened over the three-hour benchmark window.

## Uncertainty and promotion

Paired bootstrap unit: match ID. All cutoffs remain together.

Promotion requires all:

1. augmented repricing hazard passes its incremental gate;
2. augmented conditional repricing passes its incremental gate;
3. augmented top-20% mean trade log-CLV is positive with bootstrap CI entirely above zero;
4. augmented per-opportunity log-CLV exceeds the baseline strategy with paired bootstrap CI entirely above zero;
5. augmented mean fair-probability CLV is positive;
6. augmented mean trade log-CLV is positive in at least 3/4 cutoffs.

Passing establishes only a historical named-book market-price CLV proxy. It authorizes a separate result/ROI, fill, latency and limit study. It does not itself prove future profit or subjective bookmaker intent.
