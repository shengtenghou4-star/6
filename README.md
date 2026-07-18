# Football Market Behavior Lab

A research-first football betting market project focused on discovering reproducible signals from bookmaker behavior, market structure, match context, and related information.

## Current working hypothesis

A useful starting hypothesis is that bookmaker behavior can be modeled conditionally: learn what a bookmaker would normally do under comparable market conditions, measure deviations from that expected behavior, and test whether those deviations contain incremental information about future outcomes or market states.

This is **not a permanent doctrine**. It is a falsifiable starting point. The project may pivot if evidence supports a better target, representation, model, or research framework.

## Non-negotiable principles

- No future-information leakage or timestamp cheating.
- Raw source data should be preserved whenever practical.
- Every important result must be reproducible from code, data version, configuration, and experiment record.
- Negative results are first-class results; do not hide failed hypotheses.
- Do not claim a signal, model, or data source works without measurable evidence.
- Separate exploratory findings from validated out-of-sample findings.
- Research direction, features, models, data sources, and agent roles remain revisable.

## Initial project areas

- `docs/` — research charter, data scope, decisions, experiment notes
- `src/collectors/` — data ingestion adapters
- `src/normalization/` — entity resolution and canonical schemas
- `src/features/` — feature generation
- `src/models/` — modeling code
- `src/audit/` — leakage, quality, reproducibility checks
- `src/backtest/` — evaluation and strategy testing
- `configs/` — source/model/experiment configuration
- `tests/` — tests and regression checks

The repository starts deliberately light. Structure should grow only when real work requires it.
