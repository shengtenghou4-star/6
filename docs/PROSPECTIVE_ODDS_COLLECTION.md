# Prospective Odds Collection

## Purpose

The historical experiments established learnable normal quote behavior and a modest abnormal-residual lead signal for subsequent repricing, but did not establish future profit. Untouched prospective named-book data is required for the next confirmatory stage.

This collector records one current-odds snapshot from The Odds API v4 without scheduling or silently spending recurring credits.

## Data retained

Every successful snapshot directory contains:

- `raw-response.json` — exact response bytes
- `normalized-outcomes.csv` — one row per event × bookmaker × market × outcome
- `manifest.json` — request scope without the API key, ingestion time, raw checksum, row/coverage counts, validation diagnostics and quota headers

Provider timing fields are kept separately:

- collector `snapshot_ingested_at_utc`
- event `commence_time`
- bookmaker `last_update`
- market `last_update` when supplied

The collector never treats ingestion time as bookmaker-native update time.

## Immutability

Snapshot directory names include ingestion time, sport key and raw SHA-256 prefix. Directory creation is exclusive. A second write to the same snapshot path fails instead of overwriting evidence.

## Fail-closed rules

- `THE_ODDS_API_KEY` must come from the environment or GitHub repository secret
- the key is excluded from manifests and printed output
- exactly one of `regions` or `bookmakers` must be specified
- decimal prices `<=1` are preserved and flagged, not silently dropped
- malformed timestamps are preserved and counted
- malformed event/bookmaker/market/outcome structures are counted
- invalid JSON preserves raw bytes plus failure evidence

## Local invocation

```bash
export THE_ODDS_API_KEY='...'
python scripts/collect_the_odds_api_snapshot.py \
  --sport soccer_epl \
  --markets h2h \
  --regions uk,eu \
  --output-root artifacts/prospective-odds
```

A bookmaker allow-list can be used instead of regions:

```bash
python scripts/collect_the_odds_api_snapshot.py \
  --sport soccer_epl \
  --markets h2h \
  --bookmakers bet365,pinnacle \
  --output-root artifacts/prospective-odds
```

## GitHub Actions

`Prospective Odds Snapshot` is intentionally `workflow_dispatch` only. It requires repository secret `THE_ODDS_API_KEY` and uploads the snapshot as a 90-day workflow artifact.

The workflow must not be scheduled until three decisions are frozen:

1. league/bookmaker/market scope;
2. monthly API credit budget;
3. a persistent storage sink beyond expiring workflow artifacts.

A successful HTTP response is only acquisition evidence. Coverage continuity, timestamps, missingness and bookmaker stability must be audited before the source is admitted to prospective model validation.
