# Sample Evidence 015 — Frozen Outcome-Blind Abnormal-Action Residuals v0

The two promoted normal-behavior layers were retrained only on the chronological training split and combined to generate outcome-blind residual records for validation/test periods.

## Frozen model training

- move-hazard HGB training states: 500,000 deterministic train sample
- conditional-movement HGB training mover states: 400,000 deterministic train sample
- no score/result/outcome field was read by residual-generation code

## Residual outputs

### Validation

- 409,350 residual rows
- 9,118 unique matches
- move rate: 34.16%
- mean predicted move probability: 31.42%
- mean absolute move surprise: 0.3665
- mean action-residual L2: 0.00949
- 269,519 no-move rows have no conditional-movement residual by definition

### Locked test

- 667,574 residual rows
- 14,230 unique matches
- move rate: 31.75%
- mean predicted move probability: 26.81%
- mean absolute move surprise: 0.3525
- mean action-residual L2: 0.00836
- 455,611 no-move rows have no conditional-movement residual by definition

All 8 frozen bookmakers and all 6 frozen cutoffs are represented.

## Frozen residual families

- signed move surprise = actual move − predicted move probability
- no-move surprise = predicted move probability when no move
- unexpected-move surprise = 1 − predicted move probability when a move occurs
- conditional movement-vector residual = actual delta − predicted conditional delta, only when a move occurs
- unconditional action residual = actual delta − p(move) × predicted conditional delta
- consensus-gap and residual magnitudes
- prior-cutoff persistence summaries computed only from earlier already-observed cutoffs for the same match/book

## Data integrity

Residual files are emitted only for chronological validation/test states. Earlier-cutoff persistence features never use later cutoffs. Match outcomes remain completely absent from construction.

Files:

- `residuals_validation.csv.gz` — 48,928,604 bytes, SHA-256 `bbf2028602b0b51e065d42f9f7dfe27aedb65784149635fd70dc9363362bf244`
- `residuals_test.csv.gz` — 79,377,393 bytes, SHA-256 `f7cb101fd732af49bd4c15e325d7369d88a360215f95730866ee2bbd41f14ac3`

Workflow artifact digest: `sha256:4f23133b22d3dbe9c25825e912ba83c016b68a73660d79f5cfe7b46e4336e4c7`.

## Next research gate

Residual definitions are now frozen before any match-outcome analysis. The next experiment may test whether these residuals add incremental information beyond contemporaneous market consensus; it may not redefine residuals after seeing outcome results.