# Experiment 006 Result — Independent Exact-Timestamp Residual Outcome Information

Status: **completed; conditional movement replicated, residual outcome-information gate failed**.

## Independent normal-action layers

Source: `eladsil/football-games-odds`, with explicit nanosecond as-of reconstruction and no cross-book features.

Reconstructed source:

- 166,977 eligible match/cutoff states
- 31,882 matches
- locked test: 12,122 states across 2,150 matches

### Conditional movement gate

Locked-test mover states:

- 3,130 mover states across 1,725 matches
- cutoff-mean baseline MAE: `0.01034771`
- fixed HGB conditional-movement MAE: `0.01017075`
- relative MAE improvement: **1.71%**
- improved cutoffs: **6/6**
- paired match-bootstrap improvement CI: `[0.00013575, 0.00022367]`

All preregistered conditional-movement checks passed.

Together with Experiment 004, the independent source now supports both normal-action layers:

1. move/no-move hazard;
2. conditional direction/magnitude after a move.

## Residual outcome test

Residuals were generated for validation/test before match results were loaded.

Outcome-layer sample:

- validation: 4,540 match/cutoff records across 788 matches
- locked test: 12,122 records across 2,150 matches

### Direct contemporaneous `t+1` market

- log loss: `1.09262163`
- multiclass Brier: `0.66276597`
- accuracy: `0.367514`

### Fitted market-only baseline

- log loss: `1.09204265`
- multiclass Brier: `0.66184369`
- accuracy: `0.360419`

### Market plus frozen residual features

- log loss: `1.09768872`
- multiclass Brier: `0.66478030`
- accuracy: `0.360914`

Incremental comparison:

- fitted-market minus augmented log loss: `-0.00564607`
- fitted-market minus augmented Brier: `-0.00293661`
- paired match-bootstrap log-loss improvement CI: `[-0.00931182, -0.00206751]`
- improved cutoffs: **1/6**
- augmented model also failed to beat the direct market reference

Every residual outcome-information promotion check failed.

## Interpretation

The result independently confirms that the project can learn normal quote behavior and abnormal deviations in a second dataset.

It also independently rejects the broad claim that the tested residual vector, fed globally into a fixed outcome model, improves H/D/A probabilities beyond the contemporaneous market. The negative result is larger than in Experiment 005 and is statistically stable across matches.

Therefore:

- normal bookmaker/market behavior predictability: supported;
- conditional quote movement predictability: supported;
- broad global residual-to-match-result alpha: not supported by Experiments 005 or 006;
- profitability: not tested and not promoted.

The next scientifically valid question is whether abnormal residuals predict **subsequent market repricing** or closing-line movement. That target is closer to the quote-generation mechanism and can support a later CLV/economic test without pretending the failed broad outcome model succeeded.

Workflow artifact digest: `sha256:19abc466e0166887941e21a1cc944742462cbc7c1dca9c2328082c5ed580fd3b`.
