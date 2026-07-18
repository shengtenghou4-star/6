# Experiment 003 Protocol — Conditional Bookmaker Movement

Status: **preregistered before execution**.

## Question

Conditional on the target bookmaker actually changing its valid 1X2 state from hour `t` to `t+1`, can the direction/magnitude of its next de-vigged probability movement be predicted from information available at or before `t`?

No match result, score or bookmaker-intent label is used.

## Frozen source, books, cutoffs and split

Use the same 92,647-match Beat The Bookie tensor, verified time axis, eight frozen bookmakers and chronological split as Experiments 001/002.

Books: `b30,b3,b9,b7,b26,b16,b6,b23`.

Cutoffs: T-48h, T-24h, T-12h, T-6h, T-3h, T-1h.

Split:
- train <= 2016-06-30
- validation 2016-07-01–2016-08-31
- locked test >= 2016-09-01

Invalid ordinary decimal odds `<=1.0` are missing.

## Eligibility and target

Require complete target-book states at `t-1,t,t+1`, at least three other complete bookmakers for contemporaneous/prior consensus, and an actual raw quote change in at least one target-book outcome from `t` to `t+1`.

Target: three-dimensional de-vigged probability delta `p(t+1)-p(t)`.

## Features at/before t

Same time-safe family as Experiment 002:
- target current/prior de-vigged H/D/A and prior movement
- target current/prior overround and change
- excluding-target current/prior consensus and movement
- current target-vs-consensus deviation
- cross-book dispersion and active count
- fraction of other books that moved during t-1→t
- hours before kickoff
- target-book one-hot identity

## Baselines

A. `conditional_mean`: training mean next delta by bookmaker × cutoff among movers.

B. `consensus_response`: per bookmaker × cutoff, fit one scalar `alpha` on training movers by least squares:

`delta_hat = alpha * (consensus_t - target_t)`

Clip alpha to [-2,2]. This is the primary baseline for promotion.

## Fixed models

1. StandardScaler + Ridge(alpha=10), multi-output.
2. Three fixed HistGradientBoostingRegressors, one per outcome:
   - max_iter=120
   - learning_rate=0.08
   - max_leaf_nodes=31
   - l2_regularization=1.0
   - seed 20260718
   - max 400,000 deterministic training mover states.

Predicted next probabilities are clipped positive and renormalized before scoring.

## Metrics

Primary: mean absolute error across H/D/A on moving states.

Secondary: RMSE, mean cosine similarity of predicted vs actual delta for nonzero vectors, dominant-direction accuracy, by-book and by-cutoff MAE.

Uncertainty: paired bootstrap over match-level MAE improvement vs the consensus-response baseline, 500 replicates, fixed seed.

## Promotion

On locked test, promote only if:
1. overall MAE beats consensus-response baseline;
2. bootstrap 95% interval for baseline-minus-model MAE is entirely >0;
3. improves >=5/8 books;
4. improves >=4/6 cutoffs.

Failure is valid.

## Follow-on

If promoted, combine the frozen move hazard from Experiment 002 with the conditional movement model to form expected-action distributions and out-of-sample abnormal residuals. Outcomes/economic value remain a later separate phase.