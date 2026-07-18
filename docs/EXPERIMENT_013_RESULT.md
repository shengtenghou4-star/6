# Experiment 013 — Selection versus ranking decomposition result

Status: **diagnostic decomposition completed**

This experiment uses the already opened Experiment 011 historical test period. It is a mechanism study, not a new untouched alpha or profit claim.

## Locked scope

- 18,072 test matches
- 59,816 match/cutoff opportunities
- 11,961 trades per strategy
- eight named bookmakers
- same four cutoffs and same-book final closing target as Experiment 011

## Candidate identity changes

The full-residual model chose the same bookmaker and outcome as the raw-market model on only `62.77%` of opportunities.

- same bookmaker: `64.18%`
- same selected H/D/A outcome: `87.42%`
- same bookmaker + outcome: `62.77%`
- changed candidate identities: `22,270`

The residual layer therefore changes bookmaker selection far more often than H/D/A side selection.

## Four frozen strategies

| Strategy | Mean trade log-CLV | Mean opportunity log-CLV | Incremental opportunity log-CLV vs baseline | 95% CI |
|---|---:|---:|---:|---:|
| Raw baseline | 0.03373733 | 0.00674623 | — | — |
| Full residual | 0.03549083 | 0.00709686 | 0.00035063 | [0.00002516, 0.00067648] |
| Rank-only overlay | **0.03748062** | **0.00749475** | **0.00074852** | **[0.00044877, 0.00104811]** |
| Selection-only overlay | 0.03503798 | 0.00700631 | 0.00026008 | [0.00003989, 0.00048624] |

Both mechanisms are real, but ranking dominates.

## Trade-set overlap

Compared with the raw baseline:

- full residual Jaccard overlap: `0.6354`
- rank-only overlay Jaccard overlap: `0.6150`
- selection-only overlay Jaccard overlap: `0.8438`

The residual ranking score replaces more of the top-20% trade set than residual candidate selection does.

## Cutoff stability

Rank-only incremental opportunity log-CLV was positive at all four cutoffs:

- T-48h: `0.00088968`, CI `[0.00026071, 0.00156172]`
- T-24h: `0.00076260`, CI `[0.00012748, 0.00137245]`
- T-12h: `0.00053018`, CI `[-0.00004744, 0.00113563]`
- T-6h: `0.00086604`, CI `[0.00041075, 0.00137559]`

Selection-only was positive overall, but materially smaller and individually significant only at T-24h.

## Mechanism conclusion

The residual edge is primarily a **trust/ranking signal**, not a wholesale directional replacement engine.

The raw market is already fairly good at proposing the bookmaker/outcome direction. The residual model adds most value by deciding **which of those apparent price-move opportunities are credible enough to rank into the top trade bucket**. When the residual model is allowed to change the selected bookmaker/outcome, that adds a smaller but still statistically positive contribution.

The rank-only overlay outperformed the full residual strategy because using residuals to rerank raw-market candidate identities preserves the market's strong directional proposal while removing weaker opportunities. Letting residuals also replace identities introduces additional directional error and dilutes part of the ranking benefit.

## Decision

For prospective architecture:

1. use the raw/normal-market model to generate candidate bookmaker/outcome directions;
2. use contemporaneous action residuals primarily as a confidence and ranking layer;
3. treat residual-driven candidate replacement as a secondary component requiring a higher evidence threshold;
4. keep move-surprise and sequential persistence as timing/risk context rather than the primary economic score.

No realized-profit, fill, limit, latency or future-performance claim is made.

Artifact digest: `sha256:a68aaec00fa30cc9437f120647490de80e4f136a2c37c03738d5cb7ce746058b`
