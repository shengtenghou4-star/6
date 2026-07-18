# Experiment 006 Protocol — Independent Exact-Timestamp Residual Outcome Information

Status: **preregistered before execution**.

## Purpose

Test whether abnormal-action residuals add match-outcome information beyond the contemporaneous market in the independent `eladsil/football-games-odds` source.

This source was not used in Experiment 005 and contains no bookmaker identity or cross-book structure. The test concerns a single provider/global feed, not bookmaker intent.

## Data and time axis

- verified public source: 461,144 timestamped odds states, 32,345 matches
- markets: 1X2 only
- cutoffs: T-48h, T-24h, T-12h, T-6h, T-3h, T-1h
- each record uses valid states at `t-1h`, `t`, and `t+1h`
- all datetime search values are explicitly normalized to nanoseconds
- odds rows after scheduled kickoff and decimal odds `<=1` are excluded

## Chronological split

- normal-model training: kickoff through 2017-10-31
- residual/outcome-layer validation: 2017-11-01 through 2017-12-31
- locked test: kickoff from 2018-01-01 onward

No match result is loaded until normal models and validation/test residual records have been generated.

## Layer 1: move hazard

Use the fixed Experiment 004 architecture:

- features: current/prior de-vigged H/D/A state, prior movement, overround/current change, time since last quote, update counts in prior 1h/6h/24h, cutoff scale
- fixed `HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=1.0)`
- training data only

## Layer 2: conditional movement

Among training records where the next-hour quote actually moves:

- target: next-hour de-vigged H/D/A probability delta
- baseline: training conditional mean delta by cutoff
- fixed model: one `HistGradientBoostingRegressor` per outcome with the same fixed tree parameters as the classifier
- primary metric: mean absolute error across the three delta components on locked-test mover states
- uncertainty: paired bootstrap by match

Conditional movement passes only if:

1. model test MAE is lower than cutoff-mean baseline;
2. bootstrap 95% CI for baseline-minus-model MAE is entirely above zero;
3. at least 4/6 cutoffs improve.

If this gate fails, match outcomes are not loaded and the outcome test is not executed.

## Frozen residuals

For validation/test states:

- move surprise: `actual_move - predicted_move_probability`
- conditional movement residual on mover states
- unconditional action residual: `actual_delta - p(move) × predicted_conditional_delta`
- L2 magnitudes
- prior-cutoff count, prior mean signed/absolute move surprise, prior mean action-residual magnitude, and cumulative H/D/A action residuals

Prior features use only earlier, already-observed cutoffs within the same match.

## Outcome layer

Three classes: home win, draw, away win.

Training: validation residual states only.

Locked evaluation: test residual states only.

Direct market comparator: actual de-vigged H/D/A state at `t+1`, when the residual becomes observable.

Fitted market-only baseline:

- clipped log `t+1` market H/D/A probabilities
- cutoff one-hot
- `StandardScaler`
- fixed multinomial `LogisticRegression(C=1.0, solver="lbfgs", max_iter=500)`

Augmented model: identical architecture and baseline features plus the frozen residual features. No competition/team/result-derived feature is used.

## Metrics and promotion

Primary: multiclass log loss.

Secondary: multiclass Brier, accuracy, per-cutoff stability.

Uncertainty: paired bootstrap by match, 1,000 fixed-seed replicates.

Outcome residual information is promoted only if all hold:

1. conditional movement gate passes;
2. augmented log loss beats fitted market-only;
3. bootstrap CI for fitted-market-minus-augmented log loss is entirely above zero;
4. augmented multiclass Brier improves;
5. at least 4/6 cutoffs improve in log loss;
6. augmented log loss also beats the unfitted direct `t+1` market.

No threshold or model selection occurs on locked test. Negative results are valid. Profitability is outside this experiment.
