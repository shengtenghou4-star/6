# Sample Evidence 012 — 32-Bookmaker × 72-Hour Odds Tensor Audit

The full acquired Beat The Bookie time-series tensor was audited through GitHub Actions using chunked numeric processing.

## Reconciliation

- `odds_series.csv.gz`: 31,074 rows
- `odds_series_b.csv.gz`: 61,573 rows
- combined: **92,647 matches**
- schema per row verified exactly: 5 identity/result fields + 6,912 odds cells = 32 bookmaker slots × 3 outcomes × 72 time indices

## Time-axis evidence

Primary-source generator code now verifies:

- index 0 ≈ T-71h
- index 71 ≈ T-0h / kickoff marker
- `hours_before_kickoff = 71 - time_index`

Independent structural evidence strongly agrees: combined quote coverage rises from about 18.14% at index 0 to 51.58% at index 71, with Pearson correlation ≈ **0.9897** between time index and quote coverage.

## Market-density growth toward kickoff

First file:
- quote coverage: ~20.19% → ~49.13%
- mean complete bookmakers per match: ~6.16 → ~14.72

Second file:
- quote coverage: ~17.11% → ~52.82%
- mean complete bookmakers per match: ~5.47 → ~16.90

This confirms that the tensor contains materially increasing market participation and update density toward kickoff rather than a flat repeated snapshot.

## Movement density

Adjacent-index quote-change rates rise materially near kickoff.

- first file: roughly 3.2% at the earliest transition, peaking near 29.6% before the final transition
- second file: roughly 4.1% at the earliest transition and reaching ~45.5% at the final transition

This supports treating bookmaker action intensity and consensus movement as time-dependent conditional behavior rather than using one global static baseline.

## Data-quality findings

Finite values at or below decimal odds 1.0 were found:

- first file: 3,162 values
- second file: 3,818 values

These values are invalid as ordinary decimal odds and must be excluded or interpreted only with explicit source semantics. They are not silently accepted as valid prices.

Observed maxima also include very large longshot prices (up to 250 and 1251 respectively), so later modeling should use robust transforms/caps only under a frozen protocol rather than ad hoc deletion.

## Bookmaker identity

The historical `b1`–`b32` slots are no longer treated as unknowable. Their source mapping and verified time-axis semantics are frozen separately in `docs/BEAT_SOURCE_SEMANTICS.md` from the original authors' generator/unpacker code.

## Research implication

The dataset is structurally adequate for a first conditional normal-market-behavior model:

- repeated time-ordered bookmaker states
- cross-book consensus available at each indexed hour
- bookmaker identity available through source mapping
- movement and relative-deviation features can be built without using future indices

It remains a derived hourly representation. Exact raw update timestamps from the original SQL archives would be superior if recoverable.

Workflow artifact digest: `sha256:b5c27d0376aa979657bc48b50f2b4f3f847d5dd24f458c209b338ed0d808ab06`.