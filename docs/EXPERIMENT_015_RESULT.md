# Experiment 015 Result — Execution-friction stress test

Status: **completed; historical execution envelope not promoted**.

Run: `29676230242`

Artifact digest: `sha256:4fda6733c7345c15263564f6093026c422dc20c549aaa4e2211e749ffa4afee3`

## Scope

The experiment preserved the frozen raw-market candidate identity and used action residuals only to rerank opportunities. It reconstructed 59,816 match/cutoff opportunities across 18,072 matches, with 11,961 attempted trades per strategy, then evaluated 64 deterministic execution scenarios:

- latency: 0, 1, 2, 3 hours;
- adverse slippage: 0, 25, 50, 100 bps;
- base fill rate: 100%, 90%, 75%, 50%;
- lower fill probability after adverse price movement.

Delayed execution-price completeness was at least 99.996% at every horizon.

## Frozen core scenarios

| Scenario | Baseline ROI/fill | Rank-only ROI/fill | Incremental return/opportunity | 95% interval | Largest positive book contribution |
|---|---:|---:|---:|---:|---:|
| 0h / 0 bps / 100% | -3.204% | -2.791% | +0.000827 | [-0.002563, 0.004111] | 39.37% |
| 1h / 25 bps / 90% | -4.650% | -4.304% | +0.000601 | [-0.002449, 0.003430] | 55.89% |
| 2h / 50 bps / 75% | -5.778% | -5.507% | +0.000380 | [-0.002446, 0.003111] | 44.76% |
| 3h / 100 bps / 50% | -4.179% | -5.330% | -0.000952 | [-0.003060, 0.001056] | 55.50% |

## Decision

All six preregistered promotion checks failed:

- the rank-only strategy was not profitable even with zero modeled friction;
- its incremental return interval crossed zero in both zero-friction and practical scenarios;
- the practical scenario remained negative;
- incremental point lift did not remain positive across all four core scenarios;
- practical positive contribution was too concentrated in one bookmaker.

The residual reranking overlay improved the point estimate under the first three core scenarios and reduced zero-friction loss by 49.44 units, but the improvement was not statistically established and disappeared under the harshest core scenario.

## Supported conclusion

The abnormal-action residual contains genuine repricing information, but the frozen rank-only implementation does **not** currently support a positive executable-return claim. The bottleneck is no longer whether residual information exists; it is converting that information into sufficiently selective candidate construction and pricing edge.

No post-result rule deletion or outcome-specific optimization is authorized from this experiment. The untouched prospective campaign remains the confirmatory path.