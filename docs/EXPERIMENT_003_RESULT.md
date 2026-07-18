# Experiment 003 Result — Conditional Bookmaker Movement

Status: **completed; both preregistered models promoted**.

## Eligible mover states

- train: 537,170
- validation: 139,831
- locked test: 211,963

Only states with an actual next-hour target-book move entered this conditional layer. No match outcome/score fields entered features or target.

## Ridge

Locked test against the preregistered consensus-response baseline:

- baseline MAE: `0.00828891`
- model MAE: `0.00797072`
- relative MAE improvement: **3.84%**
- improves 7/8 bookmakers
- improves 6/6 cutoffs
- match-level bootstrap CI for MAE improvement: `[0.0002528, 0.0002976]`, entirely >0

Also beats the conditional-mean baseline (`0.00859040`).

Promotion rule passed.

## Fixed HistGradientBoosting regressors

Locked test:

- consensus-response baseline MAE: `0.00828891`
- model MAE: `0.00757920`
- relative MAE improvement: **8.56%**
- conditional-mean baseline MAE: `0.00859040`
- RMSE: `0.01277940` vs consensus baseline `0.01361139`
- improves **8/8 bookmakers**
- improves **6/6 cutoffs**
- match-level bootstrap CI for MAE improvement: `[0.0006298, 0.0006809]`, entirely >0
- mean vector cosine similarity: `0.3437`
- dominant movement-direction accuracy: `0.3535`

Promotion rule passed.

## Conclusion

The two-stage normal-behavior architecture is now empirically supported:

1. Experiment 002: predict whether the bookmaker moves next hour;
2. Experiment 003: conditional on a move, predict the expected de-vigged movement vector.

Both layers pass locked chronological out-of-sample tests and broad book/cutoff stability gates.

This is the first complete promoted **normal-bookmaker action model** in the project.

It still does not establish bookmaker intent, match-outcome alpha, or profitability.

## Next stage

Freeze the two promoted layers and generate out-of-sample expected-action distributions / abnormal residuals without retraining on future matches.

Residual families should include at minimum:

- surprise that a predicted-high-probability move did not occur;
- surprise that a predicted-low-probability move did occur;
- conditional movement-vector deviation when a move occurs;
- deviation from consensus-response expectations;
- persistence/duration of abnormal states across sequential cutoffs.

Only after residuals are frozen may match outcomes enter a separate preregistered incremental-information/economic-value study.

Workflow artifact digest: `sha256:28cd6996246d05095dd7a0f7624dc39717632e1eaffa3d963d248d729dd63678`.