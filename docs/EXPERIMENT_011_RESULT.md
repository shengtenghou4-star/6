# Experiment 011 — Same-book closing-line residual result

Status: **promoted**

## Frozen question

Do abnormal quote-action residuals predict the same bookmaker's final pre-match quote beyond the complete contemporaneous market state?

No match outcome was used.

## Locked test scope

- 18,072 matches
- 403,248 bookmaker/cutoff rows
- eight named bookmaker slots
- signal cutoffs: T-48h, T-24h, T-12h, T-6h
- target: same bookmaker's final valid H/D/A state at tensor index 71

## Closing move hazard

- market-only Brier: `0.10419731`
- market + residual Brier: `0.10268062`
- relative improvement: `1.456%`
- improved cutoffs: `4/4`
- paired match-bootstrap improvement CI: `[0.00133373, 0.00170453]`

All frozen hazard checks passed.

## Conditional closing repricing

- market-only H/D/A delta MAE: `0.02001569`
- market + residual MAE: `0.01999630`
- relative improvement: `0.0969%`
- improved cutoffs: `4/4`
- paired match-bootstrap improvement CI: `[0.00001159, 0.00002703]`

The magnitude is small but statistically stable across a large locked sample. All frozen conditional-delta checks passed.

## Frozen top-20% closing-CLV strategy

Residual-augmented strategy:

- 59,816 match/cutoff opportunities
- 11,961 trades
- mean trade log-odds CLV: `0.03549083`
- bootstrap CI: `[0.03301792, 0.03813210]`
- mean fair-probability CLV: `0.01535262`
- positive trade log-CLV at `4/4` cutoffs

Raw-market strategy:

- mean trade log-odds CLV: `0.03373733`
- mean fair-probability CLV: `0.01485208`

Residual-specific incremental comparison:

- augmented minus baseline opportunity log-CLV: `0.00035063`
- paired match-bootstrap CI: `[0.00002516, 0.00067648]`

The strict residual-specific closing-CLV gate passed.

## Decision

Abnormal quote-action residuals are promoted as a durable same-book closing-line signal. The result is stronger than the earlier three-hour repricing result because it survives to the bookmaker's final recorded pre-match quote and produces statistically positive incremental closing CLV beyond a strong raw-market model.

This does **not** establish realized profit, executable fills, limits, latency feasibility, or future prospective performance. The earlier frozen return audit remained negative. Untouched prospective named-book data is still required before any profit claim.

Artifact digest: `sha256:528ab6443ffde7db713c238ff17148baf818b012fd988a39e21c338d0ae410d1`
