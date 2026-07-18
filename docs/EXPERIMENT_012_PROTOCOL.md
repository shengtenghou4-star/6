# Experiment 012 — Residual attribution and shuffled-null protocol

## Status

Preregistered before opening the audit output.

This experiment uses the already opened Experiment 011 historical test period. It is a diagnostic falsification and mechanism-attribution audit, not a new untouched alpha test.

## Frozen reconstruction

- Beat The Bookie hourly 1X2 tensor
- same chronological train/validation/test split as Experiments 002–011
- same eight named bookmaker slots
- signal cutoffs T-48h, T-24h, T-12h and T-6h
- residual observed at the next hourly tensor state
- target is the same bookmaker's final valid H/D/A state at index 71
- same raw-market baseline features
- same fixed HGB classifier/regressors
- same one-book/outcome-per-match/cutoff selection
- same top-20% trade fraction and deterministic ties

## Residual variants

Every real variant adds only the stated residual family to the identical raw-market baseline.

1. **Move surprise**: absolute/signed move surprise, no-move surprise and unexpected-move surprise.
2. **Contemporaneous action**: conditional and unconditional H/D/A action residuals and their L2 magnitudes.
3. **Sequential persistence**: prior-cutoff surprise and action-residual aggregates.
4. **Full residual**: all Experiment 011 residual features.
5. **Shuffled residual null**: the full residual vector is jointly permuted within bookmaker × cutoff, separately in validation and test. This preserves its marginal distribution and internal correlation while breaking match-level alignment.

## Outputs

For each variant:

- closing move/no-move Brier versus the common raw-market baseline
- conditional closing H/D/A delta MAE versus baseline
- paired match-bootstrap intervals
- frozen top-20% closing log-odds and fair-probability CLV
- paired incremental opportunity log-CLV versus baseline

## Frozen adversarial checks

The audit passes only if all are true:

1. the full residual model reproduces Experiment 011's promoted move-hazard result;
2. the full residual model reproduces Experiment 011's promoted conditional-delta result;
3. the full residual model reproduces positive incremental closing-CLV with CI above zero;
4. the full residual point improvement exceeds the shuffled null for hazard;
5. the full residual point improvement exceeds the shuffled null for conditional delta;
6. the full residual point incremental CLV exceeds the shuffled null;
7. the shuffled null incremental CLV CI includes zero;
8. at least one interpretable residual family has positive point lift in hazard, conditional delta and incremental CLV.

No thresholds, model settings, cutoffs, family definitions or trade rules may be changed after the result is opened. A failed audit is valid evidence against the current interpretation.