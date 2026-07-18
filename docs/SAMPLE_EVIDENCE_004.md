# Sample Evidence 004 — Full Football-Data Seasonal Archive

Date: 2026-07-18

Produced by GitHub Actions workflow `Football-Data Full Archive`.

Workflow run: `29648336761`
Artifact: `football-data-full-archive`
Artifact SHA-256 digest: `535a7dc4e8a86f28c656df650c20e28565f8b406634aac023a8ca7a999ed869d`

## Verified acquisition

- Seasons requested/acquired: 33 (`1993/94` through `2025/26`)
- Successful seasonal ZIP archives: 33/33
- Valid league CSV files parsed: 684
- Match rows: **240,023**
- Distinct division codes: **22**
- Unioned source/provenance columns: **222**
- Duplicate `(division, date, home, away)` match keys: **0**
- Source ZIP archives preserved with SHA-256
- Bronze union and machine-readable coverage report produced

Division codes observed:
`B1, D1, D2, E0, E1, E2, E3, EC, F1, F2, G1, I1, I2, N1, P1, SC0, SC1, SC2, SC3, SP1, SP2, T1`

## Explicit parse failures

Five legacy Greece `G1.csv` files (`2000/01` through `2004/05`) did not expose the expected `HomeTeam` / `AwayTeam` schema and were rejected rather than guessed into the canonical match structure.

All failures remain recorded in `coverage_report.json`.

## Interpretation

The free coarse historical layer has now moved from a 19,763-row Big-5 sample to a **240,023-row, 22-division, 33-season** archive suitable for entity resolution, long-horizon team/context features, schema/missingness research, and coarse odds baselines.

It still does **not** replace high-frequency bookmaker/exchange movement history. Odds availability and semantics vary materially by era, and older seasons often lack the richer open/close fields available in recent data.
