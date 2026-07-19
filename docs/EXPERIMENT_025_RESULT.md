# Experiment 025 Result — Closing-line value to realized-return bridge by outcome

Status: **completed; the home-only realized-return concentration is not fully reproduced in closing-line relative value**.

Run: `29691050527`.

Artifact digest: `sha256:4adf37c93117e3fa404e1448f568b4dd5510b13e75c8227e65e25b10dcf13247`.

## Construction

The diagnostic rebuilt the exact matched-budget raw and residual policies over 59,816 opportunities and 18,072 matches, then reran the four fixed practical envelopes: 1-hour delay, 90% fill and 25 bps slippage under common-random fill, adverse-move rejection, highest-edge rejection and bookmaker-clustered outage.

For each filled row, closing-line relative value was defined as:

`executed_decimal_odds / closing_decimal_odds - 1`.

Unfilled rows contributed zero. This is a price-quality diagnostic relative to the same bookmaker's closing quote, not a devigged expected-return estimate.

## Residual standalone price quality

Residual closing-line relative value was positive for home, draw and away in all four mechanisms. Every one of the 12 outcome × mechanism residual closing-value bootstrap intervals had a lower bound above zero.

Per-opportunity residual closing-value point estimates were:

- home: approximately `+0.313%` to `+0.347%`;
- draw: approximately `+0.085%` to `+0.097%`;
- away: approximately `+0.104%` to `+0.171%`.

Thus the residual policy's filled selections beat their later same-book raw closing quotes across all three selected outcomes, even where realized return was negative.

## Residual-minus-raw incremental bridge

### Home

Incremental closing-line relative value was positive in all four mechanisms, from `+3.08` to `+7.21` units. Incremental realized return was also positive in all four, from `+41.31` to `+65.84` units.

The direction agreed, although all incremental confidence intervals still crossed zero.

### Away

Incremental closing-line relative value was positive in all four mechanisms, from `+1.51` to `+4.47` units. Incremental realized return was negative in three mechanisms and positive only under bookmaker-clustered outage.

Therefore away exhibited a sign divergence in three of four mechanisms: better relative closing-price quality did not become better realized return in this historical sample.

### Draw

Incremental closing-line relative value was negative in all four mechanisms, from `-1.74` to `-2.17` units. Incremental realized return was also negative in all four, from `-5.28` to `-12.27` units.

Draw was the only selected outcome whose residual-minus-raw point estimate was consistently negative on both the price-quality and realized-return sides.

## Interpretation

Experiment 024 correctly identified that historical realized execution return was home-dependent. Experiment 025 shows that this concentration is only partly a price-quality phenomenon:

- home is positive on both closing-value and realized-return dimensions;
- away is positive on closing-value point estimates but usually negative in realized return;
- draw is negative incrementally on both dimensions.

The frozen classification records:

- home incremental closing value positive in 4/4 and realized return positive in 4/4;
- away incremental closing value positive in 4/4 but realized return positive in only 1/4;
- draw incremental closing value positive in 0/4 and realized return positive in 0/4;
- `home_concentration_fully_explained_by_closing_value = false`.

This weakens any simplistic claim that only home selections contain market information. The broader price-quality signal extends to away selections; finite outcome realization and execution variance amplify the apparent home concentration. Draw remains the clearest weak segment at the point-estimate level.

## Evidence boundary

The diagnostic was specified after outcome concentration had already been observed. It is post-hoc and cannot authorize a home-only, non-draw or any other selected-outcome policy. All incremental closing-value and realized-return confidence intervals crossed zero.

The supported conclusion is that outcome realization materially distorts the conversion from closing-line value to historical return. Future selected-outcome claims must come from separately activated prospective cohorts rather than retrospective filtering.
