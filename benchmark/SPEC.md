# Market Action Residual Benchmark

## Purpose

The Market Action Residual Benchmark (MARB) generalizes the project's central question:

> After conditioning on the observable market state, does an agent's abnormal action contain information about its own future price?

The first profile uses multi-book football odds, but the contract is intended to transfer to prediction markets, exchange market makers, insurance quote panels and other decentralized price-setting systems.

MARB is a **fixed-identity residual-ranking benchmark**. A submission may improve ranking confidence for a candidate selected by a raw model, but it may not switch the agent or instrument after observing the residual. This isolates incremental information in abnormal action from gains caused by choosing a different object.

## Core objects

For each opportunity \(i\):

- `entity_id`: event, contract or quote request;
- `agent_id`: bookmaker, exchange, insurer or pricing node;
- `instrument_id`: home/draw/away or another fixed priced claim;
- `observation_time`: timestamp before the future target;
- `state_features`: observable contemporaneous state;
- `observed_action`: the agent's subsequent move;
- `expected_action`: the normal-action prediction;
- `action_residual`: observed minus expected action;
- `raw_candidate_score`: future-price score without the residual;
- `residual_candidate_score`: score using the same fixed identity plus residual information;
- `future_price_target`: later same-agent price, joined only after selection is frozen.

## Benchmark tasks

### Task A — Normal-action prediction

Predict whether the agent moves and the conditional change in the priced instrument.

Report:

- movement-hazard log loss or Brier score;
- conditional delta MAE/RMSE;
- chronological calibration;
- coverage and missing-state rates.

Task A is infrastructure. A strong normal-action model is necessary for meaningful residuals, but it does not establish incremental future-price information.

### Task B — Fixed-identity residual repricing

The raw model fixes `agent_id` and `instrument_id`. The residual model reranks the same opportunity universe.

Primary metrics:

1. within-stratum slope of future same-agent log price quality on standardized residual uplift;
2. event-cluster confidence interval;
3. baseline-preserving chronological alignment-placebo p-value;
4. highest-minus-lowest residual-dose contrast.

A submission passes the historical mechanism tier only when the slope lower bound exceeds zero and the alignment placebo beats the frozen threshold.

### Task C — Distribution and transport

Report the Task B slope by:

- agent;
- instrument identity;
- horizon;
- calendar block;
- leave-one-agent-out sample;
- source/provider or deployment adapter.

Required transport diagnostics include standardized mean difference, population-stability index, out-of-support rate and a grouped historical-versus-deployment discriminator.

### Task D — Economic conversion

Task D is secondary and must never replace Task B.

Report:

- exact-capacity raw and residual policies;
- paired event-cluster return difference;
- latency and slippage grid;
- random, clustered and adverse fill mechanisms;
- outcome/instrument contribution;
- closing-price quality to realized-return bridge.

A positive return point estimate with an interval crossing zero remains a diagnostic, not validation.

## Split and leakage rules

1. All model fitting precedes the chronological test interval.
2. Candidate identity and policy membership are written before future prices or outcomes are loaded.
3. Future-price targets must come from the same agent unless a cross-agent task is separately declared.
4. Entity clusters may not cross train/test boundaries where repeated observations would leak identity.
5. Post-event, settlement and revised fields are forbidden from scoring inputs.
6. Hyperparameter, threshold and subgroup selection must be frozen before confirmatory evaluation.
7. Failed and insufficient-volume runs remain visible.

## Evidence tiers

| Tier | Requirement |
|---|---|
| Implemented | Code and configuration exist. |
| Executed | A complete run and immutable artifact exist. |
| Replicated historical | The historical mechanism survives reruns, placebo and predefined slices. |
| Validated prospective | A future-only frozen cohort passes volume, uncertainty, stability and concentration gates. |
| Operational candidate | Prospective mechanism plus separate execution, capacity and risk evidence. |

No benchmark score may silently promote itself across tiers.

## Football profile v1

The repository's reference profile uses:

- 1X2 home/draw/away instruments;
- T-48, T-24, T-12 and T-6 horizons;
- bookmaker/outcome identity fixed by the raw model;
- same-book closing log-CLV as the primary mechanism target;
- exact 5% matched capacity for policy diagnostics;
- match-cluster uncertainty;
- baseline-preserving chronological circular-shift placebos.

The current reference submission is historical-mechanism replicated and prospective-transfer pending.

## Submission format

Submissions use `benchmark/submission.schema.json`. They must include:

- model and data identifiers;
- chronology and identity-control declarations;
- Task B primary metrics;
- subgroup and leave-one-agent-out summaries;
- economic diagnostics separately labeled;
- evidence tier;
- artifact and source hashes;
- prohibited-claim acknowledgements.

Validate with:

```bash
python scripts/validate_benchmark_submission.py benchmark/reference_submission.json
```

## Cross-domain profiles

A new domain profile must define the analogues of agent, instrument, action and future same-agent price before any modeling begins.

Promising profiles include:

- prediction-market market makers reacting to cross-venue consensus;
- insurers revising quotes relative to a peer quote panel;
- airline or hotel sellers changing prices relative to marketplace state;
- crypto exchanges or liquidity providers reacting to cross-venue order-book state.

These are research directions, not claimed transfers. Each requires its own chronology, identity and target audit.
