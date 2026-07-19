# Experiment 017 Result — Matched-budget historical return diagnostic

Status: **completed; residual policy had positive point return and beat the matched raw reference, but uncertainty intervals crossed zero**.

Run: `29677444272`

Artifact digest: `sha256:91b74781bb7bc71b732d7e4abbea94f1c3a35a66dcaef48400af630e0cc0c3f3`

## Frozen comparison

Both policies used the same raw-model-selected bookmaker/outcome candidate universe and retained exactly 5% within each cutoff:

- 59,816 opportunities;
- 2,988 selections per policy;
- selected prices were bound before outcomes were loaded;
- no bookmaker, outcome or cutoff was deleted.

## Realized return

### Matched raw-score reference

- total profit: `-22.31` units;
- ROI: **-0.747%**;
- match-bootstrap 95% interval: `[-6.586%, 5.893%]`;
- 2,353 unique selected matches.

### Residual rank policy

- total profit: **+16.89** units;
- ROI: **+0.565%**;
- match-bootstrap 95% interval: `[-5.324%, 6.930%]`;
- 2,416 unique selected matches;
- positive-profit bookmaker concentration: `48.34%` maximum share.

### Residual minus raw

- point profit improvement: **+39.20 units**;
- incremental return per full opportunity: `+0.0006553`;
- paired match-bootstrap 95% interval: `[-0.0015619, 0.0026306]`;
- trade-set Jaccard overlap: `48.92%`;
- where both selected, bookmaker and outcome identity were identical by construction.

## Residual ROI by cutoff

- T-48h: `+4.295%` across 491 selections;
- T-24h: `+1.213%` across 745 selections;
- T-12h: `+2.199%` across 851 selections;
- T-6h: `-3.546%` across 901 selections.

The residual policy was positive at three of four cutoffs. The frozen protocol does not authorize deleting T-6h after observing this result.

## Frozen diagnostic gate

Passed:

- residual ROI point estimate positive;
- positive in at least three of four cutoffs;
- positive profit was not more than 50% attributable to one bookmaker.

Failed:

- residual standalone ROI confidence interval did not clear zero;
- residual-minus-raw paired confidence interval did not clear zero.

Therefore the frozen `economically_encouraging` gate remains **false**.

## Supported interpretation

Capacity matching changed the picture materially: the selective residual policy moved the point estimate from a matched raw loss to a small residual profit and improved profit by 39.20 units. The direction is promising, but the sample remains too noisy to establish either standalone profitability or incremental return with statistical confidence.

No confirmatory profit claim or live execution authorization follows. The already-deployed timestamped prospective 5% challenger is the correct next test.