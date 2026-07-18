# OddsMarket Odds Archive API — Candidate Evaluation

Status: **Tier A/S candidate — documentation verified, not sampled or connected**
Date: 2026-07-18

Official product page currently claims:

- 100+ bookmakers
- every price move recorded with 1-millisecond fractionality
- historical archive since March 2023
- mapped events across sportsbooks
- permanent API connection via flat fee or one-time pay-as-you-go runs per event

Official evidence:
- https://www.oddsmarket.org/product/odds-archive-api/

## Why it matters

If the claims survive sampling, this source may be more directly aligned with bookmaker-abnormality research than periodic snapshot products because it explicitly advertises all price moves rather than only fixed-interval snapshots.

## Unknowns that block adoption

1. Exact football league coverage by year.
2. Whether `1-millisecond fractionality` is source-native bookmaker update time, OddsMarket capture time, or timestamp precision only.
3. Availability/continuity of 1X2, Asian handicap and totals for the same bookmaker/event set.
4. Historical bookmaker churn and alias mapping.
5. Suspension/reopen and line-change semantics.
6. Bulk export versus event-metered economics at 100k+ match scale.
7. Research/storage/license restrictions.
8. Real sample payload shape and missingness.

## Required sample gate

Before any purchase at scale, obtain one month of football history covering:
- one liquid top league
- one secondary league
- at least 10 bookmakers where possible
- 1X2 + Asian handicap + totals

Measure:
- events and bookmaker continuity
- number of changes per market per match
- timestamp monotonicity and duplicate rate
- lead/lag distributions across bookmakers
- line/price change semantics
- total bytes and projected storage
- projected cost for 10k / 100k / 300k matches

Do not mark `connected` until a real sample passes this gate.
