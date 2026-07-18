# Source Sampling Protocol

Before any large scrape or paid backfill, every serious source must pass the same small-sample test.

## Standard sample scope

Use two competitions where possible:

- one highly liquid major league (default: EPL)
- one secondary league with weaker liquidity / noisier coverage

Use at least 20–50 fixtures across multiple matchdays when access permits.

## Required checks

### Market history

- bookmaker count actually returned
- key bookmaker continuity by fixture
- 1X2, Asian handicap, totals availability
- first quote time before kickoff
- update count per bookmaker/market/fixture
- effective timestamp resolution
- duplicate / stale / impossible prices
- missing intervals
- source-native event/market/bookmaker identifiers
- opening and closing reconstruction quality

### `known_at`

- identify source timestamp semantics precisely
- distinguish snapshot time from bookmaker update time
- preserve raw timestamp and ingestion timestamp separately
- never infer an earlier availability time than evidence supports

### Entity joins

- team name normalization
- fixture kickoff changes / postponements
- league/season identifiers
- duplicate fixture handling
- mapping confidence to canonical IDs

### Cost model

Calculate actual units/credits/files for:

- 1 league-season
- 10 league-seasons
- target full scope

Include storage and API/download cost separately.

## Pass criteria

A source is not `connected` merely because an API returns HTTP 200.

It passes only when:

1. real payloads are preserved,
2. timestamps are understood,
3. joins work on a representative sample,
4. missingness and coverage are measured,
5. cost at target scale is estimated,
6. a reproducible script can repeat the sample.

## First three sources to sample

1. The Odds API — multi-bookmaker historical snapshots.
2. Betfair Historical Data — narrow soccer period/package for exchange microstructure.
3. Sportmonks Football + Premium Odds/TXODDS — entity integration and prospective change archive.

Public/free supporting sources (Football-Data, StatsBomb Open Data, Open-Meteo) can be ingested independently, but should still preserve provenance and raw files.
