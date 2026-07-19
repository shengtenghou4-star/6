# Market Action Residual Benchmark (MARB)

MARB tests whether an agent's abnormal action, after conditioning on observable market state, contains information about that same agent's later price.

The benchmark is designed for multi-agent pricing systems such as bookmakers, exchanges, insurers, prediction markets and travel marketplaces. It is not a profitability leaderboard. Mechanism, economic conversion, execution and prospective transfer are separate evidence tiers.

## Current release status

**Release:** Beta v0.2  
**Contract status:** executable and CI-validated  
**Empirical profiles:** football historical reference  
**Contract-test profiles:** deterministic synthetic multi-agent pricing  
**Missing maturity step:** an independently sourced real second-domain profile

## Five-minute quickstart

Install the project and validate the reference submission:

```bash
python -m pip install -e ".[dev]"
python scripts/validate_benchmark_submission.py benchmark/reference_submission.json
```

Run the deterministic synthetic profile:

```bash
python scripts/run_synthetic_marb_profile.py \
  --output-root artifacts/synthetic-marb-profile

python scripts/validate_benchmark_submission.py \
  artifacts/synthetic-marb-profile/submission.json
```

The synthetic profile is expected to recover a known positive residual mechanism while leaving execution and prospective transfer unvalidated.

## What a profile must define

Every profile must identify:

- `entity_id`: event, contract or quote request;
- `agent_id`: the price-setting or forecasting agent;
- `instrument_id`: the fixed priced claim;
- `observation_time`: when the decision information exists;
- `observed_action`: the agent's realized update;
- `expected_action`: the normal-action forecast;
- `action_residual`: observed minus expected action;
- `future_price_target`: a later same-agent target;
- candidate-identity and chronology rules.

Use `PROFILE_TEMPLATE.md` before implementing a new domain.

## Submission path

1. Write and freeze a domain profile.
2. Produce a schema-valid `submission.json`.
3. Run `scripts/validate_benchmark_submission.py`.
4. Retain the output report, code reference and artifact hash.
5. Open a pull request containing the profile, submission and an evidence-boundary statement.

Detailed instructions are in `SUBMISSION_GUIDE.md`.

## Evidence tiers

| Tier | Meaning |
|---|---|
| Implemented | Code and configuration exist. |
| Executed | A complete run and artifact exist. |
| Replicated historical | Mechanism survives placebo, uncertainty and distribution checks. |
| Validated prospective | A frozen future cohort passes its gates. |
| Operational candidate | Separate prospective execution, capacity and risk evidence also passes. |

A submission cannot promote itself by changing a label. The semantic validator enforces the tier requirements encoded in the contract.

## Current catalog

`catalog.json` is the machine-readable profile and submission catalog. It distinguishes empirical profiles from simulation-only contract tests and records the maximum defensible evidence tier.

## Fair-use and interpretation rules

MARB scores must not be presented as proof of stable profit. A positive mechanism result means that correctly aligned abnormal action predicts later same-agent price quality under the declared controls. Economic and execution claims require their own evidence.

Failed, inconclusive and insufficient-volume submissions are valid research outputs and should remain visible.