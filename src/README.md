# Source Code

Code should be added as real needs appear. Avoid prematurely building a large architecture.

Likely modules may include:

- `collectors/` — source-specific ingestion adapters
- `normalization/` — canonical IDs, schema normalization, timestamp normalization
- `features/` — reproducible feature pipelines
- `models/` — baselines and research models
- `audit/` — leakage, provenance, data-quality, replication checks
- `backtest/` — out-of-sample evaluation and economic simulation

These directories are suggestions, not constraints. Refactor when evidence or workflow demands it.

Every collector should eventually expose enough metadata to answer:

- Where did this record come from?
- When was the underlying information actually known?
- When was it ingested?
- Can the raw source record be recovered or audited?
- Can the same extraction be reproduced?
