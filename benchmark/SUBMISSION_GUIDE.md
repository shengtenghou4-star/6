# MARB submission guide

## 1. Freeze the research question

Before running a model, write a profile that defines the agent, instrument, action, observation time and future same-agent target. State what information is available at each timestamp and how revised data are handled.

A submission is not acceptable when agent or instrument identity can change after residual information is observed unless the profile declares a separate identity-selection task.

## 2. Required files

A reviewable submission should contain:

- a domain profile based on `PROFILE_TEMPLATE.md`;
- executable code or a stable code reference;
- a `submission.json` matching `submission.schema.json`;
- an immutable or content-addressed result artifact;
- a short result note explaining failures and evidence boundaries;
- commands needed to reproduce the reported metrics.

## 3. Minimum mechanism analysis

Task B requires:

- standardized residual-uplift slope;
- entity-cluster confidence interval;
- at least one structure-preserving alignment placebo;
- highest-minus-lowest residual-dose contrast;
- fixed candidate identity;
- later same-agent target;
- no post-event scoring fields.

A historical mechanism tier additionally requires a positive lower confidence bound, placebo probability at or below the contract threshold and positive leave-one-agent-out support.

## 4. Distribution and transport

Report the mechanism by agent, instrument and horizon. Add calendar blocks or provider/source splits when relevant. Explain missing groups rather than silently removing them.

For deployment or cross-source work, report support diagnostics such as standardized mean difference, population-stability index, interval overlap, out-of-support rate and a grouped discriminator.

## 5. Economic diagnostics

Economic conversion is secondary. Use equal capacity and bind policy membership before future outcomes are loaded. Report paired entity-level uncertainty.

Execution validation requires more than a positive point estimate. At minimum, stress delay, slippage, random fill and informative rejection. The benchmark currently treats execution as unvalidated unless the submission explicitly supplies sufficient prospective evidence.

## 6. Evidence-tier selection

Choose the lowest tier that fully describes the evidence:

- `implemented` for code without a complete run;
- `executed` for a completed run and artifact;
- `replicated_historical` after historical falsification and distribution gates;
- `validated_prospective` only after a frozen future cohort passes;
- `operational_candidate` only after separate execution and risk evidence.

The validator rejects unsupported promotion.

## 7. Validation

```bash
python scripts/validate_benchmark_submission.py path/to/submission.json \
  --output artifacts/submission-validation.json
```

A passing schema/semantic report means that the submission obeys the declared contract. It does not independently verify the underlying data or reproduce the analysis.

## 8. Pull-request checklist

- [ ] Profile defines entity, agent, instrument, action and later same-agent target.
- [ ] Availability timestamps and revision rules are explicit.
- [ ] Candidate identity is fixed before future targets.
- [ ] Structure-preserving placebo is described.
- [ ] Full-distribution or dose-response result precedes strategy selection.
- [ ] Economic and execution claims are separately labeled.
- [ ] Artifact hash and code reference are present.
- [ ] `submission.json` passes the validator.
- [ ] Negative and insufficient results remain visible.
- [ ] The result note states what the submission does not establish.

## 9. Review outcomes

A submission can be accepted into the catalog as:

- empirical profile;
- synthetic contract test;
- failed replication;
- inconclusive/insufficient-volume result;
- proposed profile awaiting execution.

Acceptance into the catalog is not endorsement of profitability or causal interpretation.