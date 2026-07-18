# Experiment 008 Result — Named-Book Residual Repricing and CLV Proxy

Status: **completed; repricing layers passed, strict residual-specific CLV promotion failed**.

## Locked-test sample

Beat The Bookie named-bookmaker tensor, using the eight frozen bookmakers and T-48h/T-24h/T-12h/T-6h signals:

- 409,591 eligible bookmaker-level test rows
- 18,120 unique test matches
- 59,895 match/cutoff strategy opportunities after selecting one bookmaker/outcome signal
- 11,977 top-20% trades
- future-price benchmark: same bookmaker and outcome three hours after the residual became observable
- no match outcomes used

## Incremental repricing models

### Future move/no-move hazard

- raw-market baseline Brier: `0.1676271941`
- market plus residuals Brier: `0.1668827531`
- relative improvement: **0.4441%**
- paired match-bootstrap improvement CI: `[0.00061530, 0.00088792]`
- improved cutoffs: **3/4**

The hazard gate passed. T-48h was effectively flat/slightly negative (`-0.0000152` Brier improvement); T-24h, T-12h and T-6h improved.

### Conditional future H/D/A repricing

- raw-market baseline MAE: `0.0106633115`
- market plus residuals MAE: `0.0106200564`
- relative improvement: **0.4056%**
- paired match-bootstrap improvement CI: `[0.00003496, 0.00005126]`
- improved cutoffs: **4/4**

The conditional repricing gate passed.

## Frozen top-20% CLV strategy

### Raw-market baseline strategy

- mean trade log-odds CLV: `0.0142538632`
- mean trade fair-probability CLV: `0.0053897094`
- positive log-CLV bootstrap CI: `[0.01311166, 0.01534021]`
- positive cutoffs: **4/4**

### Residual-augmented strategy

- mean trade log-odds CLV: `0.0147550172`
- mean trade fair-probability CLV: `0.0056487168`
- positive log-CLV bootstrap CI: `[0.01362216, 0.01591895]`
- positive cutoffs: **4/4**

Residual-augmented mean trade log-CLV by cutoff:

- T-48h: `0.00722498`
- T-24h: `0.00782306`
- T-12h: `0.01530006`
- T-6h: `0.02410365`

Both frozen strategies selected prices that subsequently shortened materially.

## Strict incremental residual CLV comparison

The preregistered economic promotion required the residual strategy to outperform the already strong raw-market strategy on per-opportunity log-CLV with a match-bootstrap interval entirely above zero.

Observed residual-minus-baseline per-opportunity log-CLV:

- point estimate: `0.0001002141`
- paired match-bootstrap CI: `[-0.00005668, 0.00026713]`

The point estimate was positive, but the interval crossed zero. Therefore the residual-specific incremental CLV condition failed.

## Promotion checks

Passed:

- residual repricing hazard gate
- residual conditional repricing gate
- residual strategy mean trade log-CLV positive with CI above zero
- residual strategy fair-probability CLV positive
- residual strategy positive in 4/4 cutoffs

Failed:

- residual strategy per-opportunity log-CLV significantly exceeds raw-market strategy

Overall strict promotion: **failed**.

## Interpretation

The experiment establishes three useful facts:

1. the named-book raw market contains a strong short-horizon price-drift signal;
2. abnormal residuals improve future repricing prediction beyond that rich raw market state;
3. the frozen residual strategy has positive historical CLV, but its incremental CLV advantage over the already strong raw-market strategy is not statistically established under the preregistered top-20% rule.

This result must not be described as residual-driven profit. It supports a named-book historical market-price CLV phenomenon and a real residual repricing signal, while leaving residual-specific economic lift unresolved.

The next valid audit may apply the already frozen strategy to realized match returns without changing its rules, but that audit is diagnostic because the underlying outcome period has already been opened elsewhere. A genuinely confirmatory profit claim still requires untouched prospective or independent named-book data with executable timestamps, fills and limits.

Workflow artifact digest: `sha256:bf572938b98b79fa1f0f2af4d9677ca7374472439e5a259bd084b7b817e654e9`.
