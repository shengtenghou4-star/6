# External review packet

## Project in one sentence

The project tests whether a bookmaker's deviation from its expected response to the contemporaneous market contains incremental information about that same bookmaker's later repricing.

## Strongest completed claim

A replicated historical **repricing-information mechanism** is supported:

- the matched historical universe contains 59,816 opportunities across 18,072 matches;
- correct match-specific residual alignment beats 4,000 baseline-preserving chronological placebos for closing log-CLV (`p=0.00025`);
- a one-standard-deviation residual-uplift increase predicts `+0.004430` same-book closing log-CLV, with event-cluster 95% interval `[+0.003316,+0.005515]`;
- the slope is positive for 8/8 bookmakers, 3/3 selected outcomes and 4/4 cutoffs;
- every leave-one-book-out lower confidence bound remains above zero.

## Claims explicitly not made

The repository does not claim:

- stable realized profit;
- live execution readiness;
- scalable stake or account capacity;
- validated future transfer;
- a validated home-only strategy.

Matched historical return improves from `-0.747%` raw ROI to `+0.565%` residual ROI, but uncertainty crosses zero. Under practical execution assumptions, ordinary fill loss leaves a thin margin and adversarial rejection removes standalone profitability.

## Why the design is harder to game

1. **Fixed identity:** the raw model selects bookmaker and outcome; the residual model reranks the same candidate universe.
2. **Chronology:** selection is bound before closing prices and outcomes are loaded.
3. **Alignment placebo:** baseline scores and capacity are preserved while residual uplift is attached to the wrong matches.
4. **Threshold-free test:** the primary slope uses the full opportunity universe rather than only a tuned top tail.
5. **Negative results:** profit, execution and transfer failures remain first-class outputs.
6. **Prospective freeze:** the current seven-day campaign was activated before its closing outcomes were available.

## Thirty-minute audit path

1. Read `README.md` for the evidence hierarchy.
2. Read `docs/EXPERIMENT_019_RESULT.md` for the alignment placebo.
3. Read `docs/EXPERIMENT_021_RESULT.md` and `docs/EXPERIMENT_022_RESULT.md` for dose response and distribution.
4. Read `docs/EXPERIMENT_023_RESULT.md` through `docs/EXPERIMENT_025_RESULT.md` for the economic bottleneck.
5. Inspect `paper/claim_evidence_registry.json` and run:

```bash
python scripts/validate_paper_claims.py
```

6. Inspect `benchmark/reference_submission.json` and run:

```bash
python scripts/validate_benchmark_submission.py benchmark/reference_submission.json
```

## Reviewer questions

A useful independent review should try to answer:

1. Does the fixed-identity construction genuinely isolate incremental residual information?
2. Does the circular-shift placebo preserve enough baseline structure to be a demanding falsification?
3. Is closing log-CLV the correct primary mechanism endpoint, and what additional endpoint would be harder to dispute?
4. Are event clusters sufficient, or should uncertainty also be clustered by league, calendar block or bookmaker?
5. Could the residual uplift still proxy for an omitted contemporaneous market variable?
6. Are the domain-shift repairs independently activated and sufficiently separated from the original stream?
7. Which claim is currently strongest, and which sentence in the paper overreaches the evidence?

## Requested review outputs

Reviewers are encouraged to submit one of three artifacts:

- a reproducibility report with exact commands and mismatches;
- a falsification proposal with a frozen pass/fail criterion;
- an independent MARB benchmark submission on another data source or domain.

Praise without a check is less useful than a narrow counterexample. A negative replication is a valid and valuable contribution.
