# Market Source Economics and Acquisition Strategy

This note separates what is technically available from what is economically sensible to acquire. Figures are planning estimates and must be replaced by observed usage/vendor quotes before bulk purchase.

## 1. The Odds API

Official historical featured-market pricing formula:

`credits = 10 × number_of_regions × number_of_markets × number_of_snapshots`

Historical snapshots are documented at 10-minute intervals from 2020-06-06 and 5-minute intervals from September 2022 for covered sports/bookmakers. A historical query returns the sport's events and bookmaker states for the requested regions/markets at the closest available snapshot at or before the requested timestamp.

### Current public self-serve plans observed 2026-07-18

- 20K credits: US$30/month
- 100K credits: US$59/month
- 5M credits: US$119/month
- 15M credits: US$249/month

Historical access is included on paid plans. Provider documentation also states that empty historical responses do not consume quota, while non-empty historical usage is charged by unique returned markets × requested regions.

### What those credits mean at 5-minute resolution

Ignoring empty-response savings and assuming one request per snapshot:

| Plan | 1 region × 1 market | 2 regions × 1 market | 2 regions × 3 markets |
|---|---:|---:|---:|
| 20K | ~6.9 continuous days | ~3.5 days | ~1.2 days |
| 100K | ~34.7 days | ~17.4 days | ~5.8 days |
| 5M | ~1,736 days | ~868 days | ~289 days |
| 15M | ~5,208 days | ~2,604 days | ~868 days |

These are deliberately conservative continuous-polling equivalents, not recommended extraction plans. A soccer competition is only meaningfully priced around active fixture windows; targeted traversal can cover much more calendar history per credit.

### Practical acquisition design

1. **Do not start with every market.** First validate 1X2 continuity using the minimum region set that contains the target bookmakers.
2. **Traverse fixture windows, not calendar time.** Learn typical first-listing horizons by competition, then query only from market appearance through cutoff/kickoff.
3. **Use snapshot links.** Where available, follow `previous_timestamp` / `next_timestamp` rather than guessing unnecessary empty timestamps.
4. **Persist every paid response immutably.** Never pay twice for the same timestamp/source scope.
5. **Measure bookmaker continuity before scaling leagues.** A large credit plan is worthless if the specific bookmakers needed for the hypothesis are sparse in older seasons.
6. **Add Asian handicap/totals only after sample evidence.** Public soccer samples currently prove multi-bookmaker 1X2 schema/coverage, not deep historical AH/totals continuity.

### Current decision rule

The 5M plan is economically interesting enough that The Odds API should not be dismissed as “too expensive” before a narrow authenticated sample. However, no subscription should be bought solely from documentation. First run the repository's credit-capped sampler on a small paid plan or existing key, measure actual bookmaker continuity and returned-market cost, then decide whether 5M/15M bulk extraction is justified.

Evidence:
- https://the-odds-api.com/historical-odds-data/
- https://the-odds-api.com/liveapi/guides/v4/
- https://the-odds-api.com/

## 2. Betfair Historical Data

Betfair provides timestamped Exchange history from April 2015. It is best viewed as a market-microstructure source rather than a multi-bookmaker replacement.

The historical stack has three useful tiers:

- **Basic:** free tier, approximately 1-minute price states / last traded price, no full volume ladder. Requires a Betfair account and the data still has to be added to `My Data` before download.
- **Advanced:** approximately 1-second granularity, top-of-book/limited ladder plus volume fields.
- **Pro:** API-tick-style granularity (documented around 50ms), full price ladder plus volume.

Official bulk pricing published for soccer (verify again before purchase):

- Advanced: £69/month; 12-month bulk package £699
- Pro: £230/month; 12-month bulk package £2,299

### Acquisition strategy

1. **Exploit Basic first.** It is free and may already be sufficient to test whether Exchange price dynamics add signal.
2. Build and validate the parser/entity join on Basic before paying for higher-frequency data.
3. Upgrade a narrow month to Advanced only if one-minute last-traded-price data loses information relevant to the anomaly hypothesis.
4. Buy Pro only if full depth/tick-level fields produce measurable incremental value over Advanced.
5. Do not buy many years before join quality and experiment value are proven.

Evidence:
- https://support.developer.betfair.com/hc/en-us/articles/360002407732-What-data-is-provided-by-the-Historical-Data-service
- https://support.developer.betfair.com/hc/en-us/articles/360019984158-Are-bulk-purchase-discounts-available
- https://betfair-datascientists.github.io/data/usingHistoricDataSite/
- https://github.com/betfair/historic-data-workbook

## 3. TxODDS / Tx LAB

Tx LAB materially changes the source landscape. The vendor publicly describes:

- decades of sportsbook historical data
- 5M+ fixtures
- 800+ bookmakers
- historical pricing delivered through an API / Tx FUSION platform

This is the closest source found so far to the project's ideal retrospective dataset. Public pages do not expose transparent self-serve pricing, exact per-market timestamp granularity, or a downloadable sample sufficient for technical acceptance.

Therefore Tx LAB is **Tier S candidate, vendor-gated**.

Questions that must be answered before any commitment:

1. Does soccer history contain every price/line change or periodic snapshots?
2. Are bookmaker-native update timestamps preserved?
3. Which bookmakers have continuous 1X2, Asian handicap and totals history by year/league?
4. Can data be exported in bulk rather than metered request-by-request?
5. Are opening/closing labels derived or source-native?
6. What fields identify suspended/reopened markets?
7. What are research/storage/redistribution license restrictions?
8. What does a narrow sample (e.g. one league, one month) cost?

Evidence:
- https://txodds.net/our-products/tx-lab/
- https://txodds.net/developer-hub/

## 4. Sportmonks Premium / TXODDS prospective feed

The documented Sportmonks Premium feed stores opening odds and changes, updates pre-match odds roughly every minute, and exposes bookmaker update timestamps. Full history through the documented API is retained only until seven days after kickoff.

Therefore its main strategic value is **prospective permanent archiving**: once connected, archive every update ourselves and never rely on the seven-day retention window.

Evidence:
- https://www.sportmonks.com/football-api/premium-odds-feed/
- https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/premium-odds-feed/premium-pre-match-odds/get-all-historical-odds

## 5. Recommended acquisition order (current, revisable)

1. Free/public baselines first: Football-Data + StatsBomb Open Data for pipeline and entity experiments.
2. Add **Betfair Basic** early because it is a free historical microstructure baseline at roughly one-minute granularity.
3. Use official The Odds API public historical samples, then run a **strictly capped authenticated sample** before choosing a 5M/15M extraction plan.
4. Request Tx LAB sample/quote because it may replace a large amount of piecemeal retrospective acquisition.
5. Upgrade Betfair to Advanced/Pro only after measured incremental-value tests.
6. Select a broad prospective feed and begin permanent self-archiving as early as practical.

No source is mandatory. If a cheaper or higher-fidelity source appears, replace the stack rather than defending sunk-cost decisions.