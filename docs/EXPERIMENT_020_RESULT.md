# Experiment 020 Result — Historical-to-prospective domain-shift audit

Status: **completed; the current sample is too small for a final transfer-risk label, but the full-schema audit exposes two material structural mismatches that require a separately frozen parallel repair**.

Run: `29685076585`

Artifact digest: `sha256:fbc2b912e6b34dda9ae67540058b9688fc5d6d981e367f6f37316a4aaf1e610c`

## Frozen comparison

The audit reconstructed the exact generic bundle's historical chronological test distribution and compared all 49 frozen model inputs and score fields with the untouched prospective per-book score ledger.

Historical reference:

- 403,248 book/cutoff rows;
- 18,072 matches;
- T-48, T-24, T-12 and T-6 all represented;
- exact generic bundle ID and manifest checksum verified.

Prospective checkpoint:

- 895 scored book/cutoff rows;
- 15 unique events;
- 12 snapshots;
- 21 bookmakers;
- T-48: 172 rows;
- T-24: 320 rows;
- T-6: 403 rows;
- no T-12 rows yet.

No match outcomes, settlement data or prospective closing targets were read.

## Full-schema shift

Across all 49 frozen fields:

- median absolute standardized mean difference: `0.1013`;
- median population-stability index: `0.1854`;
- median prospective out-of-support fraction: `0.0%`;
- median central-90% interval overlap: `81.52%`;
- 31 fields crossed at least one warning threshold;
- 23 fields crossed at least one severe threshold.

The grouped historical-versus-prospective discriminator remained only moderately separable:

- median AUC: `0.6339`;
- mean AUC: `0.6264`;
- 10th–90th percentile: `[0.5377, 0.7057]`.

Because the prospective sample contains only 15 events, below the frozen 20-event minimum, the formal status remains `insufficient_interim_volume`. If the volume gate were ignored, the severe-feature share would already trigger the frozen high-transfer-risk rule; that is a warning, not a final classification.

## Structural mismatches

### Source-breadth feature

`active_other_books_scaled_31` had:

- PSI: `9.2778`;
- absolute SMD: `0.2175`;
- central-90% overlap: `29.41%`.

The historical tensor could expose up to 31 peer books, while the current provider panel contains roughly twenty. This is a structural feature-definition mismatch rather than ordinary sampling noise.

### Time-to-kickoff support

`hours_to_commence_scaled_71` had:

- PSI: `3.6582`;
- prospective out-of-historical-support fraction: `47.93%`;
- central-90% overlap: `81.11%`.

The historical bundle was trained at exact T-48/T-24/T-12/T-6 states, while the prospective adapter accepts broad 36–60h, 18–36h, 9–18h and 4–9h windows. Nearly half of current rows therefore fall outside the historical 0.5%–99.5% time-feature range.

### Market-state composition

Own-price, consensus-price and observation-probability fields showed large PSI values despite mostly moderate standardized mean differences. With only 15 events, part of this can reflect the current fixture mix; it must be remeasured as event coverage grows.

Overround fields were more directly concerning: prospective out-of-support rates were approximately 9.5%–10.3%, including `observation_overround` at `10.28%`.

## Supported interpretation

The model is not obviously encountering a wholly alien market—the grouped discriminator is far below the frozen 0.85 high-risk threshold—but the current adapter does not reproduce two important historical input conditions: peer-book breadth and exact cutoff timing.

The correct response is not to rewrite the running v2 evidence. Its rows remain untouched and valid as a test of the originally frozen deployment. A separately preregistered parallel challenger should instead test:

1. narrow nearest-cutoff timing support;
2. a coverage-robust historical bundle whose peer-book features remain valid under smaller source panels.

The audit will also be rerun automatically or manually after more prospective events accumulate. No predictive, CLV or profit conclusion follows from this domain-only diagnostic.