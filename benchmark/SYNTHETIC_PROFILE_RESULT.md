# Synthetic MARB profile result

Status: **completed; benchmark mechanics recovered the known residual signal, while simulated return remained unvalidated**.

Run: `29694632368`

Artifact digest: `sha256:f8114252495f9ac1e4755e10bc216dcad67ad0d425eaffc0b2a9871631b89015`

## Frozen simulation

The profile generated 12,000 independent fixed-identity opportunities across:

- eight synthetic pricing agents;
- three fixed instruments;
- T-48, T-24, T-12 and T-6 horizons;
- ten raw-score baseline bins;
- a known residual coefficient of `+0.12` in the future same-agent price-quality target;
- a realized-return variable generated independently of the price-quality mechanism.

The residual score reranked the same preassigned agent and instrument. It could not change candidate identity.

## Mechanism recovery

The within-stratum standardized residual-uplift slope was:

- point estimate: `+0.120512`;
- bootstrap 95% interval: `[+0.107430,+0.133668]`;
- known generating coefficient: `+0.12`.

The highest residual-dose decile exceeded the lowest by `+0.427146` future-price-quality units.

## Alignment placebo

Across 1,000 within-stratum circular-shift placebos:

- empirical upper-tail p-value: `0.000999`;
- placebo 99th-percentile slope: `+0.013139`;
- observed slope: `+0.120512`.

The benchmark therefore distinguished the correctly aligned abnormal action from residual values attached to the wrong synthetic opportunities while preserving strata and residual-score distribution.

## Distribution

The recovered slope was positive for:

- 8/8 synthetic agents, ranging from `+0.091150` to `+0.133929`;
- 3/3 instruments;
- 4/4 horizons, ranging from `+0.106080` to `+0.152897`;
- every leave-one-agent-out sample.

## Economic separation

The independent realized-return variable produced:

- raw top-5% point return: `+0.053053`;
- residual top-5% point return: `+0.032704`;
- paired contribution interval per opportunity: `[-0.003519,+0.001251]`.

Execution validation remained false. This is intentional: the simulation demonstrates that MARB can recover a price-quality mechanism without mechanically manufacturing an economic claim.

## Evidence boundary

This result validates implementation behavior under a known data-generating process. It is not an independent empirical replication, does not show transport beyond football data, and does not raise the reference project above `replicated_historical` or `prospective-transfer pending`.
