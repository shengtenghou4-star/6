# Football Market Behavior Lab

A reproducible research project testing whether deviations from a bookmaker's **expected market behavior** contain incremental information about subsequent football-odds repricing.

The project is deliberately narrower than “predict football with AI.” It models what a bookmaker would normally do from contemporaneous market state, measures abnormal action residuals, and asks whether those residuals improve forecasts of the same bookmaker's later price.

## Current conclusion

The historical evidence supports a real **repricing-information mechanism**:

- match-specific residual alignment beats baseline-preserving shuffled placebos;
- residual uplift has a graded dose relationship with later same-book closing-price quality across the full opportunity universe;
- the relationship is positive across every tested cutoff, selected outcome and bookmaker, and survives removing any one bookmaker;
- related effects transfer to independent timestamped data and unseen-book diagnostics.

The project has **not** established stable realized profit, executable scalability, account capacity or live-betting readiness. Residual-minus-raw execution point return is broadly positive across frozen friction envelopes, but the small practical return is concentrated in home-selected opportunities, disappears under adversarial rejection, and remains statistically uncertain.

The decisive next evidence is an untouched seven-day prospective campaign running from `2026-07-19T06:00:00Z` to `2026-07-26T06:30:00Z`.

## Evidence hierarchy

| Evidence level | Current status | Representative evidence |
|---|---|---|
| Bookmaker actions are conditionally modelable | Supported historically and on an independent exact-timestamp feed | Experiments 001–004 |
| Abnormal residuals predict later same-book repricing | Supported across attribution, shuffled-null, unseen-book and matched-identity tests | Experiments 007–014 |
| Match-specific alignment matters | Passed 4,000 baseline-preserving circular-shift placebos, `p=0.00025` | [Experiment 019](docs/EXPERIMENT_019_RESULT.md) |
| Effect is threshold-free | One-SD residual-uplift log-CLV slope `+0.004430`, 95% CI `[+0.003316,+0.005515]`; all four cutoffs positive | [Experiment 021](docs/EXPERIMENT_021_RESULT.md) |
| Effect is broadly distributed | Positive slope for 8/8 bookmakers, 3/3 selected outcomes and 4/4 cutoffs; every leave-one-book-out lower bound above zero | [Experiment 022](docs/EXPERIMENT_022_RESULT.md) |
| Historical matched-budget return | Residual policy `+0.565%` ROI versus raw reference `-0.747%`, but uncertainty crosses zero | [Experiment 017](docs/EXPERIMENT_017_RESULT.md) |
| Execution robustness | Residual-minus-raw point return positive in 60/64 exact envelopes; ordinary fill loss leaves a thin positive margin, adversarial rejection erases it, and the validation gate fails | [Experiment 023](docs/EXPERIMENT_023_RESULT.md) |
| Execution outcome attribution | Home point return positive in 4/4 practical mechanisms, draw in 0/4 and away in 1/4; removing home makes the point lift negative in 3/4 | [Experiment 024](docs/EXPERIMENT_024_RESULT.md) |
| Untouched prospective transfer | Original and separately activated challenger evaluations are in progress | [Phase 36 campaign](docs/PROSPECTIVE_MATCHED_BUDGET_SHADOW.md) |
| Stable profit and live execution | **Not established** | No authorization follows from this repository |

## Prospective validation

### Original frozen stream

The primary campaign collects bounded, immutable near-event 1X2 snapshots every three hours. It builds leakage-safe quote chains, applies the frozen generic action-residual bundle and records candidate scores without match outcomes.

The original matched-budget campaign-close evaluator is frozen before completion:

- full matured cohort within T-48, T-24, T-12 and T-6;
- exact `floor(n × 0.05)` raw and residual policies;
- policy ledgers written and hashed before closing targets are read;
- exact same-book closing joins;
- event-cluster uncertainty, cutoff stability, concentration and fixed evidence-volume gates.

See [the frozen cohort protocol](docs/PROSPECTIVE_MATCHED_BUDGET_COHORT_EVALUATION.md).

### Support-repaired parallel stream

An outcome-blind domain-shift audit found two structural deployment mismatches:

1. broad prospective timing windows versus exact historical cutoff states;
2. a historical 31-peer coverage scale versus the current 19–20-peer provider panel.

