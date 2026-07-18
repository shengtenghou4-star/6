# Sample Evidence 013 — Original BeatTheBookie SQL Archive Recovery Probe

The original authors' public source code/README documents exact-update SQL data with named bookmakers and `odds_datetime`, which would be materially richer than the derived hourly Kaggle tensor.

## Dropbox archive probes

Two original README links were probed non-destructively:

- `odds_series_sql_db.zip`
- `odds_series_b_sql_db.zip`

Both URLs returned HTTP 200 **HTML landing/error content rather than ZIP bytes**:

- content type: `text/html; charset=utf-8`
- no ZIP `PK` signature
- no usable content range / downloadable archive metadata

Therefore the historical Dropbox links are **not counted as live data sources**.

## Google Drive fallback

The historical Google Drive route referenced by the original project currently redirects into a Google sign-in/access flow rather than exposing a directly downloadable public SQL archive in our reproducible environment. It is treated as account/access gated until proven otherwise.

## Decision

The exact-update named-bookmaker SQL data are not recovered in this phase. No source-availability claim is made from old README links alone.

Fallback for immediate research:

- use the actually acquired 92,647-match hourly tensor
- use the verified primary-source bookmaker-slot mapping and time semantics
- keep the SQL recovery path open only if a valid mirror, owner-provided link or authenticated public export becomes available

The modern BeatTheBookie data service is a separate API product and is not assumed to expose these historical exact-update SQL tables.

Probe workflow artifact digest: `sha256:bd420441c9f391346e6ec410a991f693702fb9f40d193730b356fd13fd11fa5a`.