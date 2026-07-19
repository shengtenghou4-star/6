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

## First authenticated pilot guardrails

Before the paid odds request, the collector calls the active-sports endpoint and refuses to continue when the selected sport key is absent or inactive. The preflight evidence is stored in `active-sports-preflight.json` without the API key.

The first authenticated request is frozen to:

- `h2h` only;
- exactly one region, or 1–10 named bookmakers;
- one manually dispatched snapshot;
- no schedule.

The workflow default is one `uk` region. A multi-region request is rejected before the odds endpoint is called.

After collection, `scripts/audit_prospective_odds_pilot.py` automatically verifies:

- raw SHA-256 and normalized row reconciliation;
- API-key exclusion from evidence;
- quota headers and request cost;
- exact one-region or ≤10-bookmaker scope;
- complete home/draw/away states;
- minimum four complete bookmakers per event for cross-book modeling;
- provider update timestamp coverage;
- pre-commence event coverage;
- normalization diagnostics.

The audit distinguishes three claims:

1. authenticated source connected;
2. suitable for a repeated snapshot pilot;
3. suitable for untouched repricing/CLV now.

The third decision is always false for one snapshot because no transition or elapsed closing target exists yet.

## Fail-closed rules

- `THE_ODDS_API_KEY` must come from the environment or GitHub repository secret
- the key is excluded from manifests and printed output
- exactly one of `regions` or `bookmakers` must be specified
- the first pilot allows one region or 1–10 named bookmakers
- the first pilot allows `h2h` only
- inactive or unknown sport keys stop before the odds request
- decimal prices `<=1` are preserved and flagged, not silently dropped
- malformed timestamps are preserved and counted
- malformed event/bookmaker/market/outcome structures are counted
- invalid JSON preserves raw bytes plus failure evidence
- raw checksum mismatch, quota metadata failure, secret leakage or insufficient coverage prevents pilot admission

## Local invocation

```bash
export THE_ODDS_API_KEY='...'
python scripts/collect_the_odds_api_snapshot.py \
  --sport soccer_epl \
  --markets h2h \
  --regions uk \
  --output-root artifacts/prospective-odds

python scripts/audit_prospective_odds_pilot.py \
  --snapshot-root artifacts/prospective-odds \
  --output-root artifacts/prospective-pilot-audit
```

A bookmaker allow-list can be used instead of the region:

```bash
python scripts/collect_the_odds_api_snapshot.py \
  --sport soccer_epl \
  --markets h2h \
  --bookmakers bet365,pinnacle \
  --output-root artifacts/prospective-odds
```

## GitHub Actions

`Prospective Odds Snapshot` is intentionally `workflow_dispatch` only. It requires repository secret `THE_ODDS_API_KEY`, performs the active-sport preflight, enforces the frozen one-credit-equivalent scope, collects one snapshot, runs the pilot audit, and uploads both snapshot and audit as a 90-day workflow artifact.

The workflow must not be scheduled until three decisions are frozen:

1. league/bookmaker/market scope;
2. monthly API credit budget;
3. a persistent storage sink beyond expiring workflow artifacts.

A successful HTTP response is only acquisition evidence. Coverage continuity, timestamps, missingness and bookmaker stability must be audited before the source is admitted to prospective model validation.
