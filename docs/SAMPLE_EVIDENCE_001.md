# Sample Evidence 001 — Public Baseline Sources

Date: 2026-07-18

This evidence was produced by GitHub Actions workflow `Public Source Sample`, not by manual inspection alone.

Workflow run: `29647568743`
Artifact: `public-source-sample`
Artifact SHA-256 digest: `acff25c6c074c56e99c29bf7116596d360b8787626deae026382ae3ee7a2b9b1`

## The Odds API official historical EPL sample

- Snapshot timestamp: `2021-10-29T23:55:00Z`
- Events: 20
- Distinct bookmaker keys observed: 13
- Market keys: `h2h`, `h2h_lay`
- Outcome quote rows counted: 810
- Bookmakers observed: betclic, betfair, betfred, betvictor, coral, ladbrokes, marathonbet, matchbook, paddypower, skybet, sport888, unibet, williamhill

Interpretation:
- A real timestamped multi-bookmaker historical payload is confirmed.
- This public sample proves the response shape and preservation pipeline, not current paid-plan coverage for Asian handicap/totals or every league/year.
- Source status may be upgraded from documentation-only candidate to **sampled (public official sample)**, not `connected`.

## Football-Data EPL 2025/26 CSV

- Rows: 380
- Match identity/result/stat fields populated across the season.
- Numerous bookmaker/open-close/average/max odds fields are present, including 1X2, totals and Asian-handicap-style fields with varying provider coverage.

Interpretation:
- Strong free coarse baseline and cross-check layer.
- Not suitable as the sole high-frequency market trajectory source.
- Status: **sampled**.

## StatsBomb Open Data competitions

- Competition/season rows observed: 80

Interpretation:
- Public event/lineup schema source is reachable and suitable for event-feature R&D on covered competitions.
- Coverage is selective, so it is not a universal match spine.
- Status: **sampled**.

## Pipeline evidence

The run preserved source payloads under append-only raw paths and generated a machine-readable `sample_report.json`. Both the normal CI suite and the public sampling workflow completed successfully on the same head commit.

## What this evidence does not prove

- authenticated The Odds API paid historical coverage beyond the official public sample
- Betfair Basic account-gated file acquisition
- Tx LAB/TXODDS deep historical granularity, pricing or export terms
- Sportmonks/TXODDS prospective feed commercial access

Those remain Phase 2 gates and must not be reported as connected until real samples are obtained.
