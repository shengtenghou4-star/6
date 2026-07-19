# Competition and award submission kit

This package converts the research repository into a judge-ready submission without changing the evidence claim.

## Project title

**Abnormal Bookmaker Actions Predict Subsequent Repricing**

Optional technical subtitle:

**A leakage-safe residual-learning and prospective-validation system for multi-agent football odds**

## Five-sentence problem statement

1. Most football prediction projects ask who will win; this project asks whether a bookmaker's unexpected response to the wider market predicts how that same bookmaker will later reprice.
2. A normal-action model estimates how each bookmaker should react to contemporaneous prices, and the observed-minus-expected movement becomes an abnormal-action residual.
3. A raw model fixes bookmaker and outcome identity, so residual information can rerank confidence but cannot win by changing the object being predicted.
4. The historical mechanism survives 4,000 structure-preserving placebos, a threshold-free dose-response test and broad bookmaker/outcome/horizon checks, while profit and execution remain explicitly unvalidated.
5. The system now runs an untouched prospective campaign, publishes machine-checkable claim provenance and exposes the method as an open benchmark for other multi-agent pricing domains.

## 200-word abstract

Bookmaker odds are forecasts, prices and strategic market responses. We test whether a bookmaker's deviation from its expected response to the contemporaneous multi-book market contains incremental information about its own later price. A normal-action model predicts each bookmaker's next movement from observable state. The observed-minus-expected action becomes an abnormal residual. A raw future-price model fixes bookmaker and outcome identity; residual information may only rerank that same candidate universe.

The principal historical evaluation contains 59,816 opportunities across 18,072 matches. Correct match-specific residual alignment beats all 4,000 baseline-preserving chronological shift placebos for closing-price quality (empirical upper-tail p=0.00025). Across the full opportunity universe, one standard deviation of residual uplift is associated with +0.004430 same-book closing log-CLV, with event-cluster 95% interval [+0.003316,+0.005515]. Slopes are positive across 8/8 bookmakers, 3/3 selected outcomes and 4/4 horizons.

Economic evidence is deliberately separated. Matched historical ROI improves from -0.747% to +0.565%, but uncertainty crosses zero; adverse non-fill removes standalone profitability. The repository therefore claims a replicated historical repricing-information mechanism, not a betting system. An immutable future campaign, open benchmark, synthetic contract test and automated claim audit make the work reproducible and difficult to overstate.

## 90-second spoken pitch

Most sports-betting AI projects try to predict the match. We did something stranger and, I think, more scientifically useful: we tried to predict the bookmaker.

At any moment, the wider market suggests how a bookmaker would normally move. We trained a model of that normal reaction. When the bookmaker moved differently, we measured the surprise - the abnormal-action residual - and asked whether that surprise predicted the bookmaker's own later price.

The key control is identity. The baseline model fixes the bookmaker and outcome first. The residual model can only rerank confidence for that same candidate, so it cannot fake improvement by switching to a different bet.

Historically, the correctly aligned residual beat all 4,000 structure-preserving placebo worlds. The relationship is continuous, statistically positive, and appears across every tested bookmaker, outcome and time horizon.

But we also found the uncomfortable part: better price prediction does not yet equal a reliable betting business. Profit uncertainty crosses zero, and adverse execution can erase the margin. We kept those failures visible.

The result is more than a model. It is a reproducible research system: immutable future testing, machine-checkable claims and an open benchmark that can be extended to exchanges, insurers and other price-setting agents.

## Judge-facing contribution summary

### Scientific contribution

A fixed-identity abnormal-action residual that predicts later same-agent repricing after demanding alignment falsification.

### Engineering contribution

A production-style evidence pipeline with timestamped snapshots, model provenance, checksums, immutable ledgers, scheduled prospective collection and fail-closed audits.

### Reproducibility contribution

A claim registry, automated evidence checks, schema-validated benchmark submissions, synthetic recovery test and external-review packet.

### Integrity contribution

The repository records negative economic and execution findings rather than converting a strong mechanism into an unsupported profit claim.

## Recommended evidence panel

Use exactly four visuals:

1. `paper/figures/residual_pipeline.svg` - the mechanism and fixed-identity design.
2. Alignment placebo plot - observed statistic against 4,000 shifted residual worlds.
3. Dose-response plot - closing-price quality across residual-uplift deciles.
4. Evidence ladder - mechanism supported, economic conversion uncertain, execution unvalidated, prospective transfer pending.

Do not lead with ROI. The scientifically strongest result is the falsified repricing mechanism.

## Three-minute demo sequence

**0:00-0:30:** Explain the market state, expected action and abnormal residual.

**0:30-1:00:** Show that raw identity is fixed before residual reranking.

**1:00-1:30:** Show the 4,000-placebo result and continuous dose response.

**1:30-2:00:** Show the negative economic/execution boundary.

**2:00-2:30:** Open the claim registry and run the validator.

**2:30-3:00:** Show the prospective workflow and MARB benchmark extension.

## Reproduction commands

```bash
python -m pip install -e ".[dev]"
python scripts/validate_paper_claims.py
python scripts/validate_methods_note.py
python scripts/validate_benchmark_submission.py benchmark/reference_submission.json
python scripts/validate_benchmark_catalog.py
pytest -q
```

## Submission variants

### Research competition

Emphasize identification, placebo construction, dose response and prospective freeze.

### Data-science competition

Emphasize temporal data engineering, model stack, fixed-identity comparison and uncertainty.

### Open-source award

Emphasize reproducibility, automated claims, benchmark contract, tests and external contributions.

### Responsible-AI or integrity award

Emphasize evidence-tier governance, negative-result preservation and the refusal to equate price quality with profit.

### Student innovation award

Emphasize the unusual question, end-to-end ownership and transformation from a sports project into a general market-behavior framework.

## Honest answers to difficult judge questions

**Does it make money?**  
Not established. The residual policy has a favorable historical point estimate, but uncertainty and execution gates do not validate stable profit.

**Why should closing-line value matter?**  
It is the closest lower-variance endpoint to the hypothesized repricing mechanism. It is not presented as guaranteed expected return.

**Did you tune this repeatedly on the same data?**  
The historical program contains sequential diagnostics, so the final historical evidence is labeled replicated historical rather than untouched discovery. The future campaign is the clean transfer test.

**Could one bookmaker drive the result?**  
All eight tested bookmakers have positive slopes, and every leave-one-book-out lower confidence bound remains above zero.

**Could the model win by switching outcomes?**  
No. The raw model fixes bookmaker and outcome identity before residual reranking.

**What is the biggest weakness?**  
Independent real-source replication. The current second profile is synthetic and verifies the contract, not empirical transfer.

## Final submission checklist

- [ ] Replace author placeholder and add institutional affiliation where appropriate.
- [ ] Use the latest compiled empirical paper.
- [ ] Include the methods note only when the venue values methodology.
- [ ] Add the final prospective block after campaign closure.
- [ ] Keep the negative-result paragraph unedited.
- [ ] Ensure every number in slides matches the claim registry.
- [ ] Include repository commit and artifact hashes.
- [ ] Tailor length and formatting to the specific venue.
- [ ] Avoid the words "profitable system" or "validated betting strategy".
- [ ] Ask judges to evaluate scientific identification and reproducibility, not a promotional ROI.