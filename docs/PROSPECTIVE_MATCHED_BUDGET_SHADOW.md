# Prospective matched-budget 5% shadow

Status: frozen before activation.

Activation: `2026-07-19T07:00:00Z`

## Purpose

Experiment 016 found strong per-trade closing CLV for a 5% positive-rank policy but did not pass its original total-capacity and concentration gate. This policy is therefore not promoted. It is retained only as a prospectively timestamped challenger against a matched-budget raw baseline.

## Frozen rules

The source is the existing prospective event-candidate ledger. Raw-market models continue to fix bookmaker and outcome identity.

Within each `realized_snapshot_id × supported_closing_cutoff_hours` group:

- **raw matched baseline**: require `raw_candidate_score > 0`, then select the top 5% by raw score;
- **residual challenger**: require `action_rank_score_for_raw_candidate > 0`, then select the top 5% by action rank score.

The denominator is all event candidates in the group. Selection count is `floor(group_size × 0.05)`, with a minimum of one when the group is nonempty. If fewer eligible candidates exist, all eligible candidates are selected.

## Guardrails

- rows before activation are excluded even when old snapshots are rebuilt later;
- no outcome or settlement data is read;
- no adaptive threshold, bookmaker deletion, outcome deletion or cutoff deletion;
- both policies share the same raw-selected candidate identity;
- selection flags, overlap, group sizes, score percentiles and provenance are persisted;
- research-only, no-execution status is explicit in every manifest.

Later evaluation must use elapsed same-book prices and must preserve this activation boundary.