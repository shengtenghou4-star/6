# Experiment 002 Protocol — Bookmaker Move / No-Move Hazard

Status: **preregistered before execution**.

## Question

Given the market state at hour `t`, can we predict whether a bookmaker will change any part of its valid 1X2 quote in the next hour better than a historical move-rate baseline?

This is a normal-behavior hazard model. It does not predict match results and does not infer bookmaker intent.

## Source and time axis

Beat The Bookie hourly tensor:

- 92,647 matches
- 32 source-mapped bookmaker slots
- index 0 ≈ T-71h, index 71 ≈ kickoff

Invalid decimal odds `<=1.0` are missing.

## Frozen books

Reuse the eight books selected strictly from Experiment 001 training-period availability:

- `b30` ComeOn
- `b3` bet-at-home
- `b9` bet365
- `b7` 10Bet
- `b26` BetVictor
- `b16` Betclic
- `b6` Expekt
- `b23` Tipico

No re-ranking on validation/test.

## Frozen cutoffs

One-hour-ahead move hazard at:

- T-48h: index 23 → 24
- T-24h: index 47 → 48
- T-12h: index 59 → 60
- T-6h: index 65 → 66
- T-3h: index 68 → 69
- T-1h: index 70 → 71

Previous-hour features use `t-1` only.

## Chronological split

- train: <= 2016-06-30
- validation: 2016-07-01 through 2016-08-31
- locked test: >= 2016-09-01

## Target

`move_next_hour = 1` when any of the target bookmaker's three valid raw 1X2 decimal quotes changes from `t` to `t+1`; otherwise `0`.

Require complete valid target 1X2 states at `t-1`, `t`, and `t+1`.

## Features available by t

Target bookmaker:

- current and previous de-vigged H/D/A state
- prior-hour de-vigged movement
- current/previous overround and overround movement

Cross-book market excluding target:

- current/previous mean de-vigged consensus H/D/A
- consensus prior-hour movement
- target-vs-consensus deviation
- current cross-book dispersion H/D/A
- current active-book count
- fraction of other eligible books that moved during `t-1 → t`

Context:

- hours before kickoff
- target bookmaker one-hot identity

No result/score fields.

## Baseline

Smoothed training empirical move probability for each `bookmaker × cutoff` cell:

`(moves + 1) / (states + 2)`.

This is stronger than a global constant/no-move classifier and is frozen before validation/test scoring.

## Frozen models

1. standardized logistic regression: `C=1.0`, no class weighting, max 250 iterations;
2. fixed `HistGradientBoostingClassifier`:
   - `max_iter=120`
   - `learning_rate=0.08`
   - `max_leaf_nodes=31`
   - `l2_regularization=1.0`
   - random seed `20260718`
   - at most 500,000 deterministic training states.

No test tuning.

## Metrics

Primary: Brier score.

Secondary:

- log loss
- ROC AUC
- move prevalence
- by-book and by-cutoff Brier improvement
- 10-bin calibration summary

Uncertainty: paired bootstrap over match-level mean Brier improvement, 500 replicates, fixed seed.

## Promotion rule

On locked test, promote a model only if:

1. overall Brier beats the book×cutoff empirical baseline;
2. 95% paired-bootstrap interval for baseline-minus-model Brier is entirely >0;
3. improves at least 5/8 books;
4. improves at least 4/6 cutoffs.

AUC alone cannot promote the model.

## Follow-on

Only if the move hazard is promoted should a separate conditional model estimate direction/magnitude among predicted/observed moves. Residuals used for outcome/economic research must come from frozen out-of-sample normal-behavior predictions.