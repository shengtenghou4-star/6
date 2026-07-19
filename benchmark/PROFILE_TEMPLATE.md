# MARB domain profile template

## Profile identity

- Profile name:
- Version:
- Owner/maintainer:
- Status: proposed / implemented / executed / historical replication / prospective validation
- Empirical or simulation-only:

## Research question

State one falsifiable sentence linking abnormal agent action to a later same-agent target.

## Core objects

- **Entity:**
- **Agent:**
- **Instrument:**
- **Observation time:**
- **Observed action:**
- **Expected action:**
- **Action residual:**
- **Raw candidate score:**
- **Residual candidate score:**
- **Future same-agent target:**

## Chronology contract

Document the earliest availability time of every feature family, revisions/corrections, target maturity rule, train/test boundary and entity-cluster split. List all forbidden post-event fields.

## Identity contract

Explain how the raw model fixes agent and instrument identity. State whether the augmented model can change either identity. Any identity-changing task must be reported separately.

## Data sources and rights

List sources, access dates, licenses/terms, retention constraints and whether redistribution is allowed. Identify any source that an external reviewer cannot independently obtain.

## Historical split

- Training interval:
- Validation interval:
- Test interval:
- Entity count:
- Opportunity count:
- Agent count:
- Instrument count:
- Horizons:

## Normal-action model

Describe movement hazard, conditional action model, calibration, missing-state rules and model-free baselines.

## Mechanism endpoint

Define the later same-agent price-quality metric and justify why it measures the hypothesized channel.

## Structure-preserving placebo

Specify exactly what is preserved and what alignment is broken. Freeze replicate count, random seed, grouping and upper-tail threshold.

## Threshold-free analysis

Specify baseline strata, residual standardization, slope estimator, cluster unit, dose bins and confidence interval method.

## Distribution checks

Freeze required agent, instrument, horizon, calendar and source/provider summaries. Define leave-one-group-out and concentration gates.

## Economic conversion

Define exact capacity, binding time, payoff, uncertainty and prohibited retrospective deletions.

## Execution stress

Define delay, slippage, fill mechanisms, informative rejection, capacity and validation gate.

## Deployment support

Define historical-versus-deployment diagnostics and the rule for activating a parallel challenger without altering the original stream.

## Prospective protocol

Record activation time, closing time, immutable ledger path, target maturity rule, volume gates, uncertainty gate, stability gates and concentration gates.

## Evidence-tier rule

State the maximum tier the current design can support and what additional evidence is needed for the next tier.

## Prohibited claims

List conclusions that cannot be made from this profile, even after a positive point estimate.

## Reproduction command

```bash
# exact commands here
```

## Frozen-signature block

- Profile SHA-256:
- Code commit:
- Model artifact SHA-256:
- Activation timestamp:
- Notes: