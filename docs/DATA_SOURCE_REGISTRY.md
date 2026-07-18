# Data Source Registry

This is the living inventory for candidate and connected data sources. Do not treat inclusion here as endorsement.

For every source, record evidence rather than assumptions.

## Required evaluation fields

- Source name
- Category: odds / match / event / player / lineup / injury / news / weather / referee / venue / other
- Access method: API / bulk download / scrape / manual archive / vendor export
- Historical coverage
- Geographic / competition coverage
- Update frequency / timestamp resolution
- Whether historical `known_at` can be reconstructed reliably
- Key fields available
- Rate limits
- Cost / license constraints
- Data quality observations
- Entity-ID quality
- Raw-data preservation method
- Connection status: candidate / sampled / connected / rejected
- Evidence artifact or sample path
- Known risks

## Initial priority order

1. High-resolution historical bookmaker and exchange market states
2. Match schedules/results and stable entity identifiers
3. Lineups, injuries, suspensions, player availability
4. Event-level and advanced match data
5. Timestamped news / announcements
6. Weather, referee, venue, travel, and other contextual sources

This order is pragmatic, not permanent. A source that unlocks stronger research can move up immediately.

## Source entries

Add one section per source only after it has been investigated.

### Example template

#### Source: <name>

- **Category:**
- **Access method:**
- **Historical coverage:**
- **Timestamp resolution:**
- **Coverage:**
- **Key fields:**
- **Cost/license:**
- **Status:** candidate
- **Evidence:** none yet
- **Strengths:**
- **Risks/gaps:**
- **Decision:** investigate / connect / reject / revisit later
