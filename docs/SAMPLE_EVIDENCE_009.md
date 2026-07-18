# Sample Evidence 009 — StatsBomb Open Event Lake

Validated from the current official `statsbomb/open-data` repository snapshot through GitHub Actions.

## Source snapshot

- source commit: `b0bc9f22dd77c206ddedc1d742893b3bbe64baec`
- raw archive bytes: 1,677,877,254
- raw archive SHA-256: `9813a34aa8b04f5e702a00abfcfbefc75845a4e57d24fafc31c8343f95dc3e9d`
- 8,987 archive files; 8,977 data files

## Verified coverage

- competition/season rows: 80
- matches: 3,961 unique matches
- event files: 4,235
- event records: **14,874,171**
- lineup files: 4,235
- lineup team entries: 8,470
- lineup player entries: 161,958
- 360 files: 426 total; 425 valid
- 360 records in valid files: **1,381,467**

## Source defect handling

One upstream 360 file (`3845506.json`) is malformed JSON. It is explicitly identified in the profile and excluded from valid-360 counts. Match, event and lineup layers have zero parse failures. No silent repair or invented data was performed.

## Research use

This layer is selective historical coverage, not the universal match spine. Event/360 data are realized during matches and therefore cannot be treated as pre-match-known features. They are suitable for lagged team/player/process feature engineering when the experiment cutoff guarantees the underlying history was already known.

Workflow artifact digest: `sha256:1a9deed9b45868efb6a523477944753893751d9d46a7b1d920b040c6af5b2d04`.