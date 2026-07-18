# Experiment 010 Result — Modern Asian Handicap Residual Repricing

Status: **completed; strict structural replication failed on the 18-match locked test**.

## Source and sample

Verified public modern Asian Handicap sample:

- 90 matches
- 30 EPL, 30 LaLiga and 30 SerieA
- 107,446 timestamped quote updates
- 15 masked bookmaker codes
- 54 train / 18 validation / 18 locked-test matches
- 5,400 match/bookmaker/cutoff states, 1,080 in locked test
- no missing target or consensus states at the four frozen cutoffs
- no match outcomes used

The provider's maximum recorded timestamp remains a close marker `C`, not independently verified kickoff. Handicap is represented as absolute line magnitude because source sign orientation is not independently verified as home-oriented.

## Normal-action layers

Training:

- 3,240 states across 54 matches
- 1,705 mover states
- move rate `52.62%`

Locked-test diagnostics:

- 1,080 states across 18 matches
- move rate `49.54%`
- normal move-hazard Brier `0.213782`
- conditional line-delta MAE `0.04055` goals
- conditional home-share MAE `0.01479`

These diagnostics establish that the normal-action models executed on the modern AH representation; they were not themselves assigned a cross-source promotion gate in this experiment.

## Future three-hour move/no-move

Raw-market baseline:

- Brier `0.14351032`

Market plus frozen residuals:

- Brier `0.14816019`
- relative change **-3.24%**
- improved cutoffs **1/4**
- paired 18-match bootstrap improvement CI `[-0.01444227, 0.00607372]`

The residual hazard was worse overall and failed every preregistered promotion check.

Cutoff detail:

- C-24h: worse by `0.01350143` Brier
- C-12h: better by `0.00283056`
- C-6h: worse by `0.00521904`
- C-4h: worse by `0.00270959`

## Conditional future line/home-share repricing

Among 818 future-moving states across all 18 test matches:

- raw-market composite MAE `1.01279648`
- market plus residual composite MAE `1.00527138`
- relative improvement **0.743%**
- improved cutoffs **3/4**
- paired 18-match bootstrap improvement CI `[-0.02658818, 0.04196287]`

Separate component metrics:

- line MAE improved from `0.06811198` to `0.06708826` goals
- home-share MAE improved from `0.01753145` to `0.01742190`
- neither component worsened by more than the frozen 2% guardrail

The point estimate and three-cutoff stability were favorable, but the match-level confidence interval crossed zero. Therefore the conditional repricing gate failed.

## Strict promotion decision

Required:

1. future-move Brier improvement with CI above zero and at least 3/4 cutoffs;
2. conditional composite improvement with CI above zero and at least 3/4 cutoffs;
3. no material component degradation.

Observed:

- future-move gate: failed
- conditional composite point estimate: positive
- conditional cutoff stability: passed
- conditional bootstrap significance: failed
- component guardrails: passed

Overall modern AH structural replication: **not promoted**.

## Interpretation

The modern AH sample does not provide confirmatory support for the full residual-repricing mechanism under the frozen design. The hazard result is directionally negative; the conditional direction/magnitude result is mildly positive but too uncertain with only 18 locked-test matches.

This result does not overturn the much larger positive 1X2 repricing tests. It establishes that transfer to modern Asian Handicap data is currently unresolved and that the 90-match public sample is too small to rescue a weak or heterogeneous effect.

No model, cutoff, handicap orientation, feature or target may be changed and retested on these 18 opened matches as confirmatory evidence. A valid next AH test requires the unacquired larger corpus, a different untouched source, or prospective collection.

Workflow artifact digest: `sha256:e53c3ff3092a138485ff76741a8b300e1cb038f8aceccef2b0714bdb04fa0c5f`.
