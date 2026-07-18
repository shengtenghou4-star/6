# Phase 1 Checkpoint

Phase 1 goal: build an evidence-based data source map before large ingestion.

## Completed

- Identified at least two credible high-resolution historical market candidates: The Odds API and Betfair Historical Data.
- Identified a broad prospective odds archive candidate: Sportmonks Premium/TXODDS.
- Identified a proposed entity spine: Sportmonks Football API v3 with vendor-independent canonical IDs.
- Identified supporting event, news and weather sources.
- Documented major timestamp / `known_at` risks.
- Documented the absence of a publicly documented cheap perfect source for long-horizon 100+ bookmaker full-change history.
- Defined a standard sampling gate before any source is marked connected.

## Not completed yet

- No paid/credentialed Tier-1 market source has been connected.
- No full-scale cost model has been validated against real API responses/files.
- No large ingestion has started.

## Next phase

Run real small-sample validation for Tier-1 sources and choose the initial acquisition stack based on measured coverage, timestamp fidelity and cost.
