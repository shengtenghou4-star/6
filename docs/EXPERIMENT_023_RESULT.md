# Experiment 023 Result — Execution break-even envelope and adverse-fill audit

Status: **completed; residual-minus-raw point return remained positive across nearly the entire envelope grid, but no preregistered practical envelope cleared paired uncertainty, so execution validation remains false**.

Run: `29687978812`

Artifact digest: `sha256:0d6d6502820b6ec867ebabed7a7ca3a26d3ad8fd05e7b9632332cc9c2640cd89`

## Frozen reconstruction

The audit rebuilt the exact matched-budget policies used by Experiments 017 and 018:

- 59,816 candidate opportunities across 18,072 matches;
- 2,988 attempted selections per policy;
- raw-model bookmaker and outcome identity;
- raw positive-score top 5% and residual action-rank top 5% within cutoff;
- policy flags and prices frozen before outcomes were loaded;
- same-source execution-price completeness of 100% at 0h and 1h and 99.9983% at 2h and 3h.

## Full 64-cell point envelope

The grid crossed four delays, four exact fill rates and four outcome-blind fill mechanisms.

- residual-minus-raw point return was positive in **60 of 64** cells;
- residual standalone ROI was positive in **18 of 64** cells;
- raw standalone ROI was positive in **6 of 64** cells;
- all 16 zero-delay cells had positive incremental point return;
- positive standalone residual cells fell from 10/16 at 0h to 6/16 at 1h and 1/16 at both 2h and 3h.

The residual policy therefore retained a broad ranking advantage, but latency rapidly consumed its small standalone economic margin.

## Preregistered practical envelopes

All practical envelopes used 1-hour delay, 90% exact fill and 25 bps common slippage.

| Fill mechanism | Residual ROI | Residual profit | Incremental profit | Incremental 95% CI per opportunity | Pass |
|---|---:|---:|---:|---:|---:|
| common random | +0.267% | +7.19 units | +39.56 units | [-0.001430, +0.002578] | no |
| bookmaker-clustered outage | +0.098% | +2.62 units | +58.57 units | [-0.001212, +0.003058] | no |
| adverse-move rejection | -1.445% | -38.86 units | +27.46 units | [-0.001741, +0.002453] | no |
| highest-edge rejection | -1.804% | -48.51 units | +27.64 units | [-0.001878, +0.002860] | no |

Two ordinary-loss envelopes retained a small positive residual standalone return. Both adversarial rejection mechanisms erased it. The incremental point estimate stayed positive in all four envelopes, but every paired confidence interval crossed zero.

## Break-even interpretation

At 1h and 90% fill before the fixed 25 bps practical haircut:

- common random fill left 51.7 bps of residual standalone price tolerance;
- bookmaker-clustered outage left 34.7 bps;
- adverse-move rejection was already 120.6 bps below standalone break-even;
- highest-edge rejection was already 157.0 bps below standalone break-even.

After the 25 bps practical haircut, the common-random and bookmaker-clustered ledgers retained only 26.7 bps and 9.7 bps of additional standalone tolerance. Bootstrap intervals around every frontier remained wide and crossed zero.

## Concentration warning

Bookmaker and cutoff concentration stayed moderate in the practical envelopes, but the incremental advantage was heavily concentrated in the home outcome. Home supplied all positive incremental contribution in three of four practical mechanisms and about 90% in the bookmaker-clustered mechanism. This is another reason not to treat the positive point estimates as execution validation.

## Frozen gate

Passed:

- residual-minus-raw point return was positive in all four practical envelopes;
- common-random and bookmaker-clustered practical residual ROI point estimates were positive.

Failed:

- no practical paired incremental confidence interval had a lower bound above zero;
- adversarial rejection made residual standalone ROI negative;
- break-even-frontier confidence intervals crossed zero;
- outcome contribution was highly concentrated.

Therefore `execution_envelope_validated` is **false**.

## Supported interpretation

The residual ranker is not merely surviving one friendly friction assumption: it remained directionally better than the raw reference in 60/64 exact envelopes and under every preregistered practical fill mechanism. The economic margin is nevertheless thin. One hour of latency plus modest ordinary fill loss leaves only a small standalone profit, while informed rejection of the best or most adversely moved orders makes the policy unprofitable. Historical execution uncertainty remains too wide for a confirmatory profit claim.

The correct status remains **mechanism-supported and economically directional, with the execution bottleneck now quantified but not validated**. The running prospective campaign was not modified.
