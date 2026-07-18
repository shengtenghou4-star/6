# Schema v0 — Flexible, Timestamp-Safe Data Lake

This is a starting contract, not a frozen warehouse design. Tables and fields may change. The invariant is provenance and time integrity.

## Layering

### Raw
Immutable source-native payloads/files. Never overwrite. Preserve source URL/ID, ingestion time, content hash, and request parameters when available.

### Bronze
Source-specific parsed records with minimal typing and normalization. Keep source-native identifiers and fields.

### Silver
Canonical cross-source entities and time-safe observations. Entity resolution is explicit and reversible.

### Gold
Experiment-specific features/labels. Rebuildable from lower layers. Never treated as source truth.

## Core entities

### `matches`
- `match_id` canonical internal ID
- source IDs by vendor
- competition/season/round
- home/away canonical team IDs
- scheduled kickoff UTC
- venue/referee where known
- status/result fields
- `known_at` for each historical state where relevant

### `teams`
- `team_id`
- canonical name
- aliases by source and validity interval
- country/competition memberships

### `players`
- `player_id`
- canonical name
- aliases/source IDs
- DOB/nationality/positions where licensed

### `bookmakers`
- `bookmaker_id`
- source-native IDs/names
- jurisdiction/region metadata when useful
- alias history

### `markets`
- `market_id`
- market family (1X2, AH, totals, etc.)
- period/scope
- normalized line semantics
- source-native market mapping

## Time-series facts

### `market_quotes`
One row per observable bookmaker/exchange market state or change.

Minimum concepts:
- `match_id`
- `bookmaker_id`
- `market_id`
- `selection_id`
- line/handicap/total where applicable
- price/odds in source format + normalized decimal
- source update timestamp if present
- conservative `known_at`
- snapshot/ingestion timestamp
- suspension/reopen state where present
- raw payload reference

Never collapse the raw trajectory to only open/close in storage.

### `exchange_market_states`
Optional deeper Betfair/exchange layer:
- publish time
- market/selection IDs
- best available back/lay ladders
- traded volume / matched state where package permits
- market status
- raw payload reference

### `lineups_and_availability`
Store observations, not only final truth:
- expected/confirmed lineup state
- player/team/match
- status (starting, bench, injured, suspended, doubtful, withdrawn, etc.)
- source
- source event/publication time if available
- first-seen ingestion time
- conservative `known_at`

### `news_observations`
- article/post/source ID
- source/publisher/account
- URL/reference
- publication timestamp if reliable
- first-seen time
- retrieved time
- involved entities
- raw text/reference subject to license
- later extraction/embedding references

### `weather_forecast_vintages`
- location/venue
- model/provider
- forecast issue/run time
- valid time
- variables
- ingestion time

Do not substitute realized weather for a forecast vintage in pre-match experiments.

### `match_events`
Post-match/in-play event stream:
- match/player/team
- event type/subtype
- match clock/timestamp
- coordinates/attributes
- source

For pre-match experiments, derived history from prior matches is allowed only if those matches/events were already completed before cutoff.

## Provenance fields

Every important fact should be traceable through some combination of:
- `source`
- `source_id`
- `source_url` or request identity
- `source_updated_at`
- `known_at`
- `ingested_at`
- `raw_payload_ref`
- `payload_hash`
- parser/schema version

## Time policy

`known_at` means the earliest conservative timestamp at which the research system can justify that the information was available to a market participant.

Rules:
1. If exact bookmaker update time exists, preserve it; snapshot time remains separately stored.
2. If only snapshot time exists, use snapshot time conservatively rather than inventing an earlier change time.
3. Historical injury start dates are not publication timestamps.
4. Confirmed lineups must not be backdated to an assumed announcement time without evidence.
5. Corrections/revisions are new observations; do not silently rewrite historical states.

## Entity resolution

Do not force one vendor to be canonical truth.

Maintain mapping tables:
- `source_match_map`
- `source_team_map`
- `source_player_map`
- `source_bookmaker_map`

Mappings need confidence/status and should be reviewable. Ambiguous mappings stay unresolved rather than guessed.

## Flexibility rule

Adding or replacing a data source should not require redefining the research question. Changing the research question should not require destroying raw data. Gold features are disposable; raw evidence is not.
