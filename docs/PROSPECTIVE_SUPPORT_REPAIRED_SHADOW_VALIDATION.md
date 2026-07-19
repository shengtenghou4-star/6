# Prospective support-repaired shadow — Engineering validation

Status: **full scoring path validated on accumulated outcome-blind rows; production evidence still begins at the frozen `2026-07-19T12:00:00Z` activation**.

Run: `29685621491`

Artifact digest: `sha256:f327cecfafdca9ffc0b5be8e442e1fbbf8713ba9e1faba4b22f313c88d8eda37`

## Validation boundary

The pull-request validation deliberately used `2026-07-19T06:00:00Z` so the complete repair and rescoring path could be exercised against already-persisted outcome-blind rows. This earlier boundary is **engineering validation only**. The production workflow remains frozen at `2026-07-19T12:00:00Z`; no validation row may enter the production repaired campaign.

No closing targets, match outcomes or settlement fields were read.

## Input and support filter

- input per-book score rows: `895`;
- input events: `15` before support filtering;
- input bookmakers: `21`;
- timing-supported rows: `146`;
- timing-excluded rows: `749`.

By assigned cutoff:

- T-48: `172` rows, `0` inside the ±1.75h and [6h, 48h] support rule;
- T-24: `320` rows, `0` supported;
- T-6: `403` rows, `146` supported;
- T-12 had no current prospective rows.

The strict filter therefore retained three snapshots covering four events and seven event-level candidates. This validates the filter and scoring machinery while confirming that the already-accumulated snapshot timing was mostly far from canonical historical cutoffs.

## Coverage normalization

Among retained rows:

- inferred contemporaneous peer-panel capacity ranged from `19` to `20`, median `20`;
- median original `active_other_books_scaled_31` was `0.6452`;
- median panel-normalized active-peer feature was `1.0`.

All active-peer counts reconciled to integers and every panel met the minimum three-peer requirement.

## Score impact

Rescoring with the frozen bundle changed the scores modestly but nontrivially:

- raw-score mean absolute change: `0.0001607`;
- action-rank-score mean absolute change: `0.0001047`;
- raw Pearson correlation: `0.9981`;
- raw Spearman correlation: `0.9919`;
- action Pearson correlation: `0.9978`;
- action Spearman correlation: `0.9963`.

Thus coverage normalization does not create an unrelated model, but it does alter some opportunity ordering—the intended purpose of the parallel transfer repair.

## Supported interpretation

The support-repaired adapter now runs end to end, fails closed on unsupported timing and invalid coverage, recomputes every residual and closing score from the frozen bundle, and produces separate hashed per-book and event ledgers. Its production evidence begins only after the frozen activation and remains unvalidated until the separately preregistered campaign-close evaluation.