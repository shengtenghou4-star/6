# Prospective post-collection workflow DAG

Status: engineering orchestration only; no evidence rule changes.

A successful `Prospective Sequence Campaign` run now immediately triggers the strict support-repaired stream, canonical-timing stream and outcome-blind evidence-volume forecast. The canonical stream then triggers campaign-liveness and adapter-coverage checks.

Scheduled cron entries remain as fallbacks. All writers rebase and retry before pushing to `prospective-data`, and the coverage audit requires the original, strict-repair and canonical manifests to reference the same original per-book score hash.

This orchestration changes latency and collision handling only. It does not alter source data, activation boundaries, candidate scores, policy quotas or final promotion gates.
