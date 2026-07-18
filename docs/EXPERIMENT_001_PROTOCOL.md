# Experiment 001 Protocol — Conditional Normal Bookmaker Behavior

Status: **preregistered before execution**.

## Question

Can the next hourly de-vigged 1X2 state of a bookmaker be predicted more accurately than simple persistence using only the bookmaker's current/past state and the contemporaneous cross-book market?

This experiment does **not** predict match results and does **not** infer bookmaker intent.

## Source

Acquired Beat The Bookie hourly tensor:

- 92,647 matches
- 32 source-mapped bookmaker slots
- 3 outcomes
- 72 hourly indices
- verified time mapping: index 0 = approximately T-71h, index 71 = approximately kickoff

Invalid ordinary decimal odds `<= 1.0` are treated as missing.

## Frozen cutoffs

Evaluate one-hour-ahead transitions at:

- T-48h: index 23 → 24
- T-24h: index 47 → 48
- T-12h: index 59 → 60
- T-6h: index 65 → 66
- T-3h: index 68 → 69
- T-1h: index 70 → 71

For lagged features, use only index `t-1`.

## Frozen chronological split

- train: match date <= 2016-06-30
- validation: 2016-07-01 through 2016-08-31
- locked test: >= 2016-09-01

No match result/score field may enter features or target.

## Bookmaker selection

Select exactly the top 8 bookmaker slots by **training-period complete 1X2 availability across the frozen current cutoffs**.

Selection uses no outcome labels and no validation/test completeness ranking.

## Market representation

For a complete bookmaker 1X2 state, transform decimal odds to proportional de-vigged probabilities.

At each state, cross-book consensus features exclude the target bookmaker. Require at least 3 other complete bookmakers.

## Features at time t only

For target bookmaker:

- current de-vigged H/D/A probabilities
- previous-hour de-vigged H/D/A probabilities
- own previous-hour movement
- cross-book mean consensus H/D/A excluding target, current and previous hour
- consensus previous-hour movement
- target deviation from current consensus
- cross-book dispersion H/D/A excluding target
- active complete-book count
- hours before kickoff
- target bookmaker identity as one-hot feature

No future index is used in features.

## Target

Three-dimensional next-hour change:

`p_book(t+1) - p_book(t)` for home/draw/away.

Predicted next probabilities are clipped positive and renormalized to sum to one.

## Baseline

Persistence:

`p_hat(t+1) = p_book(t)`.

## Frozen models

1. `Ridge(alpha=10)` with standardized numeric features; multi-output delta regression.
2. Fixed nonlinear variant: one `HistGradientBoostingRegressor` per outcome with:
   - `max_iter=100`
   - `learning_rate=0.08`
   - `max_leaf_nodes=31`
   - `l2_regularization=1.0`
   - `random_state=20260718`

For computational boundedness, nonlinear training uses at most 400,000 training states chosen by deterministic random sample with seed `20260718`. Ridge uses all eligible training states.

No hyperparameter tuning on the locked test.

## Metrics

Primary:

- probability MAE across H/D/A

Secondary:

- RMSE
- performance by bookmaker
- performance by cutoff
- validation/test eligible sample counts

Uncertainty:

- paired bootstrap over match-level mean absolute-error improvement, fixed seed, 500 replicates.

## Promotion rule

A model is promoted as a useful normal-behavior baseline only if on the locked test:

1. overall MAE beats persistence;
2. paired-bootstrap 95% interval for `persistence MAE - model MAE` is entirely above zero;
3. it improves at least 5 of the 8 selected bookmakers;
4. it improves at least 4 of the 6 frozen cutoffs.

Failure is a valid result. No residual/outcome-alpha study may reinterpret a failed normal model as successful.

## Next phase

Only after this experiment is frozen and executed may model residuals be constructed for separate abnormal-behavior research.