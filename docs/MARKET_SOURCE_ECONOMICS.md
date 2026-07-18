# Market Source Economics and Acquisition Strategy

This note separates what is technically available from what is economically sensible to acquire. Figures are planning estimates and must be replaced by observed usage/vendor quotes before bulk purchase.

## 1. The Odds API

Official historical featured-market pricing formula:

`credits = 10 × number_of_regions × number_of_markets × number_of_snapshots`

Historical snapshots are documented at 10-minute intervals from 2020-06-06 and 5-minute intervals from September 2022 for covered sports/bookmakers. A historical query returns the sport's events and bookmaker states for the requested regions/markets at the closest available snapshot at or before the requested timestamp.

### Illustrative credit budgets

For one soccer competition, continuously polling three regions and three featured markets:

- per snapshot: 90 credits
- 24 hours at 5-minute resolution: 288 snapshots = 25,920 credits
- 30 days continuous: 777,600 credits
- 270-day season continuous: 6,998,400 credits

This means brute-force continuous backfill is possible but wasteful at scale. The query returns all currently listed events in a sport, so extraction should exploit fixture calendars and only traverse windows in which relevant pre-match markets exist.

### Better strategy

1. Start with 1X2 only and a small region/bookmaker set to measure coverage continuity.
2. Learn how early each competition is normally listed.
3. Traverse only active pre-match windows rather than every five minutes of an entire calendar year.
4. Add regions/markets only when sample evidence shows incremental value.
5. Store responses permanently so no timestamp is paid for twice.

Important caveat: official documentation states that spreads and totals are mainly available for US sports/bookmakers. Soccer Asian-handicap and totals depth must be measured empirically before treating The Odds API as the core AH source.

Evidence:
- https://the-odds-api.com/historical-odds-data/
- https://the-odds-api.com/liveapi/guides/v4/
- https://the-odds-api.com/

## 2. Betfair Historical Data

Betfair provides timestamped Exchange history from April 2015. It is best viewed as a market-microstructure source rather than a multi-bookmaker replacement.

Official bulk pricing published for soccer (verify again before purchase):

- Advanced: £69/month; 12-month bulk package £699
- Pro: £230/month; 12-month bulk package £2,299

Acquisition strategy:

1. Obtain the smallest practical soccer sample/month first.
2. Measure whether Advanced already contains sufficient price/volume state for our research questions.
3. Buy Pro only if order-book depth fields materially improve experiments.
4. Do not buy many years before entity joins and parser correctness are proven.

Evidence:
- https://support.developer.betfair.com/hc/en-us/articles/360002407732-What-data-is-provided-by-the-Historical-Data-service
- https://support.developer.betfair.com/hc/en-us/articles/360019984158-Are-bulk-purchase-discounts-available

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
2. Obtain official The Odds API public historical samples and then a small paid historical test if needed.
3. Obtain a narrow Betfair historical package/sample for exchange microstructure.
4. Request Tx LAB sample/quote because it may replace a large amount of piecemeal retrospective acquisition.
5. Select a broad prospective feed and begin permanent self-archiving as early as practical.

No source is mandatory. If a cheaper or higher-fidelity source appears, replace the stack rather than defending sunk-cost decisions.
