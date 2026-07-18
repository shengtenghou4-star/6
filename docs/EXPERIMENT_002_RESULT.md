# Experiment 002 Result — Bookmaker Move / No-Move Hazard

Status: **completed; both preregistered models promoted**.

## Data

Same frozen historical tensor, bookmaker set, cutoffs and chronological split as preregistered.

Eligible states:

- train: 1,669,834
- validation: 409,350
- locked test: 667,574

Locked-test move prevalence: `0.317512`.

No match result/score field entered features or target.

## Logistic regression

Locked test:

- empirical book×cutoff baseline Brier: `0.17540601`
- logistic Brier: `0.15914995`
- relative Brier improvement: **9.27%**
- ROC AUC: `0.81142`
- log loss: `0.48370`
- improved books: **8/8**
- improved cutoffs: **5/6**
- only T-48h worsened slightly (`-0.00219` Brier improvement)
- match-level paired bootstrap CI for improvement: `[0.02115, 0.02269]`, entirely above zero

Promotion rule passed.

## Fixed HistGradientBoosting classifier

Locked test:

- empirical baseline Brier: `0.17540601`
- model Brier: `0.14957415`
- relative Brier improvement: **14.73%**
- ROC AUC: `0.83534`
- log loss: `0.45762`
- improved books: **8/8**
- improved cutoffs: **6/6**
- match-level paired bootstrap CI for improvement: `[0.03064, 0.03230]`, entirely above zero

Promotion rule passed.

The strongest cutoff-level improvement occurs near kickoff (T-1h), but even T-48h improves slightly for the nonlinear model.

## Core conclusion

The sparse-action formulation is empirically supported:

> Whether a bookmaker changes its 1X2 state in the next hour is conditionally predictable from its own recent state and contemporaneous cross-book market structure.

This is the first promoted component of the project's normal-bookmaker-behavior system.

It does **not** prove bookmaker intent, outcome alpha, or profitability.

## Next stage

Build a separate conditional movement model **only among actual next-hour moves**:

1. predict the direction/structure of movement relative to the current consensus;
2. estimate movement magnitude only conditional on a move;
3. combine hazard + conditional movement to form an expected-action distribution;
4. generate out-of-sample abnormal residuals only from frozen normal-behavior predictions.

Those residuals can later be tested against outcomes/economic value in a separate preregistered phase.

Workflow artifact digest: `sha256:eeb1ce177c6357f446c7e8949a09db6b9824e1a472afb54c1ddfd6cdd4f1f3d7`.