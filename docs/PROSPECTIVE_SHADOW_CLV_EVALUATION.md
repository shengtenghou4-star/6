# Prospective action-shadow closing-CLV evaluation

This is the untouched prospective price-quality gate for the generic action-residual ranker.

It uses no match outcomes and cannot establish realized profit, fills, limits or scalability.

## Observation unit

Each observation is the single generic raw-market bookmaker/outcome candidate selected for one event at one newly realized snapshot.

The candidate identity remains fixed. The action-residual model is allowed only to rerank that same identity.

Candidates are joined to Phase 32 closing targets using the exact tuple:

- event ID;
- bookmaker key;
- market key;
- realized observation snapshot ID.

Every supplied candidate must have exactly one matching closing target. The evaluator fails closed rather than silently dropping candidates whose closing evidence is absent.

The evaluator rejects mixed model bundles, duplicate observation identities, unsupported cutoff buckets, false research-policy flags, invalid bundle checksums, non-finite ranking scores, forbidden result fields and invalid observation → close → commence chronology.

## Frozen support

Only the Phase 34 supported closing buckets are eligible:

- T-48h;
- T-24h;
- T-12h;
- T-6h.

One evaluation may contain only one frozen bundle ID and one bundle manifest checksum.

## Frozen strategies

Within each realized snapshot × cutoff bucket:

- **baseline** ranks the fixed candidates by `raw_candidate_score`;
- **action ranker** ranks the same fixed candidates by `action_rank_score_for_raw_candidate`;
- each strategy selects exactly the top 20%;
- deterministic ties use event ID, bookmaker key and outcome;
- a group needs at least 20 candidates to create trades.

Undersized groups remain in the evaluation ledger and are explicitly marked ineligible; they are not silently removed.

## Frozen metrics

For the selected candidate identity:

- closing log-odds CLV;
- closing fair-probability CLV;
- mean trade CLV;
- mean per-opportunity CLV;
- action-minus-baseline per-opportunity log-CLV;
- event-cluster bootstrap confidence intervals;
- point lift by T-48/T-24/T-12/T-6 bucket.

Repeated observations of the same event are clustered together in bootstrap resampling.

## Minimum evidence gate

Promotion cannot be evaluated until all are true:

- at least 1,000 unique events;
- at least 20 eligible snapshot × cutoff groups;
- at least 200 unique events in each of the four cutoff buckets.

## Frozen promotion gate

All must pass:

1. the evidence-volume gate;
2. action-minus-baseline opportunity log-CLV bootstrap CI above zero;
3. action strategy trade log-CLV bootstrap CI above zero;
4. positive action mean trade fair-probability CLV;
5. positive action-minus-baseline point lift in at least three of four cutoff buckets.

No threshold, trade fraction, grouping rule, bootstrap unit or promotion condition may be changed after real prospective closing values are opened.

## Usage

```bash
python scripts/evaluate_prospective_action_shadow_clv.py \
  --candidates artifacts/prospective-shadow-scores/event-shadow-candidates.csv.gz \
  --closing-targets artifacts/prospective-sequences/closing-targets.csv.gz \
  --output-root artifacts/prospective-shadow-evaluation
```

Outputs:

- `prospective-evaluation-ledger.csv.gz`: every joined candidate, eligibility flag, baseline/action trade flags and per-opportunity CLV;
- `result.json`: evidence volume, strategy metrics, bootstrap intervals and frozen promotion checks;
- `manifest.json`: exact input/output hashes, policy and bundle provenance.

Passing this gate would establish untouched prospective closing-price quality for the generic action-residual ranker. It would still not establish realized ROI or executable profit.
