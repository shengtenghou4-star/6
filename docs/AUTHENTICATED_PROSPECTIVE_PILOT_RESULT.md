# First authenticated prospective odds pilot result

Status: **source connected; repeated snapshot pilot admitted**

Run: `29674672082`

## Immutable evidence

- workflow conclusion: success
- artifact: `prospective-odds-snapshot-29674672082`
- artifact digest: `sha256:b9c16bae04b09babfe28be40f6a6a34823e07d512bbf5ae557b989f507943871`
- snapshot ID: `20260719T052009_386334Z__soccer_epl__5829e2ac2142`
- raw response SHA-256: `5829e2ac21428f8850021b52f8d52c434217844c4344a0004217efb7e15fcc29`
- provider: The Odds API v4
- request: `soccer_epl`, `h2h`, region `uk`
- HTTP status: 200

## Real coverage

- 10 future events
- 20 unique bookmaker keys
- 199 complete event × bookmaker H/D/A quote states
- 657 normalized outcome rows
- 19–20 complete bookmakers per event
- median 20 complete bookmakers per event
- all 10 events passed the minimum four-bookmaker cross-market coverage gate
- provider update timestamps present on 100% of complete quote states
- all complete quote states were pre-commence
- median provider update age at ingestion: 28.386 seconds
- maximum provider update age at ingestion: 166.386 seconds
- zero malformed events, bookmakers, markets or outcomes
- zero invalid commence, bookmaker-update, market-update or decimal-price fields

Observed bookmaker keys:

- betano_uk
- betfair_ex_uk
- betfair_sb_uk
- betfred_uk
- betvictor
- betway
- boylesports
- casumo
- coral
- grosvenor
- ladbrokes_uk
- leovegas
- livescorebet
- paddypower
- skybet
- smarkets
- sport888
- unibet_uk
- virginbet
- williamhill

The provider also emitted `h2h_lay` rows for exchange books. They remain preserved in raw/normalized evidence but were not counted as `h2h` quote states for the frozen pilot admission gate.

## Quota and secret audit

- request cost: 1 credit
- credits used: 1
- credits remaining: 499
- API-key parameter markers in evidence: none
- exact secret matches in evidence: none
- raw checksum verification: passed
- normalized row/event/bookmaker/market reconciliation: passed

## Decision

The authenticated source is connected and the real sample is suitable for a repeated prospective snapshot pilot.

This single snapshot is **not** sufficient for quote-transition, abnormal-action, closing-CLV, alpha or profit claims. Those require multiple untouched snapshots of the same events, formation of valid three-snapshot chains, and elapsed same-book closing targets.

The next phase should collect a small frozen sequence under an explicit credit budget, preserve immutable snapshots, generate quote/transition ledgers, apply the generic action-residual shadow bundle, and wait for closing prices before opening the prospective CLV gate.
