# Generic action-residual shadow bundle result

Status: **infrastructure completed; prospective transfer remains unvalidated**

## Built model bundle

Bundle ID:

`generic-action-shadow-v1-8bb898c3c067`

The workflow trained and serialized twelve bookmaker-identity-free models:

- generic normal move hazard;
- three generic conditional next-action H/D/A delta models;
- generic raw closing-move hazard;
- three generic raw conditional closing-delta models;
- generic contemporaneous-action-residual closing hazard;
- three generic action-residual conditional closing-delta models.

Historical training scale:

- normal hazard: `500,000` training states;
- normal conditional action: `400,000` mover states;
- closing models: `238,090` validation quote states;
- conditional closing models: `205,293` future-moving states;
- closing-model validation coverage: `11,826` matches and eight historical bookmaker slots.

No bookmaker one-hot or bookmaker identity field is present in any model input.

## Frozen feature contracts

- normal-action features: `30`;
- raw closing features: `38`;
- contemporaneous action-residual fields: `8`;
- action-augmented closing features: `46`.

The exact ordered feature lists are stored in the bundle manifest and verified by the loader.

## Prospective adapter

The scorer consumes the Phase 32 quote and transition ledgers and requires a three-snapshot chain:

1. prior state;
2. context state used for the normal-action forecast;
3. newly observed state used to form the abnormal action residual.

It reconstructs the historical generic normal-reaction inputs, computes conditional and unconditional H/D/A action residuals, and emits:

- the generic raw-market bookmaker/outcome candidate;
- the action-residual ranking score for that exact fixed identity;
- a secondary action-residual replacement candidate;
- complete snapshot, raw-response and bundle provenance.

Prospective closing scoring is restricted to the historically supported windows around T-48h, T-24h, T-12h and T-6h. Post-commence, unsupported-horizon, missing-consensus and invalid chains are excluded or rejected.

## Historical compatibility safeguards

A dedicated regression test locks the exact Experiment 008/011/013 scoring convention:

- normal-action conditional deltas are projected back to the probability simplex before residual formation;
- closing-delta regressors are used directly for candidate ranking and are **not** reprojected.

This prevents a superficially reasonable implementation change from silently changing the historical signal definition.

## Serialization and integrity

Final runtime:

- Python `3.11`;
- scikit-learn `1.9.0`;
- joblib `1.5.3`;
- NumPy `2.4.6`;
- pandas `2.3.3`.

The serialization-sensitive scikit-learn and joblib versions are pinned. The loader checks Python major/minor, scikit-learn and joblib compatibility before unpickling any model.

Every model file has a SHA-256 checksum. The final manifest checksum is:

`1bc04196e86b9802eedba50411f834e5155de814dffccc16289f6c65d12da757`

All twelve model hashes were independently reconciled against the uploaded artifact.

## Validation

- all repository CI tests passed;
- shadow feature-order, three-snapshot alignment and stale provider timestamp tests passed;
- post-commence and missing-consensus rejection tests passed;
- supported historical horizon tests passed;
- bundle tampering and runtime mismatch rejection tests passed;
- historical closing-delta compatibility test passed;
- all model predictions passed finite-value smoke checks;
- the full model-bundle workflow completed successfully.

## Evidence boundary

Every score is explicitly marked:

- `research_only = true`;
- `no_execution = true`;
- `unvalidated_prospective_transfer = true`.

The bundle operationalizes the strongest historical mechanism found so far: the raw market proposes direction and contemporaneous action residuals rank confidence. Experiment 014 supported unseen-book conditional direction transfer but did not promote unseen-book economic transfer. Therefore this bundle is a shadow research instrument, not a betting system.

Untouched authenticated prospective snapshots and elapsed closing prices remain necessary before any live closing-CLV claim.

Workflow artifact digest:

`sha256:53c5218fc3a0e20edcfcb7002ee08d76348e8115e590082b824cc0a16a209a37`
