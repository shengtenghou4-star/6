# Sample Evidence 002 — Multi-League Public Baseline Lake

Date: 2026-07-18

Produced by GitHub Actions workflow `Public Baseline Backfill`.

Workflow run: `29647664620`
Artifact: `football-data-baseline`
Artifact SHA-256 digest: `6ce2943c1f59c6ce35a5991bfbf261caada19716276299d031722fbb9cf06315`

## Scope acquired

- Divisions: `E0`, `D1`, `I1`, `SP1`, `F1`
- Seasons: `1516` through `2526` (11 seasons)
- Source files requested: 55
- Successful source files: 55
- Failed source files: 0
- Raw source files preserved: 55
- Match rows: 19,763
- Unique source/metadata columns in unioned bronze table: 183
- Duplicate match keys detected by `(division, date, home, away)`: 0

## Produced evidence

- immutable compressed raw CSV copies with SHA-256 per source file
- per-file row/column/non-empty coverage profile
- compressed bronze union table retaining source-native columns plus season/division/source URL
- machine-readable `coverage_report.json`

## Interpretation

This dataset is now sufficient for entity resolution, schema evolution, feature engineering, missingness analysis, and coarse opening/closing-market baselines while higher-resolution market sources are acquired.

It must **not** be treated as a replacement for bookmaker/exchange time-series history. Many odds fields are open/close/aggregate-style observations and field availability varies by season/provider.

## Gate result

Phase 3 initial acceptance threshold (`>=15,000` rows, reproducible raw preservation, explicit failures/duplicates) is satisfied.
