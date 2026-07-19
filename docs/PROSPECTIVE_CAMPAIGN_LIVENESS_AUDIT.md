# Prospective campaign liveness audit

Status: **engineering safeguard; outcome-blind and independent of all evidence gates**.

The seven-day campaign is scheduled every three hours. This audit runs after the expected collection window and checks that the persistent `prospective-data` state is fresh and internally aligned.

It verifies:

- the newest immutable snapshot is no more than 4.5 hours old while the campaign is active;
- the accumulated sequence manifest is materialized;
- sequence quote-ledger and transition hashes match the original shadow inputs;
- the original per-book score hash matches the source hash used by each available parallel adapter;
- no manifest claims to have used match outcomes or closing targets during scoring.

The audit makes no provider request and reads no results, winners, settlements or closing-price performance. It cannot change scores, candidate selection, activation boundaries or final evaluation gates.

Each scheduled audit is persisted immutably on the `prospective-data` branch. An unhealthy result is committed first and then fails the workflow so that missing collection or stale derived state becomes visible rather than silently reducing the untouched cohort.
