# Experiment 001 Result — Conditional Normal Bookmaker Behavior

Status: **completed; neither preregistered model promoted**.

## Data used

Training-only completeness selected these 8 historical bookmaker slots:

1. ComeOn (`b30`)
2. bet-at-home (`b3`)
3. bet365 (`b9`)
4. 10Bet (`b7`)
5. BetVictor (`b26`)
6. Betclic (`b16`)
7. Expekt (`b6`)
8. Tipico (`b23`)

Eligible normal-behavior states after time-safe completeness/consensus gates:

- train: 1,669,890
- validation: 409,358
- locked test: 667,579

No match outcome/score field entered features or target.

## Primary result

Persistence (`next state = current state`) remained the strongest MAE baseline.

### Ridge

Locked test:

- persistence MAE: `0.00272888`
- model MAE: `0.00308080`
- relative MAE change: **12.90% worse**
- improved bookmakers: `0/8`
- improved cutoffs: `0/6`
- bootstrap interval for MAE improvement entirely below zero

Not promoted.

### Fixed HistGradientBoosting

Locked test:

- persistence MAE: `0.00272888`
- model MAE: `0.00289831`
- relative MAE change: **6.21% worse**
- improved bookmakers: `0/8`
- improved cutoffs: `1/6` (`T-1h` only)
- bootstrap interval for MAE improvement entirely below zero

Not promoted.

## Important diagnostic

Both learned models improved RMSE despite worsening MAE:

- persistence RMSE: `0.00799551`
- Ridge RMSE: `0.00771743`
- HistGradientBoosting RMSE: `0.00766996`

This pattern is consistent with a sparse-action process: most hourly bookmaker states do not move, so persistence is extremely hard to beat on average absolute error; learned continuous regressors can reduce some large-move errors while introducing small false movements on many no-change states.

This is a diagnostic, not a post-hoc success claim.

## Decision

The direct continuous one-stage next-state formulation is **not promoted** as the project's normal-behavior model.

The next hypothesis should be tested separately and preregistered:

1. first model the **hazard/probability that a bookmaker changes at all** in the next hour;
2. conditional on a change, model direction/magnitude;
3. combine the two only after each component passes frozen out-of-sample tests.

This is closer to the actual research object: `should this bookmaker move in this market state?` A bookmaker that is normally expected not to move must not be penalized by a regression model that invents tiny changes.

No residual/outcome-alpha claim is made from Experiment 001.

Workflow artifact digest: `sha256:349735c17f882d9ecd8ccf7a488b350d84e48b7e1f32de7992ca15d8a1057173`.