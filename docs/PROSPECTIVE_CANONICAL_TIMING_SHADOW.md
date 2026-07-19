# Prospective canonical-timing coverage-normalized shadow

Status: **frozen before production activation**.

## Purpose

The outcome-blind domain-shift audit found two deployment mismatches between the historical frozen bundle and the live provider feed:

1. historical training states sit at the canonical T-48, T-24, T-12 and T-6 cutoffs, while live observations arrive throughout broader windows;
2. historical peer-book coverage was scaled to a 31-peer panel, while the live panel currently exposes about 19–20 peers.

The existing support-repaired stream addresses both mismatches conservatively by retaining only observations within 1.75 hours of a canonical cutoff. This second challenger asks whether the timing mismatch can instead be removed without discarding most otherwise valid observations.

## Frozen adapter

Adapter ID: `canonical_cutoff_coverage_normalized_v1`.

Production activation: `2026-07-19T15:00:00Z`.

Campaign end: `2026-07-26T06:30:00Z`.

For every post-activation per-book score row:

- retain only actual observations inside the historical global support `[6h, 48h]`;
- require the assigned supported closing cutoff to be one of `48, 24, 12, 6` hours;
- preserve the actual time and its distance from the assigned cutoff as audit-only columns;
- replace the model input `hours_to_commence_scaled_71` with the assigned canonical cutoff divided by 71;
- reconstruct the active peer-book count and normalize it by the contemporaneous event × context-snapshot × market panel capacity;
- recompute all normal-residual, raw and action scores from the unchanged frozen generic action-shadow bundle;
- select event candidates using the unchanged frozen candidate-selection routine.

No match result, settlement field, closing target or future snapshot is read while producing the stream.

## Evidence separation

This is a separately activated challenger. It does not replace, backfill or modify:

- the original v2 prospective shadow;
- the stricter support-constrained repair;
- either existing campaign-close evaluator.

Evidence is written to immutable run directories and a separate latest pointer on the `prospective-data` branch. Pre-activation rows are excluded even if they are already available in the cumulative source file.

## Interpretation boundary

The adapter is motivated only by outcome-blind feature-support diagnostics. It is not tuned against closing prices or match outcomes. A successful campaign-close result would support transfer of this specific adapter; it would not prove realized profit, live execution capacity or bookmaker-account durability.
