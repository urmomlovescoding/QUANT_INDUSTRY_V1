# Decision Intelligence Platform Enhancement — Structured, Explainable, Self-Improving

## Overview

You are tasked with enhancing an existing trading application by implementing missing advanced intelligence layers. Your work must be incremental, non-destructive, and grounded in proven research and libraries. The goal is to transform the application into a self-aware, explainable, and self-improving decision intelligence platform.

## Absolute Rules

1. **Do Not:**
   - Rewrite the application
   - Remove existing, functional logic
   - Invent new APIs or datasets
   - Assume features exist without verification
   - Add speculative ML without safety measures
   - Merge intelligence layers prematurely

2. **Do:**
   - Extend existing abstractions
   - Add new modules only when necessary
   - Prioritize observability over intelligence
   - Prioritize safety over computational power
   - Base implementations on established research and libraries

## Core Objective

Transition the system from a "trading app with AI assistance" to a comprehensive decision intelligence platform capable of understanding, learning, and evolving strategies.

## Approved Research & Libraries

1. **Python (Primary Orchestration)**
   - Core: `numpy`, `pandas`, `scipy`, `polars`
   - Stats & Regimes: `statsmodels`, `ruptures`, `arch`, `hmmlearn`
   - ML & Clustering: `scikit-learn`
   - Explainability: `networkx`, `shap` (optional)
   - Structure & Safety: `pydantic`, `duckdb`, `sqlite3`

2. **Rust (Safety-Critical & Deterministic)**
   - Libraries: `ndarray`, `polars`, `serde`, `rayon`, `petgraph`
   - Interop: `pyo3`, `maturin`

3. **Julia (Research & Probabilistic Intelligence)**
   - Libraries: `Distributions.jl`, `StatsBase.jl`, `Turing.jl`, `HiddenMarkovModels.jl`, `Clustering.jl`, `Flux.jl` (only if justified)

## Architecture Overview

```
┌──────────────────────────────┐
│      Human Oversight         │
│ (Explainability + Control)   │
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│      AI Control Plane        │
│ (Risk Governor / Kill Switch)│
│ Drift Detection / Throttles) │
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│  Recursive Decision Engine   │
│  Regime → Structure → Policy │
│  Exit-Value Learning (RMDP)  │
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│ Strategy Layer (Composable)  │
│  ORB / VWAP / Vol / Kill     │
│  Shadow & Evolution Support  │
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│ Market Memory & Analytics    │
│  Counterfactuals / Analogs   │
│  Long-Term Immutable Memory  │
└──────────────▲───────────────┘
               │
┌──────────────┴───────────────┐
│   Data + Execution Layer     │
│  Brokers / Feeds / Logging   │
└──────────────────────────────┘
```

## Implementation Steps

### Step 1: Full System Audit

- **Objective:** Identify missing or incomplete intelligence layers.
- **Action:** Produce the following audit table:

| Capability              | Exists | Partial | Missing | Notes           |
|-------------------------|--------|---------|---------|-----------------|
| Decision trace logging  |        |         |         |                 |
| Exit-aware learning     |        |         |         |                 |
| Strategy weighting      |        |         |         |                 |
| Counterfactual analysis |        |         |         |                 |
| Regime discovery        |        |         |         |                 |
| Strategy lifecycle      |        |         |         |                 |
| AI risk governor        |        |         |         |                 |
| Explainability          |        |         |         |                 |
| Long-term memory        |        |         |         |                 |
| Drift detection         |        |         |         |                 |

- **Ranking Criteria:** 
  1. Safety impact
  2. Learning impact
  3. Architectural risk

- **Output:** Complete the table and rank missing items. **Stop** and await further instructions.

### Step 2: Implementation of Missing Layers

For each identified missing layer:

1. **Explanation:**
   - Describe what is missing.
   - Explain its significance.

2. **Implementation:**
   - Provide minimal code or schema (e.g., `layer_decision_trace.py`).
   - Detail integration points within the existing system.

3. **Risk Management:**
   - List potential risks and proposed mitigations.
   - Implement in shadow mode to avoid live impact.

- **Output:** Implement each layer incrementally. **Stop** after each and await review.

### Step 3: Self-Grading & Critique

- **Objective:** Assess the quality and safety of each implementation.
- **Checklist:**
  - Safety preserved?
  - Existing behavior unchanged?
  - New logic observable & logged?
  - No black-box decisions?
  - Clear termination paths?
  - Reversible if incorrect?

- **Output:**
  ```
  SELF-GRADE REPORT
  - Safety: X/5
  - Correctness: X/5
  - Clarity: X/5
  - Architectural Fit: X/5

  What I'm confident about:
  - ...

  What could be wrong:
  - ...

  What I would improve next if allowed:
  - ...
  ```

- If any category scores < 4/5, propose a safer alternative. **Do not proceed** automatically.

## Forbidden Behavior

- No black-box AI
- No hallucinated math
- No silent failures
- No performance tuning before correctness
- No live-trading changes without kill switches

## Final Standard

Upon completion, the system should:
- Understand and explain its actions
- Learn from actions and non-actions
- Evolve strategies safely
- Govern itself under risk
- Scale beyond trading applications

This is not a bot; it is decision intelligence infrastructure.