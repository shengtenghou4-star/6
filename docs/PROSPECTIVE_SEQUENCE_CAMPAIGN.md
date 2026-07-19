# Budgeted near-event prospective sequence campaign

## Purpose

This seven-day campaign converts the authenticated source connection into untouched multi-snapshot quote sequences near kickoff. It is designed to create valid three-snapshot action-residual chains inside the historically supported closing windows without opening match outcomes or making executable betting claims.

## Frozen campaign window and budget

- start: `2026-07-19T06:00:00Z`
- end: `2026-07-26T06:30:00Z`
- cadence: every three hours at minute 47
- maximum scheduled runs: 56
- maximum paid sports per run: 4
- maximum request cost per run: 4 credits
- maximum campaign cost: 224 credits
- market: `h2h`
- region: `uk`
- event scouting horizon: next 60 hours

The active-sports and events endpoints are used for scouting before paid odds requests. Only competitions with upcoming events inside the horizon can be selected. Selection is deterministic and capped before any paid request.

## Fixed competition allow-list

The campaign may choose from active summer competitions including MLS, Brazil Série A/B, Argentina, Liga MX, Chile, Finland, Norway, Sweden, Korea, China, Ireland, Copa Libertadores, Copa Sudamericana and Denmark.

Each run weights events closer to kickoff more heavily while retaining event-count density. At most four competitions are selected.

## Persistent evidence

The default branch contains code and frozen policies. A dedicated `prospective-data` branch stores:

- immutable raw response directories;
- normalized outcomes and source manifests;
- quota and coverage audits;
- per-run scouting/selection manifests;
- accumulated quote, transition and provisional closing-target ledgers;
- latest and run-specific action-residual shadow state.

Every snapshot retains ingestion time, bookmaker/market update times, raw SHA-256, event identity and request scope.

## Sequence and shadow path

After each run:

1. all accumulated snapshots are verified;
2. complete H/D/A quote states are canonicalized;
3. consecutive same-book transitions are generated;
4. contemporaneous peer consensus and movement are reconstructed;
5. provisional same-book closing targets are materialized from the latest pre-commence observation;
6. once three observations overlap, the frozen generic model bundle calculates abnormal action residuals;
7. only chains in these windows are scored:
   - 36–60 hours → T-48;
   - 18–36 hours → T-24;
   - 9–18 hours → T-12;
   - 4–9 hours → T-6.

The raw-market model fixes bookmaker/outcome candidate identity. Contemporaneous action residuals only rerank that fixed candidate. Every output remains `research_only`, `no_execution` and `unvalidated_prospective_transfer`.

## Fail-closed rules

The campaign stops or excludes affected evidence when it encounters:

- missing repository secret;
- execution outside the frozen date window;
- request cost above the per-run ceiling;
- API-key material in evidence;
- raw checksum mismatch;
- invalid timestamps or prices;
- malformed or incomplete H/D/A quote states;
- invalid observation chronology;
- mixed or tampered model bundle;
- post-commence shadow observations.

Insufficient overlap and an absence of historically supported chains are recorded as explicit non-error states so that valid raw collection is not discarded while evidence accumulates.

## Evidence boundary

This phase can establish:

- real provider continuity;
- multi-book quote-transition availability;
- prospective abnormal-action signal generation;
- untouched closing-price-quality evidence once closing observations have elapsed.

It cannot establish fills, limits, realized ROI, scalable profit or bookmaker intent.
