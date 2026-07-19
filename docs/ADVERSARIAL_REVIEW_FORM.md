# Adversarial review form

This form is designed for a technically serious external review. The goal is to find the narrowest claim that fails, not to produce a generic endorsement.

## Reviewer metadata

- Reviewer name or pseudonym:
- Date:
- Relevant background:
- Repository commit reviewed:
- Artifacts reproduced:
- Time spent:

## Severity scale

- **S0 - clarification:** wording or navigation issue; no effect on evidence.
- **S1 - minor:** local reproducibility or reporting weakness; main claim unchanged.
- **S2 - material:** important robustness gap or ambiguous attribution; claim should narrow.
- **S3 - major:** primary mechanism may not survive a valid alternative explanation.
- **S4 - critical:** chronology, identity or target leakage invalidates the principal result.

## A. Chronology and leakage

1. Can every scoring field be shown to exist before the target and event outcome?
2. Are revised or corrected source values handled consistently?
3. Could entity matching or repeated observations cross a split and leak latent identity?
4. Are policy membership and prices bound before outcomes are loaded?
5. Is any future closing information used indirectly in filtering, normalization or feature construction?

Finding:

- Severity:
- File/line or artifact:
- Reproduction steps:
- Proposed falsification:

## B. Fixed identity

1. Does the raw model genuinely fix bookmaker and outcome identity?
2. Can the residual model improve by silently switching candidate identity?
3. Are matched raw/residual capacity and opportunity universes identical where claimed?
4. Does any preprocessing depend on the augmented score?

Finding:

- Severity:
- Evidence:
- Minimal repair:

## C. Alignment placebo

1. Does the circular shift preserve baseline score, group chronology, residual distribution and exact capacity?
2. Does it break only the hypothesized opportunity-specific alignment?
3. Are groups large enough for a meaningful shift?
4. Would a calendar-block, league-block or source-block placebo be more demanding?
5. Is the replicate count and random seed frozen before interpretation?

Finding:

- Severity:
- Alternative placebo:
- Expected pass/fail criterion:

## D. Threshold-free result

1. Are baseline strata sufficiently narrow to isolate incremental residual information?
2. Is standardization performed without target information?
3. Is the cluster unit appropriate?
4. Does the result depend on a few dose bins, books, horizons or dates?
5. Would a monotonic model, rank statistic or out-of-time slope materially change the interpretation?

Finding:

- Severity:
- Alternative estimator:
- Expected effect:

## E. Mechanism endpoint

1. Is later same-book closing log-CLV an appropriate measure of the claimed repricing channel?
2. Could the closing quote itself be stale, thin or mechanically linked to the observation?
3. Would devigged probability change the main result?
4. Is same-book targeting essential, and are cross-book targets reported separately?
5. What endpoint would be harder to dispute?

Finding:

- Severity:
- Recommended endpoint:

## F. Economics and execution

1. Are matched ROI and paired uncertainty computed on the correct unit?
2. Does outcome concentration undermine the aggregate economic interpretation?
3. Are delay and slippage assumptions realistic?
4. Do adverse-fill mechanisms capture informative rejection?
5. What additional evidence is required before operational use?

Finding:

- Severity:
- Missing execution variable:

## G. Prospective design

1. Were model, activation time, policy and gates frozen before target maturity?
2. Can any original row be rewritten or silently dropped?
3. Are parallel adapters genuinely separate from the original stream?
4. Are volume and stability gates resistant to optional stopping?
5. Is the campaign long and independent enough for the intended claim?

Finding:

- Severity:
- Evidence:
- Required correction:

## H. Paper and claim governance

1. Does every load-bearing number map to a result artifact?
2. Does the prose overstate the evidence tier?
3. Are post-hoc analyses labeled clearly?
4. Are failed gates and negative results visible?
5. Which sentence is the strongest unsupported sentence, if any?

Finding:

- Severity:
- Sentence:
- Recommended rewrite:

## I. Benchmark contract

1. Can a submission promote itself without satisfying the semantic validator?
2. Is the synthetic profile clearly separated from empirical replication?
3. Are agent, instrument and target analogues sufficiently defined for new domains?
4. Is the submission schema missing any provenance or uncertainty field?
5. Could two implementations obtain incomparable scores while both passing?

Finding:

- Severity:
- Contract change:

## Final verdict

Choose one:

- [ ] Principal historical mechanism is reproducible as stated.
- [ ] Mechanism is likely real but the claim should narrow.
- [ ] Evidence is inconclusive pending a specified falsification.
- [ ] A major methodological flaw currently blocks the principal claim.
- [ ] Chronology or leakage invalidates the principal result.

## Strongest supported claim

Write one sentence:

## Weakest or most overstated claim

Write one sentence:

## Highest-value next experiment

Describe one experiment with a frozen pass/fail criterion:

## Reproducibility log

```text
commands, versions, hashes and mismatches
```

## Reviewer declaration

State any conflict of interest, data-access limitation or use of automated tools. A negative review is welcome when it is specific and reproducible.