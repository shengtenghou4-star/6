# Sample Evidence 010 — Beat The Bookie Historical Odds Dataset

Validated by direct public Kaggle API download and GitHub Actions. The archive was actually opened and all compressed CSV schemas were read before recording this evidence.

## Archive

- Kaggle dataset: `austro/beat-the-bookie-worldwide-football-dataset`
- downloaded bytes: 87,701,470
- archive SHA-256: `8bb898c3c067dfca4c4e50f7e0fb3f01104b52a1d748c27ea7973ec96b36cab1`
- licence shown on dataset page: CC BY-SA 4.0
- profile failures: 0

## Long-horizon closing-odds layer

`closing_odds.csv.gz`

- 479,440 matches
- 19 columns
- dates: 2005-01-01 through 2015-06-30
- 818 leagues observed by profiler
- fields include match/result identity plus average odds, maximum odds, top-bookmaker name and bookmaker count for home/draw/away

This is aggregate closing-market context, not bookmaker-level trajectories.

## Bookmaker time-series layer

Two wide odds tensors:

- `odds_series.csv.gz`: 31,074 matches, 2015-09-01 through 2016-02-29
- `odds_series_b.csv.gz`: 61,573 matches, 2016-03-01 through 2016-11-20
- total matches with wide odds-series rows: **92,647**

Each time-series file has 6,917 columns:

- 5 match/result fields
- 6,912 odds columns = 3 outcomes × 32 bookmaker slots × 72 indexed time points
- bookmaker slots are encoded as `b1` through `b32`
- outcomes are `home`, `draw`, `away`
- time indices are `0` through `71`

### Semantics correction after primary-source audit

The wide files themselves use compact `b1`–`b32` slot identifiers, but the original authors' public generator/unpacker code provides the fixed historical bookmaker mapping. Therefore the slots are **source-mappable**, not permanently anonymous. The mapping is frozen in `docs/BEAT_SOURCE_SEMANTICS.md`.

The original generator also verifies the time direction:

- index 0 ≈ T-71h
- index 71 ≈ T-0h / kickoff marker
- `hours_before_kickoff = 71 - time_index`

This correction supersedes the earlier provisional statement that slot identity and time-index direction were unresolved.

Companion match metadata:

- `odds_series_matches.csv.gz`: 48,774 rows, 2015-09-01 through 2016-02-29
- `odds_series_b_matches.csv.gz`: 79,478 rows, 2016-03-01 through 2016-11-20

The metadata universe is larger than the subset with usable odds-series rows, so joins must remain explicit and no missing-odds matches may be silently fabricated.

## Research significance

This is the first actually acquired multi-bookmaker historical trajectory dataset in the project. It is older and hourly/indexed rather than modern five-minute/tick data, so it does not by itself complete the modern high-resolution market-data gate. It is sufficient to build and falsify the first serious normal-market-behavior/residual pipeline.

The original authors' SQL schema is still strategically preferable if recoverable because it preserves named bookmakers and exact `odds_datetime` updates before hourly sampling.

Workflow artifact digest: `sha256:4c25a976fe59d4daa8c7b38c14591ef09ac0954921164cb42a8cf762494409e9`.