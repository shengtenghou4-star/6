# Sample Evidence 008 — Wyscout-Derived Figshare Open Lake

Validated through the public Figshare API and GitHub Actions.

## Verified acquisition

- 8 selected public articles acquired successfully
- 80,003,597 source bytes preserved in workflow artifact
- 0 download failures
- 0 critical parse failures in events, matches, players or teams
- 1 explicit noncritical upstream defect: `referees.json` is malformed JSON and is preserved/reported rather than silently repaired

## Verified records

### Events

- England: 643,150
- European Championship: 78,140
- France: 632,807
- Germany: 519,407
- Italy: 647,372
- Spain: 628,659
- World Cup: 101,759
- **Total event records: 3,251,294**

### Matches

- England: 380
- European Championship: 51
- France: 380
- Germany: 306
- Italy: 380
- Spain: 380
- World Cup: 64
- **Total matches: 1,941**

### Entities

- Players: 3,603
- Teams: 142
- Coaches: 208
- Competitions: 7
- Tag mapping: 60 CSV rows including header

## Research use

This source adds an independent event/player/team layer, especially useful for football-process and player/lineup feature engineering. It is selective historical coverage and does not become the universal match spine. Event data are realized during matches and are not treated as pre-match-known features without an explicitly time-safe lagged construction.

## Provenance

Collection: Figshare `Soccer match event dataset`, collection ID `4415000`.

Selected articles expose CC BY 4.0 licences through Figshare metadata. Preserve source citations/licence metadata in downstream publications.

Workflow artifact digest: `sha256:2d9b0b93a0fda96f9ea90c825d7e5ae8c37993f51e570559eb4de8c75e71efc8`.