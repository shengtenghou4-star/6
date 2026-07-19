# Experiment 016 Result — Validation-only selective abstention

Status: **completed; selective policy not promoted under the preregistered gate**.

Run: `29676728049`

Artifact digest: `sha256:bb2afe8e8892b76d687dcac8fcc2cb9ac79ee41e680296028ddc9181da8b1715`

## Frozen selection

The validation-only calibration selected:

- family: `positive_rank_score`;
- trade fraction: 5% within each cutoff;
- calibration trades: 554;
- calibration mean same-book closing log-CLV: `0.06568`;
- calibration match-bootstrap 95% interval: `[0.04924, 0.08470]`;
- positive calibration cutoffs: 4/4.

No match outcomes were used for calibration.

## Historical test result

The frozen policy produced:

- 2,988 trades from 59,816 opportunities;
- 2,416 unique traded matches;
- mean trade closing log-CLV: **0.04896**;
- match-bootstrap 95% interval: **[0.04258, 0.05557]**;
- positive mean closing log-CLV at all four cutoffs.

By cutoff:

- T-48h: `0.04557` across 491 trades;
- T-24h: `0.04509` across 745 trades;
- T-12h: `0.05702` across 851 trades;
- T-6h: `0.04639` across 901 trades.

## Why the frozen gate rejected it

Two preregistered checks failed:

1. Compared with the raw-market 20% strategy, the 5% selective policy had lower total opportunity log-CLV (`-0.003798` incremental per opportunity). This is a capacity comparison: the selective policy generated much higher quality per trade but placed one quarter as many trades.
2. The largest positive bookmaker contribution was `53.82%`, above the frozen 50% concentration ceiling.

The other four checks passed: a policy existed, test trade CLV was positive, its confidence interval was above zero, and all four cutoffs were positive.

## Decision

The exact Experiment 016 gate is not changed after results. Therefore the policy is **not promoted** by this experiment.

Supported interpretation:

- strong selective closing-price quality replicated out of calibration;
- selectivity materially increased per-trade CLV;
- the experiment did not establish superior total opportunity capacity versus a four-times-larger baseline;
- bookmaker concentration remains a live robustness concern;
- no realized-profit claim follows from closing CLV alone.

A later prospective comparison may evaluate this frozen 5% challenger against a matched 5% raw-market baseline, but the historical gate is not retroactively rewritten.