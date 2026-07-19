# Prospective support-repaired shadow

Status: **parallel adapter frozen before activation**.

Activation: `2026-07-19T12:00:00Z`

Adapter ID: `support_constrained_coverage_normalized_v1`

## Purpose

Experiment 020 found two outcome-blind deployment mismatches between the frozen historical bundle and the current prospective adapter:

1. the historical model was trained at exact T-48/T-24/T-12/T-6 states, while the original prospective adapter admits broad cutoff windows;
2. the historical peer-coverage feature used a 31-book denominator, while the current provider panel is materially smaller.

This protocol creates a separate parallel shadow. It does not replace, amend or reinterpret the original v2 prospective evidence.

## Frozen timing support

For each prospectively scored book row:

- reconstruct actual context time to kickoff from `hours_to_commence_scaled_71 × 71`;
- retain only rows no more than `1.75` hours from their assigned canonical cutoff;
- require actual time to kickoff within the global historical range `[6, 48]` hours;
- preserve and report every excluded row by cutoff.

Thus T-48 rows above 48 hours and T-6 rows below 6 hours cannot enter this parallel stream.

## Frozen coverage normalization

- reconstruct active peer count as `active_other_books_scaled_31 × 31`;
- require exact integer reconciliation within numerical tolerance;
- define the contemporaneous panel peer capacity as the maximum active peer count within `event_id × context_snapshot_id × market_key`;
- require capacity of at least three peers;
- replace the model feature with `active_peer_count / inferred_panel_peer_capacity`;
- retain the original feature and inferred counts for audit.

The transformed row is rescored from the original frozen generic bundle. Normal-action residuals, raw closing scores and action-rank scores are all recomputed. The raw model continues to determine bookmaker/outcome candidate identity; residual information only reranks that identity.

## Evidence boundary

- rows before activation are excluded;
- no match outcomes, settlement fields or closing targets are read;
- the original v2 ledger remains immutable and primary for its preregistered test;
- the repaired ledger is explicitly unvalidated, research-only and non-executable;
- no adaptive tolerance, cutoff deletion, bookmaker deletion or result-driven transformation is allowed.

## Outputs

- repaired per-book score ledger;
- repaired event-candidate ledger;
- source, bundle and output SHA-256 hashes;
- timing, panel-capacity and score-change diagnostics;
- immutable scheduled evidence on the `prospective-data` branch.

A separate campaign-close evaluator must be frozen before any closing target is attached to this repaired stream.