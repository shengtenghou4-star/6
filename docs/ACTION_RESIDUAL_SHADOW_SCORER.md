# Generic action-residual shadow scorer

This component turns the historical bookmaker-behavior architecture into a reproducible, outcome-blind prospective research scorer.

It does not place bets and must not be described as proven bookmaker intent, executable alpha or future profit.

## Frozen architecture

The historical bundle deliberately removes bookmaker identity from every model input.

1. A generic normal-action model estimates whether a bookmaker should move and the conditional H/D/A probability change.
2. Once the next quote is actually observed, the scorer computes:
   - conditional residual = actual probability change − predicted conditional change;
   - unconditional action residual = actual probability change − predicted move probability × predicted conditional change.
3. A generic raw closing model proposes the bookmaker/outcome direction.
4. The contemporaneous action-residual closing model scores that same raw candidate identity for ranking.
5. Residual-driven candidate replacement is emitted only as secondary research output.

This follows Experiments 012–014:

- contemporaneous action residuals carried the historical economic signal;
- residual ranking was stronger than residual candidate replacement;
- conditional closing-direction information transferred across unseen bookmakers, while economic transfer remained unpromoted.

## Exact prospective data requirement

A score requires three ordered snapshots for the same event × bookmaker × market:

- prior snapshot;
- context snapshot, used to predict the next action;
- newly realized snapshot, used to calculate the abnormal action residual.

The Phase 32 quote ledger and transition ledger provide the required provenance and cross-book state.

The adapter reconstructs the exact 30 generic historical normal-action inputs:

- own prior/current H/D/A fair probabilities and their change;
- prior/current overround and change;
- peer consensus prior/current and change;
- current target-versus-consensus deviation;
- current peer dispersion;
- peer coverage scaled by the historical 31-book denominator;
- fraction of peer books moving;
- hours to event scaled by the historical 71-hour denominator.

The closing models were trained only at T-48h, T-24h, T-12h and T-6h. Prospective context states are accepted only in the following frozen, non-overlapping support windows:

- T-48 bucket: 36–60 hours before event;
- T-24 bucket: 18–<36 hours;
- T-12 bucket: 9–<18 hours;
- T-6 bucket: 4–<9 hours.

Rows are rejected or excluded when they are post-commence, outside those historical support windows, non-consecutive, missing peer consensus, non-finite or inconsistent with the frozen feature order.

## Build a model bundle

```bash
python scripts/build_generic_action_shadow_bundle.py \
  --output-root artifacts/generic-action-shadow-bundle
```

The bundle contains twelve joblib model files and a manifest with:

- source archive checksum;
- chronological training policy;
- exact feature order;
- model classes and parameters;
- training counts;
- residual equations;
- exact Python, scikit-learn and joblib runtime versions;
- per-file SHA-256 hashes;
- explicit research-only flags.

The loader verifies runtime compatibility before unpickling any model and rejects mismatched Python major/minor, scikit-learn or joblib versions. The project pins the serialization-sensitive scikit-learn and joblib versions used by the workflow.

Model binaries are uploaded as workflow artifacts and are not committed to the repository.

## Score prospective sequences

```bash
python scripts/score_prospective_action_shadow.py \
  --bundle-root artifacts/generic-action-shadow-bundle/bundle \
  --quote-ledger artifacts/prospective-sequences/quote-ledger.csv.gz \
  --transitions artifacts/prospective-sequences/consecutive-transitions.csv.gz \
  --output-root artifacts/prospective-shadow-scores
```

Outputs:

- `per-book-shadow-scores.csv.gz`: normal-action expectations, realized action residuals, raw candidate direction, action rank score and full snapshot/bundle provenance;
- `event-shadow-candidates.csv.gz`: one raw-market bookmaker/outcome candidate per event and newly observed snapshot, with its action-residual rank score;
- `manifest.json`: input/output hashes, chain diagnostics and policy flags.

Every output row is marked:

- `research_only = true`;
- `no_execution = true`;
- `unvalidated_prospective_transfer = true`.

## Evidence boundary

Historical experiments support abnormal quote-action residuals as a durable closing-line research signal and support their use as a confidence/ranking layer. They do not establish future fills, limits, latency feasibility, realized profit or transferable live alpha. Those claims require untouched authenticated prospective snapshots and elapsed closing prices.
