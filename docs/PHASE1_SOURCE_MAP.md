# Phase 1 Source Map — 2026-07-18

## Decision in one sentence

Use a **hybrid acquisition strategy**: reconstruct history from several imperfect sources, while starting a permanent prospective archive as early as possible so future research is no longer hostage to vendor retention limits.

## Ranked market-data candidates

| Rank | Source | Best use | Time depth / resolution | Main weakness | Current decision |
|---|---|---|---|---|---|
| 1 | The Odds API | Multi-bookmaker retrospective snapshots | 2020+; 10 min then 5 min | query-credit cost; exact soccer market coverage must be sampled | sample + cost model first |
| 1 | Betfair Historical Data | Exchange microstructure, liquidity, price discovery | Apr 2015+; stream-style timestamped changes | exchange only; Advanced/Pro cost | sample narrow period |
| 1 | Sportmonks Premium / TXODDS | Broad prospective bookmaker archive | 120+ bookmakers; every change while retained | public API history expires ~7 days after kickoff | negotiate/sample; archive continuously if chosen |
| 2 | Football-Data.co.uk | Long baseline/results/open-close odds | long horizon, some leagues to 1993/94 | not full intraday trajectory | ingest as benchmark |
| 3 | API-Football odds | backup prospective odds | short retention, ~3h prematch updates | too coarse/short-history for core problem | backup only |

Rank ties are intentional: the three Tier-1 sources solve different parts of the problem.

## Recommended identity spine

**Leading candidate: Sportmonks Football API v3**, because fixture/team/player/venue/referee/lineup/injury objects share one source-native ID system and can link directly to its odds feed.

However, our canonical IDs must remain vendor-independent:

- `canonical_match_id`
- `canonical_team_id`
- `canonical_player_id`
- source mapping tables for every vendor

Never let a single provider's ID become the permanent ontology of the project.

## Supporting data stack

- **StatsBomb Open Data:** event-level feature engineering and schema prototyping on covered competitions.
- **GDELT 2.0:** broad historical news discovery / first-seen timing.
- **NewsAPI:** simpler article discovery and `publishedAt` cross-checks over recent years.
- **Open-Meteo:** historical weather and vintage forecast products.
- **Sportmonks/API-Football:** lineup, injury, player and referee coverage after sampling.

## Critical `known_at` findings

### Strong

- Betfair historical exchange publish timestamps.
- The Odds API snapshot timestamps (conservative availability time).
- Prospectively self-archived Sportmonks/TXODDS updates.

### Mixed / requires caution

- Historical injury records: start/end dates do **not** prove when the market first learned the information.
- Historical lineups: confirmed XI is useful, but exact first-publication time must be validated or prospectively captured.
- News publication timestamps: may represent source metadata, repost time, or first-seen time depending source.
- Weather: realized weather is future information when making an earlier betting decision; use a forecast vintage that existed before cutoff.

## Architecture implication

Every normalized record should preserve at least three clocks when possible:

1. `event_time` — when the real-world event/quote applies.
2. `source_published_at` — timestamp claimed by source/vendor.
3. `ingested_at` — when our system actually observed it.

Derived `known_at` must be conservative and documented, not guessed.

## The biggest market-data gap

We did **not** find a publicly documented, cheap source that simultaneously offers:

- many years,
- 100+ bookmakers,
- every price movement,
- easy bulk historical export.

This is now an explicit project constraint, not something an Agent is allowed to hand-wave away.

## Next gate before large-scale collection

For each Tier-1 source, obtain a narrow real sample and answer:

1. How many relevant bookmakers and markets actually exist for EPL + one secondary league?
2. What is the real timestamp granularity and missingness?
3. Can William Hill / bet365 / Pinnacle or equivalent key actors be tracked consistently?
4. How much would 1 league-season, 10 league-seasons, and full target scope cost?
5. Can vendor IDs be joined reliably to fixtures/teams?
6. Are raw terms/licensing compatible with permanent research storage?

Only after this gate should Codex start large-scale ingestion.
