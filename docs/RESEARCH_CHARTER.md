# Research Charter

## Purpose

Build a research system that can discover, test, reject, and refine hypotheses about football betting markets using large-scale historical data.

The current leading hypothesis is to model bookmaker behavior conditionally, identify abnormal deviations from expected behavior, and test whether those deviations carry incremental information. This hypothesis is provisional and may be replaced.

## Hard guardrails

These rules are intentionally narrow and hard to change because breaking them can create false discoveries.

1. **Time integrity**
   - Every feature used for a prediction or decision must have been knowable at that exact decision time.
   - Preserve `event_time`, `known_at`, source timestamp, ingestion timestamp, and timezone where available.
   - Never backfill revised information into an earlier prediction state without explicitly marking it as unavailable then.

2. **No fabricated evidence**
   - Never report a data source as connected, a model as trained, an experiment as run, or a result as validated unless it actually happened and an artifact/log exists.

3. **Reproducibility**
   - Important findings must be reproducible from a documented data snapshot/version, code commit, configuration, and random seed where relevant.

4. **Out-of-sample discipline**
   - Exploratory, validation, and final holdout periods must be distinguished.
   - Repeated tuning on the same holdout turns it into training data; create a new untouched holdout when necessary.

5. **Raw-data preservation**
   - Preserve source-native raw data whenever legally and practically possible.
   - Transformations should be additive and traceable rather than destructive.

6. **Negative results stay visible**
   - Failed hypotheses, unstable signals, and null results must be recorded so agents do not endlessly rediscover and retest the same dead ends.

7. **Claim strength must match evidence**
   - Correlation is not intent.
   - Price movement is not automatically information.
   - Backtest profit is not automatically a robust edge.
   - A high model score is not automatically monetizable.

## Explicitly flexible areas

The following are **not constitutional commitments** and may be changed whenever evidence supports a better choice:

- Primary research target or dependent variable
- Whether bookmaker abnormal behavior remains the main direction
- Data vendors and collection methods
- Number and identity of bookmakers, leagues, markets, or seasons
- Database technology and storage format
- Feature definitions
- Machine-learning algorithms
- Agent architecture and role names
- Whether LLM agents are used at all in a specific stage
- Evaluation metrics and backtesting design, provided changes are documented and do not violate time integrity
- Repository structure

## Research decision rule

A research direction should earn continued investment by producing one or more of:

- reproducible incremental predictive information,
- robust explanatory value that unlocks better experiments,
- measurable data-quality or engineering improvement,
- a credible path to monetizable advantage.

If evidence repeatedly fails, pivot quickly. The project serves the evidence; the evidence does not serve the original plan.

## Change protocol

Major assumptions should be written as versioned hypotheses, not eternal rules.

For any meaningful pivot, record:

- what changed,
- why it changed,
- evidence motivating the change,
- which prior experiments remain valid,
- which must be rerun.

This charter protects scientific integrity while keeping the research direction deliberately revisable.
