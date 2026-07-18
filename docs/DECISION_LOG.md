# Decision Log

Use this file to record major research or architecture decisions that materially change what the project is testing or how evidence is interpreted.

The purpose is not bureaucracy. It is to prevent agents from silently rewriting history or treating an old plan as permanent truth.

## Template

### YYYY-MM-DD — Decision title

**Status:** proposed / adopted / superseded / rejected

**What changed**

Describe the decision or pivot.

**Why**

State the evidence, failure mode, new opportunity, or engineering constraint that motivated it.

**What remains valid**

List prior data, experiments, or conclusions that still hold.

**What must be revisited**

List experiments, assumptions, schemas, or conclusions that should be rerun or reinterpreted.

**How we will test the new direction**

Define the shortest falsifiable test.

---

## 2026-07-18 — Start a separate research-first project

**Status:** adopted

**What changed**

Create a new repository separate from the existing Major Forest project. The new project starts from raw data and falsifiable experiments rather than primarily from textbook/SOP training of LLM agents.

**Why**

The previous master-apprentice training loop produced uncertain score meaning and diminishing progress among weaker models. A new research system should anchor progress in external data, reproducible experiments, and measurable incremental information.

**What remains valid**

Prior Major Forest domain knowledge, bookmaker heuristics, audit lessons, and candidate patterns remain useful as hypotheses and feature ideas.

**What must be revisited**

Any prior model score or claimed capability must be revalidated under the new data and evaluation framework before being treated as evidence of real predictive or economic value.

**How we will test the new direction**

Build a broad timestamp-correct data foundation, then run small experiments that compare baseline market information with additional bookmaker-behavior and context features under strict out-of-sample evaluation.

---

## 2026-07-18 — Treat bookmaker abnormal behavior as a hypothesis, not doctrine

**Status:** adopted

**What changed**

The initial leading research direction is to learn conditional normal bookmaker behavior, quantify deviations, and test whether deviations contain incremental information. This direction is explicitly replaceable.

**Why**

Directly inferring bookmaker intent is not observable and risks storytelling. Abnormal behavior can be measured, but its value must be demonstrated empirically. A different target may prove simpler or more profitable.

**What remains valid**

Collecting detailed market time series and contextual data remains valuable under many alternative research directions.

**What must be revisited**

Dependent variables, target definitions, and feature priorities should be reconsidered whenever experiments show weak signal or a superior research opportunity appears.

**How we will test the new direction**

Compare models with and without abnormal-behavior residual features using strict time-based holdouts and incremental evaluation.
