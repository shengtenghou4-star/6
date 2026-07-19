# Phase 53 decision record

The canonical-timing challenger is activated because the outcome-blind feature audit identified timing support mismatch and live-panel coverage mismatch before campaign outcomes were available.

The challenger is not a replacement for either existing stream. Its sole purpose is to test a prespecified alternative to strict timing-row exclusion: retain observations inside the historical global 6–48 hour range, snap only the model timing input to the assigned canonical cutoff, normalize peer coverage, and rescore with the unchanged frozen bundle.

Activation is fixed at `2026-07-19T15:00:00Z`. No row ingested before that boundary is eligible for production evidence. The final evaluator, volume gates and promotion gates were committed before activation.
