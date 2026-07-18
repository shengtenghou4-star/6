# Hypothesis Registry

Use this file to keep research hypotheses explicit, testable, and replaceable.

A hypothesis is not a rule. It remains alive only while evidence justifies further work.

## Status labels

- `idea`
- `queued`
- `testing`
- `supported`
- `partially-supported`
- `rejected`
- `superseded`

## H001 — Conditional bookmaker abnormality may contain incremental information

**Status:** queued

**Claim**

After conditioning on observable market state and context, some bookmaker actions or non-actions that deviate from expected behavior may carry incremental information about future match outcomes or economically relevant states.

**Why it is plausible**

Bookmakers and market participants may differ in information, customer flow, risk constraints, reaction speed, and pricing behavior. Some residual behavior may therefore be informative after obvious market movements are controlled for.

**Main alternative explanations**

- mechanical risk management
- customer-flow imbalance
- stale or delayed quotes
- source latency
- market-specific rules
- random noise
- omitted public information

**Minimum falsifiable test**

1. Build a baseline model using information observable at decision time.
2. Build an expected-bookmaker-behavior model from historical states.
3. Generate residual / abnormal-behavior features.
4. Test whether adding those features improves strict time-based out-of-sample performance beyond the baseline.
5. Check stability across bookmakers, competitions, time periods, and market regimes.

**Kill criteria**

Downgrade or reject if apparent gains disappear under leakage audit, new time periods, realistic market segmentation, or replication.

## H002 — A superior primary target may exist

**Status:** idea

The project should actively search for research targets that are easier to measure or more economically valuable than bookmaker-abnormality signals. Candidate targets may include other forms of market microstructure, information diffusion, conditional mispricing, execution opportunities, or combinations not yet specified.

This hypothesis exists to prevent H001 from becoming doctrine.
