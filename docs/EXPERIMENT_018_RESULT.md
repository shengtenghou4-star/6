# Experiment 018 Result — Matched-budget execution-friction diagnostic

Status: **completed; the residual policy preserved a broad directional advantage over the matched raw reference, but did not remain independently profitable in the practical scenario and the paired uncertainty intervals did not clear zero**.

Run: `29678230647`

Artifact digest: `sha256:2747e57af9c54e64d3a0cf83eaf29a30c7523e29de18108168ef4b93ea8789bd`

## Frozen comparison

Experiment 018 reconstructed the exact matched-budget policies from Experiment 017:

- 59,816 candidate opportunities;
- 2,988 attempted selections per policy before execution frictions;
- the raw model fixed bookmaker and outcome identity;
- the raw reference retained positive raw-score candidates at 5% per cutoff;
- the residual policy retained positive action-rank candidates at 5% per cutoff;
- policy flags and timestamp prices were frozen before outcomes were loaded.

The audited grid crossed four delays, four adverse-slippage levels and four base fill rates for 64 scenarios. Same-source execution-price completeness was 100% at 0h and 1h and 99.9983% at 2h and 3h.

## Four preregistered core scenarios

### 0h / 0 bps / 100% fill

- matched raw reference: `-22.31` units, **-0.747% ROI** across 2,988 fills;
- residual policy: `+16.89` units, **+0.565% ROI** across 2,988 fills;
- residual-minus-raw improvement: `+39.20` units;
- incremental return per full opportunity: `+0.0006553`;
- paired match-bootstrap 95% interval: `[-0.0016759, 0.0028718]`;
- maximum positive-book contribution share: `40.80%`.

### 1h / 25 bps / 90% fill

- matched raw reference: `-35.21` units, **-1.452% ROI** across 2,425 fills;
- residual policy: `-30.21` units, **-1.250% ROI** across 2,416 fills;
- residual-minus-raw improvement: `+5.00` units;
- incremental return per full opportunity: `+0.0000836`;
- paired match-bootstrap 95% interval: `[-0.0019968, 0.0018493]`;
- maximum positive-book contribution share: `47.06%`.

### 2h / 50 bps / 75% fill

- matched raw reference: `-112.23` units, **-5.901% ROI** across 1,902 fills;
- residual policy: `-54.14` units, **-2.868% ROI** across 1,888 fills;
- residual-minus-raw improvement: `+58.09` units;
- incremental return per full opportunity: `+0.0009711`;
- paired match-bootstrap 95% interval: `[-0.0007873, 0.0025902]`;
- maximum positive-book contribution share: `28.13%`.

### 3h / 100 bps / 50% fill

- matched raw reference: `-39.61` units, **-3.307% ROI** across 1,198 fills;
- residual policy: `-8.67` units, **-0.757% ROI** across 1,145 fills;
- residual-minus-raw improvement: `+30.94` units;
- incremental return per full opportunity: `+0.0005173`;
- paired match-bootstrap 95% interval: `[-0.0008134, 0.0018968]`;
- maximum positive-book contribution share: `47.23%`.

## Full-grid picture

Across all 64 scenarios:

- residual-minus-raw incremental point return was positive in **58 of 64** scenarios;
- residual standalone ROI was positive in **15 of 64** scenarios;
- matched raw standalone ROI was positive in **3 of 64** scenarios;
- only **1 of 64** paired incremental confidence intervals had a lower bound above zero;
- the median incremental return per opportunity was `+0.000690`;
- the mean incremental return per opportunity was `+0.000622`;
- 54 of 64 scenarios kept the maximum positive-book contribution share at or below 50%.

The broad sign consistency supports a real ranking advantage over the matched raw reference. It does not establish executable profitability because most frictional residual returns were still negative and nearly all paired confidence intervals crossed zero.

## Frozen diagnostic gate

Passed:

- residual zero-friction ROI point estimate was positive;
- incremental point return was positive in all four core scenarios;
- practical positive-profit concentration remained below 50%.

Failed:

- residual practical-scenario ROI was negative;
- zero-friction residual-minus-raw paired confidence interval did not clear zero;
- practical residual-minus-raw paired confidence interval did not clear zero.

Therefore the frozen `friction_robust` gate is **false**.

## Supported interpretation

The matched-budget residual ranker appears to choose materially better opportunities than the raw-score reference: its incremental point estimate stayed positive across most of a demanding friction grid and across every preregistered core scenario. Execution friction nevertheless erased the residual policy's small standalone historical profit under the practical assumptions, while uncertainty remained too wide for a confirmatory incremental-return claim.

The correct status is **mechanism-supported and economically directional, but not execution-validated**. No live betting authorization or profit claim follows. The running timestamped prospective 5% shadow remains the decisive next evidence source.