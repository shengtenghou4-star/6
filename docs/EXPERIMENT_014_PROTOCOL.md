# Experiment 014 — Completely unseen-book action-residual transfer

## Status

Preregistered before opening the transfer output.

This experiment uses the already opened historical test period. It is a diagnostic bookmaker-transfer audit, not a new untouched alpha or profit test.

## Frozen source and timing

- Beat The Bookie hourly 1X2 tensor
- same eight named bookmaker slots
- same chronological train, validation and test periods as Experiments 002–013
- signal cutoffs T-48h, T-24h, T-12h and T-6h
- same-book final valid H/D/A state at tensor index 71
- no match outcomes

## Leave-one-book-out construction

Eight folds are run. For each held-out bookmaker:

1. bookmaker one-hot columns are removed from every model input;
2. normal move-hazard and conditional-action models are trained only on the other seven books' chronological training rows;
3. action residuals are generated for validation and test rows;
4. generic raw-market closing models and contemporaneous-action-residual closing models are trained only on the other seven books' validation rows;
5. predictions are retained only for the held-out bookmaker's locked test rows.

Concatenating all folds creates one out-of-book prediction for every eligible test quote. No quote is scored by a model trained on that bookmaker.

## Frozen residual family

Only the economic carrier identified in Experiment 012 is added:

- conditional residual H/D/A and L2 magnitude;
- unconditional action residual H/D/A and L2 magnitude.

Move-surprise and sequential-persistence fields are excluded from the augmented closing model.

## Frozen strategies

1. **Generic raw baseline**: select bookmaker/outcome identity from generic raw-market expected closing delta and rank top 20% by that score.
2. **Unseen-book action ranker**: preserve the baseline bookmaker/outcome identity and rank the same candidates by the action-residual augmented expected closing delta for that identity.
3. **Unseen-book action selector**: allow the augmented model to replace bookmaker/outcome identity and rank by its own score. This is secondary.

Trade fraction, per-cutoff ranking, deterministic ties and CLV definitions are identical to Experiments 011–013.

## Primary promotion gate

All must pass:

1. rank-only incremental opportunity closing log-CLV versus baseline is positive with paired match-bootstrap CI above zero;
2. rank-only point lift is positive in at least three of four cutoffs;
3. no single held-out bookmaker supplies more than 40% of total positive incremental opportunity log-CLV.

## Structural checks

- action-residual conditional closing-delta MAE improvement has paired match-bootstrap CI above zero;
- conditional MAE improves in at least three of four cutoffs;
- closing-move hazard is reported but is not a mandatory gate because the action family was identified as an economic/directional carrier, while move surprise and persistence carried most timing information.

No folds, features, models, cutoffs, strategy rules or thresholds may be changed after the result is opened. Negative or concentrated transfer is valid evidence.