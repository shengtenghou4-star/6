# Data Source Registry

This is a living inventory of candidate and connected data sources. Inclusion is not endorsement. Research direction and source choices may change when evidence changes.

The project should distinguish two acquisition problems:

1. **Retrospective backfill** — reconstruct as much trustworthy history as possible.
2. **Prospective permanent archive** — from the day collection starts, preserve every raw update so future research is not limited by vendor retention windows.

## Non-negotiable evaluation fields

For every source, record evidence rather than assumptions:

- category and access method
- historical / geographic / competition coverage
- update frequency and timestamp resolution
- whether historical `known_at` can be reconstructed reliably
- fields, identifiers, rate limits, cost and licensing constraints
- raw preservation method
- status: candidate / sampled / connected / rejected
- evidence and known risks

---

## Market / odds sources

### Source: The Odds API

- **Category:** multi-bookmaker odds
- **Access:** JSON REST API
- **Historical coverage:** featured-market snapshots from 2020-06-06 for covered sports/bookmakers; 10-minute snapshots initially, 5-minute snapshots from September 2022. Additional markets available historically from May 2023 at 5-minute snapshots.
- **Coverage:** global bookmaker regions; provider advertises 40+ / 50+ bookmakers depending page and current coverage. Soccer coverage exists, but exact bookmaker/market/league history must be sampled before commitment.
- **Markets:** featured markets include h2h/1X2 and, where supported, spreads/handicaps and totals; additional event markets vary.
- **Timestamp quality:** strong snapshot timestamp; responses also expose bookmaker `last_update`. Snapshot time is not necessarily the exact moment an underlying bookmaker changed a quote.
- **Historical `known_at`:** **good but not perfect**. Safe if using source snapshot time conservatively.
- **Cost:** paid historical access. Query-credit economics may become material for multi-year, many-league, many-market extraction.
- **Status:** **candidate — authoritative documentation verified, not yet connected**.
- **Evidence:** https://the-odds-api.com/historical-odds-data/ ; https://the-odds-api.com/liveapi/guides/v4/
- **Strengths:** easiest documented multi-bookmaker historical snapshot source; clean JSON; explicit previous/next snapshot pointers.
- **Risks/gaps:** historical availability starts only when each sport/bookmaker/market was added; full-football Asian handicap/totals coverage must be sampled; brute-force global extraction may consume many credits.
- **Decision:** **Tier A backfill candidate. Build a credit/cost estimator and sample EPL + one secondary league before buying scale.**

### Source: Betfair Historical Data

- **Category:** exchange market microstructure
- **Access:** purchased bulk files + Historical Data API
- **Historical coverage:** detailed Exchange market data from April 2015; older data exists only via older/other formats.
- **Coverage:** Betfair Exchange markets, including soccer.
- **Fields:** market definitions, prices, settlement; Advanced/Pro streams can expose order-book style available-to-back/lay updates and volumes depending package.
- **Timestamp quality:** very high for exchange changes; historical format mirrors Exchange Stream API and includes publish timestamps.
- **Historical `known_at`:** **excellent for Betfair market state**.
- **Cost:** Basic/Advanced/Pro packages. Official 2026 bulk pricing lists Soccer Advanced at £69/month or £699/year and Pro at £230/month or £2,299/year for a 12-month package.
- **Status:** **candidate — authoritative documentation and sample messages verified, not purchased/connected**.
- **Evidence:** https://support.developer.betfair.com/hc/en-us/articles/360002407732-What-data-is-provided-by-the-Historical-Data-service ; https://support.developer.betfair.com/hc/en-us/articles/360018468438-Advanced-Historical-Data-How-do-I-interpret-updates ; https://support.developer.betfair.com/hc/en-us/articles/360019984158-Are-bulk-purchase-discounts-available
- **Strengths:** deepest currently identified source for price-discovery mechanics, liquidity, traded/available volume and exact exchange evolution.
- **Risks/gaps:** exchange, not bookmaker; cannot by itself represent bookmaker intent; full multi-year Advanced/Pro history is expensive; jurisdiction/account access restrictions apply.
- **Decision:** **Tier A microstructure source. Buy/sample a narrow month first, not a decade blind.**

### Source: Sportmonks Premium Odds Feed / TXODDS

