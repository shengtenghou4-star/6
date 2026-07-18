# Experiment 007 Protocol — Abnormal Residuals and Subsequent Market Repricing

Status: **preregistered before execution**.

## Question

After a one-hour quote action is judged abnormal relative to the frozen normal-action models, does that residual predict the market's next three hours of repricing beyond the complete raw market state already observable at signal time?

This is a mechanism/lead-lag test. It does not use match outcomes and is not yet a profit test.

## Source and split

Independent exact-timestamp source: `eladsil/football-games-odds`.

- normal-action training: kickoff through 2017-10-31
- repricing-layer training: 2017-11-01 through 2017-12-31
- locked repricing test: kickoff from 2018-01-01 onward

The normal move-hazard and conditional-movement architectures are exactly those frozen in Experiment 006.

## Signal and target timestamps

Signal cutoffs: T-48h, T-24h, T-12h, T-6h.

For cutoff `T-h`:

1. normal behavior is evaluated at `t = T-h`;
2. the realized one-hour action and its residual become observable at `t+1 = T-(h-1)`;
3. the target state is the as-of market at `t+4 = T-(h-4)`;
4. target repricing is the de-vigged H/D/A change from `t+1` to `t+4`.

This gives a fixed three-hour forward window after the signal is observable. T-3h and T-1h signals are excluded because their three-hour windows would reach or cross kickoff.

All datetime search values are explicitly normalized to nanoseconds. Post-kickoff rows and decimal odds `<=1` remain excluded.

## Fair market-only information set

The market-only models receive all raw information used by the normal-action model plus everything observed during `t→t+1`:

- prior/current de-vigged H/D/A states at `t-1` and `t`
- prior movement and overround features
- update recency/count features
- actual `t→t+1` move indicator
- actual `t→t+1` H/D/A delta
- actual `t+1` H/D/A state and overround
- cutoff one-hot indicators

Therefore the residual model receives no trivial advantage from knowing the latest quote movement or state.

## Augmented residual information

The augmented models receive exactly the same raw market features plus:

- signed and absolute move surprise
- conditional movement residual H/D/A and L2 magnitude
- unconditional action residual H/D/A and L2 magnitude
- prior-cutoff residual count
- prior mean signed/absolute move surprise
- prior mean action-residual magnitude
- cumulative prior H/D/A action residual

No future target field enters these features.

## Task A — Future repricing hazard

Target: whether the raw 1X2 quote state changes at all between `t+1` and `t+4`.

Fixed baseline and augmented models:

`HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=1.0, random_state=20260718)`

Primary metric: Brier score.

Promotion checks:

1. augmented locked-test Brier is lower than market-only;
2. paired match-bootstrap 95% CI for market-only-minus-augmented Brier is entirely above zero;
3. at least 3/4 cutoffs improve.

## Task B — Conditional repricing direction/magnitude

Eligibility: locked-test records where the market actually changes during the three-hour target window.

Target: three-dimensional de-vigged H/D/A probability delta from `t+1` to `t+4`.

Fixed baseline and augmented models: one `HistGradientBoostingRegressor` per H/D/A component with the same fixed tree parameters.

Primary metric: row MAE averaged across H/D/A.

Promotion checks:

1. augmented locked-test MAE is lower than market-only;
2. paired match-bootstrap 95% CI for market-only-minus-augmented MAE is entirely above zero;
3. at least 3/4 cutoffs improve.

## Overall promotion

A directional residual repricing signal is promoted only if both Task A and Task B pass every check.

Passing authorizes a separately preregistered closing-line-value/executable-price study. It does not by itself establish match-result alpha, profit or subjective bookmaker intent.

A negative result is valid. No feature/model/threshold selection may be made after viewing locked-test results.
