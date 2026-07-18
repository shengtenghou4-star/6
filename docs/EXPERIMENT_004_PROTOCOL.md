# Experiment 004 Protocol — Independent Exact-Timestamp Move-Hazard Replication

Status: **preregistered before execution**.

## Question

Does one-hour move/no-move predictability generalize to an independent exact-timestamp football odds feed, without cross-book features or Beat The Bookie data?

## Source

`eladsil/football-games-odds`, already independently audited:

- 461,144 quote-state rows
- 32,345 unique matches
- exact `date_created` timestamps
- one source/global feed; no bookmaker identity column

Exclude quote rows after scheduled kickoff and any row with a home/draw/away odd <=1 or nonnumeric.

## Frozen cutoffs

For each match reconstruct latest known quote states as-of:

- T-49/T-48/T-47h
- T-25/T-24/T-23h
- T-13/T-12/T-11h
- T-7/T-6/T-5h
- T-4/T-3/T-2h
- T-2/T-1/T-0h

Targets correspond to current cutoffs T-48, T-24, T-12, T-6, T-3 and T-1h.

A next-hour move is any change in the source's full H/D/A quote state between the as-of state at t and t+1h.

## Features available by t

- current and prior de-vigged H/D/A probabilities
- prior-hour de-vigged movement
- current/prior overround and change
- hours since last source quote update at current cutoff
- quote-update counts during prior 1h, 6h and 24h
- hours before kickoff

No results or scores. No cross-book features exist in this source.

## Split

By scheduled kickoff:

- train <= 2017-10-31
- validation 2017-11-01 through 2017-12-31
- locked test >= 2018-01-01

## Baseline

Smoothed training empirical move probability by cutoff: `(moves+1)/(states+2)`.

## Fixed models

1. StandardScaler + LogisticRegression(C=1.0, max_iter=250).
2. HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=1.0, seed=20260718).

No test tuning.

## Metrics

Primary: Brier score.

Secondary: log loss, ROC AUC, by-cutoff performance, calibration.

Uncertainty: paired bootstrap over match-level Brier improvement, 500 replicates.

## Replication criterion

A model supports independent structural replication only if on locked test:

1. overall Brier beats the cutoff empirical baseline;
2. bootstrap 95% CI is entirely above zero;
3. at least 4/6 frozen cutoffs improve.

Failure is valid and would imply the strong Experiment 002 result may depend materially on cross-book information and/or the original source structure.