# Sample Evidence 011 — Modern European Asian Handicap Time-Series Sample

Validated by direct public Kaggle API download and inspection of the actual archive.

## What the public archive actually contains

The dataset README advertises a much larger EU5 2021–2025 corpus (7,494 matches), but the downloadable public archive inspected by this project contains **sample data only**:

- 90 match CSV files
- 107,446 total odds-update rows
- EPL 2024–2025: 30 matches
- LaLiga 2024–2025: 30 matches
- SerieA 2024–2025: 30 matches
- no Bundesliga/Ligue1 files in the downloaded archive
- archive bytes: 821,224
- archive SHA-256: `5a062f1a43a8fec9c345e62069540bc6a4565bb1c943bb8354e9137af5e935a0`

Therefore the advertised 7,494-match corpus is **not treated as acquired or validated**.

## Verified row schema

Each sampled match file contains 8 fields:

- `Teams`
- `FT Score`
- `HT Score`
- `Bookmaker`
- `Home Odds`
- `Handicap`
- `Away Odds`
- `Timestamp`

Rows are actual timestamped odds/line states rather than one open/close pair. Timestamps have `YYYYMMDDHHmmss` form. The source README states UTC and states row 0 is closing / final row is opening; those semantics are source assertions and should still be validated against chronological sorting before modeling.

## Bookmaker coverage

15 distinct masked bookmaker codes were observed in real CSV rows:

`12*`, `18*`, `36*`, `Crow*`, `Interwet*`, `伟*`, `利*`, `威*`, `平*`, `明*`, `易*`, `澳*`, `盈*`, `金宝*`, `香港马*`.

The README provides mappings/types for some masked codes (for example `36*` as Bet365, `平*` as Pinnacle and `香港马*` as HKJC), but these identities are source-provided metadata rather than independently verified identities.

## Important odds semantics

This is Asian Handicap payout/price data, not ordinary European decimal 1X2 odds. `Handicap` is a moving line and `Home Odds` / `Away Odds` are side payouts. Split-ball lines require explicit parsing rather than naive float conversion.

## Strategic value and limitation

The sample is excellent for validating modern AH parsing, line/price-state modeling, timestamp handling and sharp-vs-public feature design. At only 90 matches, it is far too small to serve as the primary training corpus or to validate profit claims.

The README states `Research and personal use only. Not for redistribution.` That source restriction is preserved in project provenance and supersedes any assumption that the raw sample may be redistributed freely.

Workflow artifact digest: `sha256:63af86b5f2735d7d7e2f3e628cb0226de1971fab0fd295f85fe836fb3948ee99`.