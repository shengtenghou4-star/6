# OpticOdds Historical Odds — Candidate Evaluation

Status: **Tier A/S candidate — official documentation verified, not sampled or connected**
Date: 2026-07-18

Official product material advertises:
- 200+ sportsbooks
- every price movement, suspension and resolution timestamped
- 25+ sports / 400+ leagues
- historical REST access and bulk export options
- historical depth of several years for many major leagues/tier-one sportsbooks, with exact depth varying by sport/book

Official developer documentation additionally states that the standard `/fixtures/odds/historical` endpoint retains data on a **rolling 2-month basis**, and full timeseries access requires additional permission.

Official evidence:
- https://opticodds.com/historical-odds
- https://developer.opticodds.com/reference/get_fixtures-odds-historical
- https://developer.opticodds.com/docs/odds-api-getting-started-guide

## Why it matters

This source is highly aligned with the project because it combines broad sportsbook coverage with explicit per-change history, suspension states and normalized fixtures/markets. It may cover both retrospective bulk acquisition and prospective live archiving through one vendor.

## Critical ambiguity

Marketing/product pages describe multi-year historical holdings and bulk export, while the standard API reference documents only a rolling two-month retention window for the historical endpoint. Therefore deep history must be treated as a **separate commercial/bulk-export entitlement until proven otherwise**.

## Required vendor/sample questions

1. What exact football history is available via bulk export by league, sportsbook and market?
2. Is every detected movement retained in the bulk archive, or are older periods downsampled?
3. What timestamps represent source update, OpticOdds capture and normalization time?
4. Are suspension/lock/unlock events preserved historically?
5. How complete are Asian handicap and totals across European/Asian sportsbooks?
6. Can a one-month raw sample be supplied before contract?
7. Pricing for 10k / 100k / 300k historical fixtures and for continuous archive access.
8. Storage/derived-feature/research publication license terms.

## Sample gate

Obtain the same benchmark slice requested from OddsMarket:
- one top league + one secondary league
- one month
- >=10 overlapping sportsbooks if available
- 1X2 + Asian handicap + totals

Compare directly on:
- changes per market-match
- timestamp semantics
- suspension visibility
- bookmaker continuity
- lead/lag recoverability
- missingness
- bytes per match
- projected acquisition cost

Do not select between OpticOdds, OddsMarket, Tx LAB or other vendors on marketing claims alone. Use the same benchmark slice and scoring protocol.
