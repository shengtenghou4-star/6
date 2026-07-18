# Experiment 005 Result — Incremental Outcome Information in Frozen Abnormal-Action Residuals

Status: **completed; promotion gate failed**.

## Integrity and timing

The test used only outcome-blind validation/test residuals frozen before outcome access.

A residual labeled `T-h` was compared against the reconstructed market state after the corresponding `t → t+1` action became observable. The stale pre-action market was not used as the comparator.

The first two workflow attempts produced no outcome metrics:

1. structurally absent conditional surprise aggregates triggered the non-finite feature gate;
2. pandas returned a read-only direct-market NumPy view during normalization.

Both were deterministic implementation issues fixed before a successful metric-producing run. No model, feature, threshold or regularization choice was changed after viewing outcome performance.

## Sample

Outcome-layer training:

- 57,048 validation match/cutoff records
- 11,855 unique validation matches

Locked test:

- 91,164 match/cutoff records
- 17,956 unique matches
- at least four eligible frozen bookmakers per record

## Locked-test results

### Direct `t+1` market reference

- log loss: `0.97464660`
- multiclass Brier: `0.57995895`
- accuracy: `0.531251`

### Fitted market-only baseline

- log loss: `0.97351668`
- multiclass Brier: `0.57921614`
- accuracy: `0.531262`

### Market plus frozen residual aggregates

- log loss: `0.97384447`
- multiclass Brier: `0.57943566`
- accuracy: `0.531339`

The residual-augmented model beat the unfitted direct market reference, but did **not** beat the like-for-like fitted market-only baseline:

- fitted-baseline minus augmented log loss: `-0.00032779`
- fitted-baseline minus augmented Brier: `-0.00021952`
- paired match-bootstrap log-loss improvement CI: `[-0.00061356, -0.00006786]`
- improved cutoffs: **0/6**

The bootstrap interval is entirely below zero, so the augmented model was consistently slightly worse than the fitted market-only model.

## Promotion checks

- beats fitted market-only log loss: **failed**
- bootstrap CI entirely above zero: **failed**
- beats fitted market-only Brier: **failed**
- improves at least 4/6 cutoffs: **failed**
- beats unfitted direct market: passed

Overall promotion: **failed**.

## Interpretation

The promoted normal-behavior models are real: bookmaker move/no-move and conditional movement are learnable and independently reproducible.

However, the first predeclared global cross-book aggregation of their abnormal residuals does **not** add broad H/D/A outcome information beyond a properly calibrated contemporaneous market model.

This result rejects the tested formulation. It does not prove that every bookmaker-specific, regime-specific or sequential residual is useless, but those alternatives cannot be selected and retested on this already opened locked test without becoming exploratory.

No profitability test is promoted from Experiment 005.

## Next valid route

The next confirmatory route must use a genuinely independent outcome holdout or prospective data. A useful immediate candidate is the independently acquired exact-timestamp 2016–2018 single-feed dataset: train both normal-action layers on its training period, freeze its own residuals, fit the residual outcome layer on its validation period and evaluate only once on its locked 2018 test period.

Workflow artifact digest: `sha256:d42eef8a4c10bb160b67a666a370ed531594d3f54a40687379f8b6bc34c4f4be`.
