# Sample Evidence 007 — Football-Data Market-Field Coverage Atlas

Validated over the full quality-filtered Football-Data archive through GitHub Actions.

## Verified scope

- 240,014 valid match rows
- 684 season/division groups
- 222 unioned source/provenance columns inspected
- 183 columns conservatively classified as market-related
  - 114 first-set / exact-time-unknown market fields
  - 69 closing market fields
- 21 realized match-stat fields blocked from pre-match use
- 6 outcome/score fields blocked from pre-match use
- 2 unresolved source columns retained explicitly as unknown (`""` and `LB`); neither is automatically approved for modeling

## Longest broad bookmaker coverage observed

Examples of non-empty coarse 1X2 fields across the archive:

- Bet365 H/D/A: 182,368 rows, 24 seasons, 22 divisions
- William Hill H/D/A: 180,454 rows, 25 seasons, 22 divisions
- Interwetten H/D/A: about 173.6k rows, 24 seasons, 22 divisions
- Bet&Win H/D/A: 165,076 rows, 22 seasons, 22 divisions
- VC Bet H/D/A: about 145.9k rows, 19 seasons, 22 divisions
- Ladbrokes H/D/A: about 128.2k rows, 19 seasons, 22 divisions

Legacy Betbrain aggregate, totals and Asian-handicap fields are mapped explicitly where identifiable rather than discarded.

## Interpretation

This atlas is a source-coverage map, not evidence of predictive value. The coarse archive has broad historical bookmaker presence, but many fields lack exact within-day observation timestamps and therefore remain blocked by default for arbitrary pre-match cutoffs. Closing fields are separately labeled and cannot be treated as earlier-known information.

Artifact digest: `sha256:6ad0a047de89654e2ebcc3fa4a4a9bc02737897e260bcc7361a1e75456c7a43f`.

Workflow: `Market Field Coverage Atlas`.