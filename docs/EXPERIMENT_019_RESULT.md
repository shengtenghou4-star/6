# Experiment 019 Result — Temporal stability and residual-uplift placebo audit

Status: **completed; match-specific residual alignment strongly improved closing-price quality over a baseline-preserving placebo, but realized-profit validation still failed**.

Run: `29684033482`

Artifact digest: `sha256:7e2dbe3b6171ce72ca89cbc690edf25ce8aeb57192161d07eb11fa7a392ff25f`

## Frozen evidence

The audit reused the exact Experiment 017 settled ledgers:

- 59,816 opportunities;
- 18,072 unique matches;
- 2,988 selections per policy;
- test dates from 2016-09-01 through 2016-11-19;
- identical raw-selected bookmaker/outcome candidate identity;
- no model refit or post-result bookmaker, cutoff, outcome or calendar deletion.

Observed results were reproduced exactly:

- matched raw profit: `-22.31` units;
- residual profit: `+16.89` units;
- residual-minus-raw profit: `+39.20` units;
- residual-minus-raw selected log-CLV sum: `+9.3142`.

## Baseline-preserving residual-uplift placebo

Each of 4,000 fixed-seed replicates preserved every baseline score and candidate identity, circularly shifted only `residual_uplift` within chronological bookmaker × cutoff groups, reconstructed the score as baseline plus shifted uplift, and reselected the exact 5% capacity.

### Closing-price quality

- observed residual selected log-CLV sum: `146.2887`;
- placebo mean: `128.6102`;
- placebo 95th percentile: `134.8843`;
- empirical upper-tail p-value: **0.00025**.

For residual minus raw:

- observed incremental log-CLV sum: `+9.3142`;
- placebo mean incremental log-CLV sum: `-8.3643`;
- empirical upper-tail p-value: **0.00025**.

The observed ranker beat all 4,000 baseline-preserving circular-shift placebos on both selected and incremental closing log-CLV.

### Realized return

- observed residual profit: `+16.89` units;
- placebo mean profit: `-33.74` units;
- placebo 95th percentile: `+38.56` units;
- empirical upper-tail p-value: **0.1212**.

The same p-value applies to observed residual-minus-raw profit because the raw reference is fixed. Realized return therefore did not beat the frozen placebo threshold.

## Temporal stability

Across 12 calendar weeks:

- incremental log-CLV was positive in **8 of 12** weeks;
- incremental profit was positive in **6 of 12** weeks;
- after omitting any one week, incremental log-CLV remained positive, with a minimum remaining sum of `+5.0819`;
- after omitting the most influential week, incremental profit fell to `-0.29` units.

The price-quality effect is not attributable to one isolated week. The profit point estimate nearly disappears when one influential week is removed.

## Cluster robustness

### Incremental log-CLV per opportunity

- point estimate: `+0.0001557`;
- match-cluster 95% interval: `[-0.0000668, +0.0003696]`;
- calendar-day interval: `[-0.0000508, +0.0003679]`;
- calendar-week interval: `[-0.0000502, +0.0003537]`.

### Incremental return per opportunity

- point estimate: `+0.0006553`;
- match-cluster 95% interval: `[-0.0014961, +0.0027747]`;
- calendar-day interval: `[-0.0016807, +0.0030750]`;
- calendar-week interval: `[-0.0015111, +0.0030050]`.

All cluster intervals still cross zero.

## Frozen gate

- `mechanism_falsification_passed`: **true**;
- `profit_validation_passed`: **false**.

## Supported interpretation

This is stronger than merely observing that the residual policy ranked historical opportunities well. When the residual uplift is attached to the wrong matches while baseline information, bookmaker/cutoff structure, score distribution and trade capacity are preserved, the closing-price advantage collapses. The correct match-specific residual alignment therefore carries real information about subsequent same-book repricing.

That information has not yet been shown to generate statistically stable realized profit. The project's strongest current claim is now: **the abnormal-action residual mechanism survives a demanding baseline-preserving falsification test as a price-quality signal, while economic execution and profit remain unvalidated**.

The untouched seven-day prospective campaign remains the confirmatory test of transfer.