- **Category:** broad real-time multi-bookmaker odds
- **Access:** paid API add-on
- **Coverage:** documented 120+ international bookmakers; broad markets including match result, over/under, Asian handicap, correct score and more.
- **History behavior:** opening odd plus subsequent changes are stored, with update timestamps / `bookmaker_update`, but full change history is publicly documented as accessible only until 7 days after fixture start.
- **Timestamp quality:** strong prospectively.
- **Historical `known_at`:** **excellent if we archive continuously ourselves; weak for deep retrospective backfill because public retention is short**.
- **Status:** **candidate for prospective collector; not a standalone deep-history solution**.
- **Evidence:** https://www.sportmonks.com/glossary/premium-odds-feed/ ; https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/premium-odds-feed/premium-pre-match-odds/get-all-historical-odds ; https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/premium-odds-feed/premium-pre-match-odds/get-updated-premium-odds-between-time-range
- **Strengths:** widest documented bookmaker coverage found in this pass; integrated fixture/bookmaker/market IDs; every change can be captured going forward.
- **Risks/gaps:** seven-day historical retention means missing archive windows are unrecoverable through the documented API; pricing for premium add-on requires vendor contact.
- **Decision:** **Tier A prospective archive candidate. If selected, collector must run continuously and preserve raw responses permanently. Ask vendor/TXODDS separately about bulk historical licensing.**

### Source: Football-Data.co.uk

- **Category:** results + low-frequency historical bookmaker odds / match stats
- **Access:** CSV/Excel downloads
- **Historical coverage:** league result files back to 1993/94 for available competitions; odds availability varies by era. Closing Pinnacle 1X2 is documented back to 2012/13, with earlier seasons often pre-closing only.
- **Timestamp quality:** low for market microstructure; mostly match-level open/pre-close/close style fields rather than full trajectories.
- **Historical `known_at`:** adequate only for coarse benchmark features, not intraday behavior.
- **Status:** **candidate baseline/backfill source**.
- **Evidence:** https://www.football-data.co.uk/data.php ; https://www.football-data.co.uk/downloadm.php
- **Strengths:** cheap/free long horizon; simple CSV; useful for sanity checks, outcome labels and baseline closing-line studies.
- **Risks/gaps:** not a high-frequency market source; upstream odds/statistics compilation uses third-party sources; fields change across eras.
- **Decision:** **use as baseline and validation layer, never as the main abnormal-bookmaker-behavior dataset.**

### Source: API-Football odds

- **Category:** odds + football API
- **Access:** API
- **History behavior:** pre-match odds provided 1–14 days before fixture and only a 7-day history is retained; documented update interval about 3 hours. In-play odds history is not stored.
- **Historical `known_at`:** weak for deep retrospective research, usable prospectively if self-archived.
- **Status:** **backup candidate, lower priority for odds**.
- **Evidence:** https://www.api-football.com/documentation-beta
- **Decision:** **do not use as core odds-history source unless a sample reveals unique coverage/value.**

---

## Match, entity, lineup, injury and referee sources

### Source: Sportmonks Football API v3

- **Category:** fixtures / leagues / teams / players / lineups / injuries / referees / venues
- **Access:** API
- **Coverage:** provider documents 2,300+ football leagues overall.
- **Lineups:** confirmed and predictive lineups supported; fixture metadata exposes whether a lineup is confirmed.
- **Injuries/suspensions:** `sidelined` and `sidelinedHistory` expose player/team/season, type, start/end dates, games missed and completion state.
- **Entity IDs:** strong source-native fixture/team/player/league/venue IDs and naturally integrated with its odds feeds.
- **Historical `known_at`:** **mixed**. Historical absence periods and confirmed lineups do not automatically prove the exact time the information first became public. For strict pre-match causal work, preserve first-seen ingestion timestamps prospectively.
- **Status:** **primary entity-spine candidate, not yet connected**.
- **Evidence:** https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/introduction ; https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/lineups-and-formations ; https://www.sportmonks.com/glossary/injuries-and-suspensions/
- **Strengths:** one provider can link fixtures, teams, players, lineups, sidelined records, referees, venues and odds.
- **Risks/gaps:** coverage quality varies by league; retrospective first-known timestamps for injuries/lineups require validation.
- **Decision:** **best current candidate for source-native backbone. Our own canonical IDs must remain vendor-independent.**

### Source: API-Football

- **Category:** fixtures / teams / players / lineups / injuries / odds
- **Access:** API
- **Injury coverage:** injury endpoint available from April 2021; updated about every 4 hours.
- **Historical `known_at`:** uncertain; current/history records do not by themselves guarantee first-publication timestamp.
- **Status:** **secondary/cross-check candidate**.
- **Evidence:** https://www.api-football.com/documentation-beta
- **Decision:** **use for coverage comparison or gap filling after sampling, not as canonical truth by default.**

---

## Event-level / advanced football data

### Source: StatsBomb Open Data

- **Category:** matches / events / lineups / selected 360 data
- **Access:** GitHub JSON bulk files
- **Coverage:** selected competitions/seasons only; not a universal match spine.
- **Fields:** competition/season files, matches, event streams, lineups and 360 data for selected matches.
- **Timestamp quality:** event timestamps are excellent for within-match sequence; dataset availability timestamps are not pre-match `known_at` for betting research.
- **Status:** **candidate / public sample verified through official repository**.
- **Evidence:** https://github.com/statsbomb/open-data
- **Strengths:** high-quality event schema; ideal for feature engineering prototypes and validating whether richer football-process variables add value.
- **Risks/gaps:** limited competition coverage; post-match event data cannot be used as if known pre-match.
- **Decision:** **use as event-feature R&D source, not universal production coverage.**

