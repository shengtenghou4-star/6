# Domain-transfer blueprints

The transferable abstraction is:

> Model an agent's expected reaction to its observable market, measure the abnormal reaction, and test whether that residual predicts the same agent's later price.

This document converts broad ideas into executable second-domain profiles. None is currently claimed as empirical transfer.

## Priority ranking

| Rank | Domain | Scientific fit | Data accessibility | Identity clarity | Execution difficulty | Recommended role |
|---:|---|---:|---:|---:|---:|---|
| 1 | Prediction markets across venues | High | Medium-high | High | Medium | Best first real replication |
| 2 | Cross-exchange crypto quotes | High | High | High | High-volume engineering | Best large-sample stress test |
| 3 | Travel marketplace prices | Medium-high | Medium | High | Collection intensive | Best non-finance public demo |
| 4 | Insurance quote panels | Very high | Low | High | Access constrained | Best long-term research partnership |

## Blueprint 1 - prediction markets

### Research question

After conditioning on cross-venue contract state, does one venue's abnormal probability update predict that venue's later price?

### MARB mapping

- Entity: resolved event contract.
- Agent: prediction-market venue or market maker.
- Instrument: fixed YES/NO claim.
- Action: venue probability or best-quote change.
- State: own price, cross-venue consensus, spread, depth, time to resolution and recent news-window controls.
- Expected action: next update predicted from contemporaneous cross-venue state.
- Residual: observed update minus expected update.
- Target: later same-venue midprice or executable quote.

### Minimum viable dataset

- At least two venues listing equivalent contracts.
- Timestamp resolution sufficient to establish ordering.
- Stable contract entity mapping.
- Both sides or a justified one-dimensional probability representation.
- Resolution time and later quote availability.

### Primary falsification

Within venue × horizon × baseline-score groups, circularly shift residual uplift across contracts while preserving raw scores, contract identity class and exact quota.

### Main threats

- supposedly equivalent contracts may have different settlement language;
- sparse or stale quotes can create artificial lead-lag;
- common news can reach venues at different timestamps;
- automated market-maker mechanics may make action predictable for structural reasons.

### Frozen success criterion

Positive residual-uplift slope with entity-cluster lower bound above zero, placebo probability at or below 0.01, and positive leave-one-venue-out support where three or more venues exist.

## Blueprint 2 - cross-exchange crypto pricing

### Research question

Does an exchange's abnormal response to cross-exchange order-book state predict its own later midprice or microprice?

### MARB mapping

- Entity: asset × episode.
- Agent: exchange.
- Instrument: fixed spot or perpetual contract.
- Action: midprice, spread or depth-adjusted microprice change.
- State: cross-exchange consensus, spread, depth imbalance, volatility, latency and funding where relevant.
- Residual: realized exchange move minus expected move.
- Target: later same-exchange midprice or volume-weighted executable price.

### Design adaptations

Events are continuous rather than naturally separated. Define non-overlapping episodes or cluster by asset × time block to avoid pseudo-replication. Use strict clock synchronization and record data-arrival latency separately from exchange timestamps.

### Primary falsification

Shift residuals within exchange × asset × volatility-regime × horizon blocks. Preserve baseline score, market regime and opportunity count.

### Main threats

- exchange timestamps are not directly comparable;
- arbitrage mechanically forces convergence;
- data vendors may backfill order-book updates;
- thousands of overlapping observations create overstated precision.

### Best contribution

A successful profile would test whether MARB scales from sparse football snapshots to dense continuous markets. Even a null result would reveal whether the football mechanism depends on slower decentralized repricing.

## Blueprint 3 - travel pricing panels

### Research question

Does a hotel's or airline seller's abnormal price revision relative to marketplace state predict its own later listed price?

### MARB mapping

- Entity: property/route × stay/travel date × product class.
- Agent: seller or listing channel.
- Instrument: fixed room/fare product with cancellation and baggage terms held constant.
- Action: listed-price change.
- State: peer prices, occupancy proxies, days to service, weekday, event calendar and inventory availability.
- Target: later same-seller price for the same product.

### Data contract

Product equivalence is the central challenge. Room type, refundability, taxes, occupancy and inclusions must be normalized before identity is frozen.

### Primary falsification

Shift residual uplift within seller × destination/route × lead-time × product-class blocks while preserving baseline score and exact selection quota.

### Main threats

- product attributes change with price;
- personalization or cookies may alter observations;
- inventory disappearance is informative missingness;
- scraping terms and redistribution rights require careful review.

### Best contribution

This is the clearest non-betting public demonstration because price revisions and peer panels are intuitive, but collection and product normalization are expensive.

## Blueprint 4 - insurance quote panels

### Research question

After conditioning on applicant risk and peer quotes, does an insurer's abnormal quote revision predict its own later quote or acceptance price?

### MARB mapping

- Entity: applicant-risk profile × coverage specification.
- Agent: insurer.
- Instrument: fixed coverage and deductible.
- Action: quote revision or bind/decline movement.
- State: anonymized risk variables, peer quote panel, channel and time since application.
- Target: later same-insurer quote or final bindable premium.

### Scientific advantage

Insurance is conceptually close to bookmaker pricing: multiple agents observe shared risk information, apply private models and manage heterogeneous liabilities.

### Main barrier

Public data rarely contain repeated synchronized quote panels. This profile likely requires a broker, comparison platform, insurer or controlled quote-collection partnership.

### Governance requirements

- strict privacy and de-identification;
- no protected-trait proxy misuse;
- audit of quote-request side effects;
- clear distinction between pricing research and underwriting decisions.

## Recommended first real profile

Prediction markets should be attempted first because agent and instrument identity are relatively clear, later same-agent prices are observable and the study can remain close to the original mechanism without being another sports-betting dataset.

The minimum acceptable first replication should:

1. use a source not involved in football model development;
2. freeze the profile before inspecting residual-target results;
3. include at least two agents and multiple horizons;
4. publish a failed or null result unchanged;
5. enter the MARB catalog at no higher than the evidence tier actually passed.

## Intake checklist

Before collecting data, complete `benchmark/PROFILE_TEMPLATE.md` and answer:

- Can identical instruments be matched without looking at future outcomes?
- Are source timestamps trustworthy and comparable?
- Is the later same-agent target observable?
- Can residual alignment be broken without destroying all market structure?
- Are there enough independent entities for clustered uncertainty?
- Do source terms permit the planned storage and publication?
- Is there a clean prospective activation boundary?

A domain that cannot answer these questions should remain a research idea rather than become a weak profile.