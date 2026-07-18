# Sample Evidence 014 — Independent Exact-Change Football Odds Source

Validated by direct public Kaggle API download and inspection of the actual files.

## Archive

- dataset: `eladsil/football-games-odds`
- archive bytes: 5,301,601
- SHA-256: `20baff7a0d65fc667225187430af7b13eab4b27e56695a8bc4f907e8c498f6f9`
- files: `Matches_Odds.csv`, `Matches_Results.csv`

## Odds-change layer

`Matches_Odds.csv`:

- 461,144 timestamped quote-state rows
- 32,345 unique matches
- 545 competitions
- quote timestamps from 2016-12-23 through 2018-05-23
- scheduled match starts over the same period
- median 13 updates per match
- mean 14.26 updates per match
- p90 27; p99 44; max 174
- 0 consecutive exact duplicate rows

Fields:

- match ID
- scheduled start
- competition
- quote-state timestamp (`date_created`)
- home/away team names
- home/draw/away odds

There is **no bookmaker column**. This source must be treated as one global/provider feed, not multi-bookmaker history.

## Pre-match safety

1,003 quote rows (0.2175%) have `date_created` after scheduled `date_start`. Those rows must be excluded from pre-match research; the source is not assumed to have cleaned this automatically.

Invalid/nonordinary values <=1 were also explicitly counted:

- home odds: 3
- away odds: 3
- draw odds: 76

They must not silently enter ordinary decimal-odds models.

## Results layer

`Matches_Results.csv`:

- 32,508 rows
- 32,348 unique match IDs
- 3 result-side match IDs have no corresponding odds rows in the odds-change file

Joins therefore must remain explicit rather than assuming perfect universe equality.

## Research role

This is a useful **independent exact-timestamp single-feed replication source**. It cannot validate cross-bookmaker lead/lag or named-bookmaker-specific behavior, but it can independently test:

- move/no-move hazard structure
- time-to-next-change dynamics
- state-dependent movement rates
- whether abnormal residual methodology generalizes beyond the Beat The Bookie hourly tensor

Workflow artifact digest: `sha256:9bdd1f9a28313b72cc67b6eb637ae41cd3d52728181f3cf8fdb4ab3711b76cd1`.