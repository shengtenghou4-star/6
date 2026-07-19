# Prospective evidence-volume and power forecast — First checkpoint

Status: **completed but not decision-grade because only one post-activation collection cycle is available**.

Run: `29684958036`

Artifact digest: `sha256:41cf1bf7bb09bb40f9e4aa83858081569892c5da3e3dc6780d553357a13c2bc9`

## Current untouched evidence

After the corrected v2 activation boundary:

- 1 inferred collection cycle;
- 4 sport snapshots;
- 13 candidate rows;
- 13 unique events;
- 8 candidate bookmakers;
- event Kish effective sample size: `13.0`;
- snapshot Kish effective sample size: `3.60`.

Cutoff coverage in the first cycle:

- T-48: 4 candidates;
- T-24: 5 candidates;
- T-12: 0 candidates;
- T-6: 4 candidates.

All observed raw and residual candidate scores were positive in the three populated cutoffs.

## Cycle-based exploratory forecast

Using 54 planned collection cycles and a Jeffreys-prior gamma-Poisson model:

- median final candidates: `709`;
- 95% interval: `[396, 1,159]`;
- median final unique events: `710`;
- median exact 5% quota: `38` selections per policy;
- median minimum detectable incremental log-CLV per opportunity: `0.00161`.

The model-based probability of meeting every Phase 43 volume gate was `90.35%`, but this probability is explicitly **not decision-grade** with only one observed cycle.

## Early warning

T-12 had no candidates in the first cycle. Its exploratory median projection was only 12 candidates and its estimated probability of reaching 40 was `22.64%`. This is an early coverage warning, not yet evidence of a structural failure.

## Interpretation

The first cycle demonstrates that the repaired pipeline is producing independent post-activation candidates across multiple books and three supported cutoffs. It is too early to estimate final power reliably. The forecast becomes preliminary after three collection cycles and operational after eight. No campaign rule or evaluation threshold is changed.