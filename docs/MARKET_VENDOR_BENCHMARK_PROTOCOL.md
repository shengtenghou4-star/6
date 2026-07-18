# Historical Market Vendor Benchmark Protocol

Purpose: compare candidate high-resolution market-history sources on the same evidence, not marketing claims.

Candidates can enter or leave at any time. Current examples include Tx LAB/TXODDS, OddsMarket Archive API, OpticOdds historical/bulk, The Odds API snapshots and other credible sources discovered later.

## Fixed benchmark slice

Where vendor coverage permits, request the same slice:

- one high-liquidity European top league
- one secondary European league
- one complete calendar month with completed fixtures
- pre-match only for the first comparison
- 1X2, Asian handicap, totals
- at least 10 overlapping sportsbooks, including several globally important books where available

If a vendor cannot provide this exact slice, record the deviation rather than silently choosing a more favorable sample.

## Evidence required

Preserve the raw delivered payload/export unchanged.
Record:
- vendor/product/version
- request/export parameters
- retrieval date
- license/entitlement
- source file hashes
- source-native IDs
- all timestamp fields and vendor definitions

## Quantitative scorecard

### 1. Fixture coverage
- requested fixtures
- returned fixtures
- missing fixture rate
- duplicate/mapping conflict rate

### 2. Sportsbook continuity
For each sportsbook × market:
- fixtures covered
- median first quote time before kickoff
- median last pre-kickoff quote time
- gaps >5m / >15m / >60m where applicable
- disappearance/suspension observability

### 3. Movement fidelity
- total updates
- unique price changes
- unique line changes
- duplicate consecutive states
- median/95th percentile update interval
- changes per match-market-book

### 4. Timestamp semantics
Classify every timestamp as one of:
- bookmaker/source-native update time
- vendor capture/first-seen time
- snapshot time
- ingestion/export time
- unknown

Measure:
- monotonicity violations
- identical timestamps across distinct changes
- precision versus actual empirical resolution

Do not award high timestamp scores merely for millisecond-formatted numbers.

### 5. Market semantics
Audit:
- 1X2 home/draw/away identity
- Asian handicap sign/home-away conventions
- quarter-line representation
- totals line/selection semantics
- odds format conversions
- opening/closing definitions
- suspension/lock/unlock representation

### 6. Cross-source overlap
On overlapping fixtures/books:
- price agreement at matched times
- missing moves unique to each source
- timestamp lead/lag distributions
- mapping conflicts

Disagreement is evidence to investigate, not automatically an error in either source.

### 7. Economics
Calculate observed:
- acquisition cost per 1k fixtures
- cost per million update records
- projected 10k/100k/300k-fixture backfill cost
- ongoing monthly prospective archive cost
- engineering/API-rate-limit burden

### 8. Research fitness
Score separately for:
- normal-bookmaker-behavior modeling
- lead/lag discovery
- abnormal residual detection
- outcome/profit backtests
- exact historical `known_at`

## Decision rule

No single composite score is mandatory. Preserve the component scores because different research lanes may use different vendors.

A cheaper source may be optimal for broad coverage while a deeper source is used for a smaller microstructure subset.

No vendor becomes canonical truth merely because it is selected. Raw provenance and cross-source disagreement must remain preserved.
