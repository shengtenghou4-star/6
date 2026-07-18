# Sample Evidence 006 — Official The Odds API Multi-League Historical Samples

Credential-free official provider samples were fetched and preserved through GitHub Actions.

## EPL sample

- provider snapshot: `2021-10-29T23:55:00Z`
- 20 events
- 13 bookmaker keys
- 240 `h2h` bookmaker-market blocks + 30 exchange `h2h_lay` blocks
- 810 outcome quote rows
- notable books include Betfair, BetVictor, Coral, Ladbrokes, Matchbook, Paddy Power, Sky Bet and William Hill

## Bundesliga sample

- provider snapshot: `2022-10-18T01:55:39Z`
- 18 events
- 12 bookmaker keys
- 197 `h2h` bookmaker-market blocks + 27 exchange `h2h_lay` blocks
- 672 outcome quote rows
- notable books include Betfair, Matchbook, Pinnacle, William Hill, Unibet EU and 1xBet

## What this proves

The provider's documented historical schema is usable across at least two football leagues/regions and preserves snapshot time plus bookmaker-level states.

## What this does not prove

- authenticated historical access is not yet connected
- continuity of any bookmaker across seasons is not yet measured
- Asian handicap/totals historical depth is not established by these public soccer samples
- sample success is not evidence that bulk extraction economics are acceptable

Workflow artifact digest: `sha256:68d60a99e4c70f6e93b6b13ed6f9c95b53683a37c9c076733d08f778bcb9906c`.