# Experiment 021 Result — Threshold-free residual dose-response audit

Status: **completed; residual uplift shows a strong threshold-free dose relationship with subsequent same-book closing-price quality, while realized-return validation remains negative**.

Run: `29685372659`

Artifact digest: `sha256:0fa5d2570220bbc8c61f4ad9173f7fa3c2b9ca3abc0d2daa3b1e52ebe6622740`

## Frozen evidence

The audit used every Experiment 017 raw-model-selected opportunity:

- 59,816 opportunities;
- 18,072 matches;
- 2016-09-01 through 2016-11-19;
- fixed bookmaker/outcome candidate identity;
- no model refit, threshold selection, bookmaker deletion, cutoff deletion or outcome deletion.

Raw baseline scores were split into 15 equal-count bins within cutoff. Residual uplift was then standardized and divided into ten dose bins within bookmaker × cutoff × baseline-score-bin strata.

## Closing-price dose response

For same-book closing log-CLV:

- within-stratum slope per one standard deviation of residual uplift: `+0.004430`;
- event-cluster 95% interval: `[+0.003316, +0.005515]`;
- highest-dose minus lowest-dose mean log-CLV: `+0.014581`;
- event-cluster 95% interval: `[+0.010072, +0.018991]`.

Both observed statistics exceeded every one of 4,000 chronological within-stratum circular-shift placebos:

- slope empirical upper-tail p: `0.00025`;
- top-minus-bottom empirical upper-tail p: `0.00025`.

The corresponding fair-probability CLV relationship was also positive:

- within-stratum slope: `+0.001303`;
- top-minus-bottom: `+0.004588`.

The ten-bin profile is graded but not perfectly monotonic at every adjacent step, as expected under sampling noise. Mean log-CLV rose from `0.00709` in the lowest dose bin to `0.02167` in the highest, with the strongest intermediate bin at `0.02423`.

## Cutoff stability

Top-minus-bottom closing log-CLV was positive at all four cutoffs:

- T-48: `+0.02005`;
- T-24: `+0.00778`;
- T-12: `+0.01657`;
- T-6: `+0.01539`.

The within-stratum slope was likewise positive at every cutoff.

## Realized return

Return did not exhibit the same reliable continuous relationship:

- return slope: `+0.000013`;
- event-cluster 95% interval: `[-0.012482, +0.012785]`;
- slope placebo p: `0.4976`;
- top-minus-bottom return: `+0.03532` per opportunity;
- event-cluster interval: `[-0.02057, +0.09078]`;
- top-minus-bottom placebo p: `0.0947`.

Return contrasts were positive at T-48, T-24 and T-12 but negative at T-6. The economic result is therefore unstable and does not validate profit.

## Frozen gate

- `dose_response_mechanism_passed`: **true**;
- `realized_profit_validation_passed`: **false**.

## Supported interpretation

The residual mechanism is not merely a consequence of choosing a convenient top-5% threshold. After conditioning narrowly on raw score, bookmaker and cutoff, larger match-specific residual uplift is associated with materially better subsequent same-book prices across the full opportunity universe. Breaking the match alignment destroys that relationship.

This substantially strengthens the mechanism claim: abnormal bookmaker-action residuals contain graded information about future repricing. It still does not show that the signal survives market friction strongly enough to generate stable realized profit. The untouched prospective test and the newly identified domain-shift repairs remain necessary.