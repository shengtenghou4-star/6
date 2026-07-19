# Prospective matched-budget 5% shadow

Status: **v2 quota repair frozen before activation**.

- v1 activation: `2026-07-19T07:00:00Z`
- v2 activation: `2026-07-19T11:00:00Z`

## Purpose

Experiment 016 found strong per-trade closing CLV for a 5% positive-rank policy but did not pass its original total-capacity and concentration gate. This policy is therefore not promoted. It is retained only as a prospectively timestamped challenger against a matched-budget raw baseline.

## v1 defect and evidence boundary

The v1 implementation used `max(1, floor(group_size × 0.05))`. For nonempty groups smaller than 20, one selection exceeds the stated 5% cap. The first materialized v1 ledger had 18 eligible rows across 10 snapshot/cutoff groups and selected 10 rows per policy.

All v1 raw snapshots, candidate scores, manifests and artifacts remain preserved. The v1 selection flags are **operational diagnostics only** and cannot support a confirmatory “5%” claim.

## Frozen v2 rules

The source is the existing prospective event-candidate ledger. Raw-market models continue to fix bookmaker and outcome identity.

Within each `realized_snapshot_id × supported_closing_cutoff_hours` group:

- **raw matched baseline**: require `raw_candidate_score > 0`, then select the highest-scoring `floor(group_size × 0.05)` rows;
- **residual challenger**: require `action_rank_score_for_raw_candidate > 0`, then select the highest-scoring `floor(group_size × 0.05)` rows.

There is no minimum-one override. Groups smaller than 20 select zero rows. If fewer positive-score candidates exist than the quota, all positive-score candidates are selected. The implementation records under-capacity groups, realized selection fractions and any fraction breach; a breach is a hard failure.

Policy IDs:

- `raw_positive_top_5pct_v2_exact_floor`
- `residual_positive_top_5pct_v2_exact_floor`

## Guardrails

- v2 rows before the new activation are excluded even when old snapshots are rebuilt later;
- no outcome or settlement data is read;
- no adaptive threshold, bookmaker deletion, outcome deletion or cutoff deletion;
- both policies share the same raw-selected candidate identity;
- selection flags, overlap, group sizes, score percentiles and provenance are persisted;
- research-only, no-execution status is explicit in every manifest.

## Campaign-close confirmatory evaluation

Tiny per-sport snapshot groups may be structurally unable to instantiate an exact 5% live quota. The confirmatory analysis will therefore use the full untouched campaign candidate cohort within each supported cutoff. Raw identity and both scores were generated prospectively; the 5% cohort policy is frozen before campaign close. Policy ledgers must be written and hashed before elapsed same-book closing targets are joined.

That evaluation is outcome-blind and may establish prospective closing-price ranking value. It does not establish fills, account limits or realized profit.
