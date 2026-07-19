# Experiment 022 Result — Residual dose-response heterogeneity audit

Status: **completed; the threshold-free closing-price relationship is distributed across all bookmakers, selected outcomes and cutoffs, while realized-return heterogeneity remains unsupported**.

Run: `29685865512`

Artifact digest: `sha256:4c0f43ece3d17ca9e318ef3ba796a99d4d38e35cba4eab80d728e88fcdfd5f3a`

## Frozen evidence

The audit reused the exact Experiment 021 construction across:

- 59,816 opportunities;
- 18,072 matches;
- eight fixed bookmaker slots;
- home, draw and away raw-selected identities;
- T-48, T-24, T-12 and T-6;
- no subgroup-specific refit, threshold or deletion.

## Bookmaker heterogeneity

Closing log-CLV slope was positive for all eight bookmakers:

- ComeOn: `+0.001406`;
- bet-at-home: `+0.004091`;
- bet365: `+0.005630`;
- 10Bet: `+0.000410`;
- BetVictor: `+0.003492`;
- Betclic: `+0.006649`;
- Expekt: `+0.001349`;
- Tipico: `+0.006262`.

Seven of eight bookmakers also had positive highest-dose minus lowest-dose CLV. The lone exception, 10Bet, was essentially flat at `-0.000190` rather than materially reversed.

No single bookmaker dominated positive slope evidence. Tipico was the largest contributor at `36.02%`, followed by bet365 at `28.22%`; both were below the frozen 50% concentration ceiling.

## Selected-outcome and cutoff stability

CLV slope was positive for every raw-selected outcome:

- home: `+0.003068`;
- draw: `+0.001225`;
- away: `+0.006870`.

It was also positive at every cutoff:

- T-48: `+0.005695`;
- T-24: `+0.003629`;
- T-12: `+0.004440`;
- T-6: `+0.004392`.

## Leave-one-book-out robustness

After removing each bookmaker in turn, the remaining global CLV slope stayed positive with its event-cluster 95% lower bound above zero.

The most conservative omission was Tipico:

- leave-Tipico-out slope: `+0.003803`;
- 95% interval: `[+0.002493, +0.005087]`.

Across all eight omissions, lower confidence bounds ranged from `+0.002493` to `+0.003719`. The price-quality mechanism therefore does not depend on any single bookmaker.

## Realized return

Return behavior remained heterogeneous and statistically unstable:

- bookmaker-level return slopes included both positive and negative values;
- selected draw and away identities had negative return slopes despite positive CLV slopes;
- T-24 and T-6 return slopes were negative;
- every leave-one-book-out return-slope interval crossed zero.

For example, after excluding Tipico, the return-slope point estimate was `-0.00610` with interval `[-0.02054, +0.00875]`.

## Frozen gate

- `mechanism_heterogeneity_passed`: **true**;
- `profit_heterogeneity_passed`: **false**.

## Supported interpretation

The residual dose relationship is not a Tipico effect, a bet365 effect, a favorite/underdog identity artifact or a single-cutoff phenomenon. It survives removal of every bookmaker and appears in all three selected outcomes and all four historical horizons.

This closes another major alternative explanation for the historical closing-price result. It does not close the economic gap: the same broad consistency is absent from realized returns, which remain dominated by outcome noise and execution concerns. The strongest defensible claim remains a generalizable historical repricing-information mechanism, pending untouched prospective transfer evidence.