# Prospective odds sequence ledger

This pipeline converts immutable The Odds API snapshots into leakage-safe, outcome-blind market sequences.

## Inputs and integrity

Only snapshot directories containing `manifest.json`, `raw-response.json`, and `normalized-outcomes.csv` are discovered. Every raw response SHA-256 and normalized row count is verified against its manifest. Duplicate snapshot identities and non-increasing ingestion timestamps fail closed.

## Derived artifacts

- `quote-ledger.csv.gz`: one complete H/D/A state per snapshot, event, bookmaker and market, with raw odds, de-vigged probabilities, overround, provider update timestamps, quote-change flags, time to event and cross-book consensus excluding the target bookmaker.
- `consecutive-transitions.csv.gz`: target-book move/no-move and probability deltas between consecutive observed states, with peer-book movement fraction and complete snapshot provenance.
- `closing-targets.csv.gz`: every strictly pre-commence observation joined to the same bookmaker's final valid strictly pre-commence state, including H/D/A fair-probability movement and raw log-odds closing-line value.
- `manifest.json`: deterministic row counts, diagnostics, hashes and explicit outcome-blind policy.

Post-commence states may remain visible in the quote ledger for audit diagnostics, but they are never eligible as closing observations or closing targets. Incomplete, ambiguous or invalid quote groups are counted and excluded rather than repaired.

## Usage

```bash
python scripts/build_prospective_sequence_ledger.py \
  --snapshots-root artifacts/prospective-odds \
  --output-root artifacts/prospective-sequences \
  --market h2h \
  --minimum-other-books 3
```

This phase creates collection and target infrastructure only. It does not score residuals, use match outcomes, or claim alpha, execution quality or profit.