The original stream remains unchanged. A separately activated conservative adapter instead:

- retains rows within 1.75 hours of canonical cutoffs and inside the historical `[6h,48h]` range;
- normalizes active peer-book coverage by contemporaneous panel capacity;
- recomputes all normal residuals and raw/action scores from the same frozen bundle;
- writes independent, research-only ledgers.

See [the repair protocol](docs/PROSPECTIVE_SUPPORT_REPAIRED_SHADOW.md), [engineering validation](docs/PROSPECTIVE_SUPPORT_REPAIRED_SHADOW_VALIDATION.md) and [separate final evaluator](docs/PROSPECTIVE_SUPPORT_REPAIRED_COHORT_EVALUATION.md).

### Canonical-timing parallel stream

A second separately activated challenger preserves more globally supported observations. It keeps rows inside `[6h,48h]`, replaces only the model timing input with the assigned T-48/T-24/T-12/T-6 state, normalizes peer coverage and rescores with the unchanged frozen bundle. Its production activation is `2026-07-19T15:00:00Z`, and it has its own immutable stream and campaign-close evaluator.

See [the canonical-timing protocol](docs/PROSPECTIVE_CANONICAL_TIMING_SHADOW.md) and [its separate final evaluator](docs/PROSPECTIVE_CANONICAL_TIMING_COHORT_EVALUATION.md).

### Future home-selected cohort

Experiment 024's home concentration is explicitly post-hoc. A new confirmatory cohort therefore uses only original-stream candidates ingested after `2026-07-19T15:00:00Z` whose raw-model selected outcome is home. It preserves the original exact quota and all original volume, uncertainty, cutoff and concentration gates; insufficient volume cannot be repaired by lowering them.

See [the separately frozen home-selected evaluator](docs/PROSPECTIVE_HOME_ONLY_COHORT_EVALUATION.md).

A scheduled outcome-blind [adapter coverage audit](docs/PROSPECTIVE_ADAPTER_COVERAGE_AUDIT.md) compares stream volume, overlap and score agreement after the common activation boundary without reading closing targets or changing any adapter.

## Research safeguards

- **Chronology first:** candidate observations must precede closing targets and kickoff.
- **Outcome blindness:** prospective scoring and policy selection read no scores, winners or settlement fields.
- **Identity control:** the raw model fixes bookmaker and outcome identity; residual models rerank the same candidate universe.
- **Immutable evidence:** raw responses, manifests, policy ledgers and evaluation artifacts receive checksums and write-once locations.
- **Frozen gates:** sample-size, uncertainty, cutoff and concentration thresholds are fixed before results.
- **Negative results remain visible:** failed profit, execution and transfer gates are recorded rather than reframed.
- **No silent dropping:** missing exact targets, invalid chronology, mixed bundles and evidence-flag violations fail closed.

## Reproducibility map

The repository keeps protocol, implementation, workflow and result evidence separate:

- `docs/EXPERIMENT_*_PROTOCOL.md` — frozen questions, constructions and gates;
- `docs/EXPERIMENT_*_RESULT.md` — supported interpretation and failed checks;
- `scripts/experiment_*.py` — executable historical diagnostics;
- `src/marketlab/` — prospective ledgers, scoring, evaluation and audit logic;
- `.github/workflows/` — pinned experiment and scheduled prospective runs;
- `tests/` — chronology, identity, quota, tampering and failure-mode regression tests;
- `prospective-data` branch — immutable campaign snapshots, manifests, forecasts and final evaluation evidence.

Most historical experiments can be rerun through their named GitHub Actions workflow. Workflows verify frozen source or artifact hashes where the evidence boundary requires it and upload the full result bundle even when a run fails.

## What this project may eventually establish

A successful untouched prospective result would support the claim that abnormal bookmaker-action residuals transfer to future same-book price quality outside the historical development data.

It would still not, by itself, prove profitable live execution. That would require separate prospective evidence for latency, fill probability, slippage, limits, account survival and sufficient independent sample size.

## Repository principles

1. No future-information leakage or timestamp cheating.
2. Raw evidence is preserved whenever practical.
3. Every important result is tied to code, data, configuration and an experiment record.
4. Negative results are first-class results.
5. Exploratory, historical diagnostic and untouched prospective evidence are never presented as interchangeable.
6. Claims stop where the evidence stops.
