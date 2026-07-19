# Experiment 020 Protocol — Historical-to-prospective domain-shift audit

Status: **frozen before the workflow reads the current prospective score ledger**.

## Question

Does the untouched prospective market stream lie inside the historical feature and score support of the frozen generic action-residual model, or is transfer risk already visible before closing-price quality is evaluated?

## Frozen inputs

- generic action-shadow model artifact ID `8435876486`;
- artifact SHA-256 `53c5218fc3a0e20edcfcb7002ee08d76348e8115e590082b824cc0a16a209a37`;
- original historical hourly 1X2 tensor with archive checksum verified by the bundle manifest;
- cumulative prospective `per-book-shadow-scores.csv.gz` from the immutable `prospective-data` branch;
- historical chronological test split only for the reference distribution.

No match outcomes, settlement fields or prospective closing targets are read. No policy threshold, feature family, bookmaker, cutoff or event may be deleted after inspection.

## Comparisons

For every common observable model feature and for the raw score, residual rank score and residual uplift:

- absolute standardized mean difference;
- population stability index using historical decile bins;
- prospective fraction outside the historical 0.5%–99.5% range;
- overlap of historical and prospective central 90% intervals;
- the same diagnostics separately at T-48, T-24, T-12 and T-6 when both domains have data.

A grouped historical-vs-prospective logistic discriminator is repeated 20 times. Historical match IDs and prospective event IDs are kept intact across train/test splits so repeated rows from the same event cannot leak between folds.

## Frozen thresholds

Feature warning:

- absolute SMD at least `0.50`;
- PSI at least `0.10`;
- out-of-support fraction at least `5%`.

Feature severe shift:

- absolute SMD at least `1.00`;
- PSI at least `0.25`;
- out-of-support fraction at least `10%`.

Overall transfer-risk status:

- `insufficient_interim_volume` below 300 score rows or 20 events;
- `high_transfer_risk` when median grouped discriminator AUC is at least `0.85` or at least 25% of features are severe;
- `moderate_transfer_risk` when median AUC is at least `0.70` or at least 25% of features trigger warning;
- otherwise `low_detected_transfer_risk`.

## Evidence boundary

This audit measures covariate and model-score transfer risk only. A low detected shift does not establish predictive validity or profit. A high detected shift does not permit adapting the running seven-day policy; any repair must be preregistered as a later campaign.