---

## News / public-information sources

### Source: GDELT 2.0

- **Category:** global news metadata / article discovery / entities/themes
- **Access:** bulk datasets, BigQuery, APIs
- **Historical coverage:** GDELT 2.0 Event/GKG era from 2015 onward; core feeds update every 15 minutes.
- **Timestamp quality:** useful `first-seen` style timing; exact publisher timestamps are not universal. GDELT's Article List documentation notes only roughly 30% of articles expose exact publication timestamps, otherwise the time may reflect when GDELT saw the article.
- **Historical `known_at`:** **conservative first-seen timestamps can be useful; claimed publication time must not be trusted blindly**.
- **Status:** **candidate**.
- **Evidence:** https://www.gdeltproject.org/data.html ; https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/ ; https://blog.gdeltproject.org/announcing-the-gdelt-article-list-rss-feed/
- **Strengths:** huge, global, multilingual, long-running and open.
- **Risks/gaps:** noisy for football-specific injury/team news; source article retrieval/licensing and entity disambiguation require work.
- **Decision:** **use as broad discovery/firehose, not sole source of truth for team news.**

### Source: NewsAPI

- **Category:** news article discovery
- **Access:** API
- **Historical coverage:** `/everything` currently documents search over the last 5 years, plan-dependent.
- **Fields:** source, author, title, description, URL, `publishedAt`, truncated content.
- **Historical `known_at`:** moderate; `publishedAt` is useful but should be audited against source pages for critical signals.
- **Status:** **candidate**.
- **Evidence:** https://newsapi.org/docs/endpoints/everything ; https://newsapi.org/docs/endpoints
- **Strengths:** simple search/filter API and UTC publication timestamps.
- **Risks/gaps:** article body is truncated; history limited; publication edits/reposts can distort timestamps.
- **Decision:** **secondary discovery source. Direct club/league/reporter feeds should be archived prospectively where permitted.**

---

## Weather / environmental context

### Source: Open-Meteo

- **Category:** weather / historical forecasts
- **Access:** API
- **Historical actual/reanalysis coverage:** historical weather back to 1940 using ERA5-class datasets; hourly variables available.
- **Historical forecast coverage:** high-resolution historical forecast series generally starts around 2021; exact archived individual model runs have shorter coverage depending model.
- **Timestamp quality:** excellent for weather valid time; `known_at` depends on which product is used.
- **Critical leakage rule:** **do not use realized match-time weather as though it was known before the betting decision.** For a pre-match model, use a forecast that had actually been issued before the prediction cutoff, or clearly label realized weather as ex-post context only.
- **Status:** **candidate, technically straightforward**.
- **Evidence:** https://open-meteo.com/en/docs/historical-weather-api ; https://open-meteo.com/en/docs/historical-forecast-api ; https://open-meteo.com/en/docs/single-runs-api
- **Decision:** **use; exact forecast-vintage reconstruction must be explicit in feature metadata.**

---

# Current recommended source stack

## A. Retrospective research stack

1. **Betfair Historical Data** — deep exchange microstructure and liquidity/price-discovery benchmark.
2. **The Odds API** — multi-bookmaker historical snapshots from 2020+, subject to cost/coverage sampling.
3. **Football-Data.co.uk** — long-horizon coarse odds/results baseline.
4. **Sportmonks or API-Football** — fixtures/entities/lineups/injuries after sample-quality comparison.
5. **StatsBomb Open Data** — event-level feature R&D on covered competitions.
6. **GDELT / NewsAPI** — historical public-information discovery with timestamp caveats.
7. **Open-Meteo** — weather and, where possible, vintage forecast reconstruction.

## B. Prospective permanent archive stack

Start as early as practical:

- continuously archive a broad multi-bookmaker feed (leading candidate: Sportmonks Premium/TXODDS, subject to pricing/sample)
- archive Betfair Exchange stream or equivalent market-state data
- snapshot fixture/entity/lineup/injury state with ingestion timestamps
- preserve official club/league announcements and selected trusted news/reporter feeds with first-seen time
- preserve raw payloads before normalization

The prospective archive is strategically important because several commercial feeds only retain change history briefly. Every day we delay is historical data we may never recover.

---

# Biggest unresolved gap

No source identified in this first pass publicly guarantees all three simultaneously:

1. many years of history,
2. 100+ bookmakers with every pre-match price change,
3. low-cost bulk retrospective access.

Therefore the next action is **not** to launch a giant scrape. It is to run narrow samples and cost models for The Odds API, Betfair, and Sportmonks/TXODDS; ask vendors explicitly about bulk historical exports; then choose the cheapest source combination that preserves timestamp integrity.
