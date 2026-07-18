# Experiment 012 — Residual attribution and shuffled-null result

Status: **adversarial audit passed**

This is a diagnostic falsification and attribution study on the already opened Experiment 011 historical test period. It is not a new untouched alpha claim.

## Locked scope

- 18,072 test matches
- 403,248 bookmaker/cutoff rows
- 59,816 match/cutoff strategy opportunities
- eight named bookmaker slots
- same final same-book closing target as Experiment 011

## Full residual reproduction

The full residual model exactly reproduced Experiment 011's promoted result:

- closing-move Brier improvement: `0.00151669`, CI low `0.00133373`
- conditional closing-delta MAE improvement: `0.00001939`, CI low `0.00001159`
- incremental opportunity log-CLV: `0.00035063`
- incremental CLV CI: `[0.00002516, 0.00067648]`

## Shuffled residual null

The full residual vector was jointly permuted within bookmaker × cutoff, preserving its distribution and internal correlation while breaking match-level alignment.

The shuffled null failed:

- closing-move Brier change: `-0.00005771`
- conditional MAE improvement: `0.00000500`, CI crosses zero
- incremental opportunity log-CLV: `-0.00004466`
- incremental CLV CI: `[-0.00032042, 0.00023376]`

Therefore the promoted result is not explained by merely adding extra variables with the same bookmaker/cutoff distributions. The residual vector must be aligned to the correct match state.

## Residual-family attribution

| Residual family | Hazard improvement | Conditional MAE improvement | Incremental opportunity log-CLV | CLV CI |
|---|---:|---:|---:|---:|
| Move surprise | 0.00029981 | 0.00000506 | -0.00008743 | [-0.00037280, 0.00019626] |
| Contemporaneous action residual | 0.00015786 | 0.00001667 | **0.00062859** | **[0.00031390, 0.00094729]** |
| Sequential persistence | 0.00101991 | 0.00000542 | -0.00018674 | [-0.00046864, 0.00008306] |
| Full residual | **0.00151669** | **0.00001939** | 0.00035063 | [0.00002516, 0.00067648] |

## Mechanism finding

The families separate cleanly:

- **Sequential persistence** is the main carrier of move/no-move timing information, but it does not create positive closing-CLV lift by itself.
- **Move surprise** also helps the closing-move hazard, but does not improve the economic ranking.
- **Contemporaneous conditional and unconditional H/D/A action residuals are the economic carrier.** This family alone improves hazard, conditional movement and closing CLV, with an incremental CLV point estimate larger than the full combined model.
- Combining all residual families improves structural prediction most, but the extra timing/persistence variables dilute some of the action-residual family's CLV ranking power.

## Decision

The match-level abnormal residual mechanism survives the shuffled-null attack. The economically relevant component is not simply that a bookmaker moved unexpectedly or showed persistent abnormality. It is the **direction and magnitude of the bookmaker's actual quote action relative to its expected action**.

This supports treating contemporaneous action residuals as the primary candidate signal for future prospective scoring, while move-surprise and persistence features should be treated mainly as timing/risk context rather than assumed economic alpha.

No profit, execution, limits or future-performance claim is made.

Artifact digest: `sha256:24467b6d6218ecac1129944dbb25ccc78648e3be159d909756cfdc3b4a95954a`
