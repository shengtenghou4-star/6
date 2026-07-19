# Synthetic MARB profile

## Purpose

This profile is a deterministic contract test for the Market Action Residual Benchmark. It demonstrates that the benchmark can recover a known residual-to-future-price relationship while preserving fixed agent and instrument identity.

It is **simulation only**. It supplies no evidence that the football result transfers to another real market.

## Data-generating process

The generator creates a panel of independent opportunities with:

- eight pricing agents;
- three fixed instruments;
- four horizons;
- two observable market-state variables;
- an expected agent action;
- a realized action equal to expected action plus a random abnormal component;
- a raw future-price score based only on market state;
- a residual score that adds the abnormal-action component;
- a future same-agent price-quality target containing a known positive residual coefficient;
- a realized-return variable deliberately generated independently of the price-quality mechanism.

The raw and residual scores refer to the same preassigned agent and instrument. The residual score can rerank opportunities but cannot switch identity.

## Frozen checks

A successful run must show:

1. positive within-stratum residual-uplift slope;
2. bootstrap lower bound above zero;
3. correctly aligned slope above the 99th percentile of chronological within-stratum circular-shift placebos;
4. positive slope at each horizon;
5. a valid MARB submission at evidence tier `executed`;
6. economic execution and prospective transfer remaining unvalidated.

## Run

```bash
python scripts/run_synthetic_marb_profile.py \
  --output-root artifacts/synthetic-marb-profile

python scripts/validate_benchmark_submission.py \
  artifacts/synthetic-marb-profile/submission.json
```

## Interpretation boundary

Passing this profile validates software behavior and benchmark semantics under a known data-generating process. It does not validate causal identification on observed markets, empirical transport, profitability or execution.
