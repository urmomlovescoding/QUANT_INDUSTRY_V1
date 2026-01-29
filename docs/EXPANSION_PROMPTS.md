# QUANT INDUSTRY V1 - Expansion Prompts

Use these with ChatGPT/GPT-4 to brainstorm new features and improvements.

---

## 🧠 ALPHA GENERATION

### Prompt 1: Alternative Data Alpha
```
I'm building an institutional-grade quant trading platform. I already have:
- Cross-asset momentum
- Lead-lag detection  
- News sentiment (FinBERT)

What alternative data sources could generate unique alpha? Consider:
- Satellite imagery (parking lots, shipping)
- Web scraping (job postings, app downloads)
- Social media beyond news
- Credit card transaction proxies
- Government filings (13F, insider trades)

For each source: explain the signal, expected alpha (bps), decay rate, and implementation complexity.
```

### Prompt 2: Crypto-Specific Alpha
```
My quant platform handles traditional equities but I want to add crypto alpha strategies. What are the unique alpha opportunities in crypto that don't exist in traditional markets?

Consider:
- On-chain analytics (whale movements, DEX flows)
- Funding rate arbitrage
- MEV-aware execution
- Cross-exchange basis trades
- Stablecoin depegging signals
- DeFi yield strategy rotation

For each: expected returns, capacity, risks, and Python implementation outline.
```

### Prompt 3: Options-Driven Alpha
```
I have a full equity platform but limited options support. What options-based alpha strategies should I implement?

Current capabilities: execution algorithms, risk management, factor models

Ideas to explore:
- Volatility surface arbitrage
- Earnings straddles with IV crush modeling
- Gamma scalping automation
- Skew trading
- Options flow sentiment (unusual activity detection)
- Dispersion trading

Provide: strategy logic, data requirements, Greeks management, and risk controls.
```

---

## ⚡ HIGH-FREQUENCY / MARKET MICROSTRUCTURE

### Prompt 4: Order Book Enhancements
```
I have basic order book analysis (VPIN, imbalance, microprice). What advanced market microstructure features would give edge?

Consider:
- Queue position estimation
- Hidden liquidity detection
- Toxic flow classification
- Optimal posting algorithms
- Adverse selection measurement
- Market maker inventory models

For each: explain the math, expected edge, latency requirements, and implementation sketch.
```

### Prompt 5: Smart Order Routing
```
Design a smart order router for a multi-asset quant platform. Current execution algos: VWAP, TWAP, Implementation Shortfall.

The SOR should:
- Route across multiple venues/exchanges
- Factor in rebates vs fees (maker-taker)
- Estimate fill probability per venue
- Minimize information leakage
- Handle partial fills intelligently
- Learn from historical execution quality

Provide: architecture, routing logic, ML components, and monitoring metrics.
```

---

## 🤖 MACHINE LEARNING

### Prompt 6: Reinforcement Learning Trading
```
I have ML infrastructure (feature store, model registry, Temporal Fusion Transformer, regime ensemble). What RL approaches should I add for trading?

Current gaps:
- No pure RL execution
- No multi-agent simulation
- No meta-learning across strategies

Design:
1. RL execution agent (state space, action space, reward function)
2. Market simulator for training (realistic order book dynamics)
3. Transfer learning across different assets
4. Safe exploration strategies (position limits during learning)

Focus on practical implementation, not toy examples.
```

### Prompt 7: Federated Learning for Quant
```
I want to enable collaborative ML across multiple trading desks without sharing proprietary data. Design a federated learning system for quant signals.

Constraints:
- No raw data leaves each desk
- Model aggregation preserves privacy
- Handle non-IID data (different assets, timeframes)
- Prevent adversarial participants
- Measure contribution fairness

Output: architecture, privacy guarantees, aggregation methods, and incentive design.
```

### Prompt 8: Causal ML for Alpha
```
Most ML models find correlations, not causation. Design a causal inference pipeline for alpha discovery.

Should include:
- Causal graph discovery from data
- Intervention analysis (what-if scenarios)
- Confounder identification
- Treatment effect estimation for trades
- Counterfactual P&L attribution

Libraries to consider: DoWhy, CausalML, EconML. Provide end-to-end workflow.
```

---

## 🛡️ RISK MANAGEMENT

### Prompt 9: Real-Time Stress Testing
```
I have Monte Carlo simulation and tail risk detection. Design a real-time stress testing engine that:

- Runs continuously (not just EOD)
- Uses live market data to update scenarios
- Detects emerging risk regimes before they fully materialize
- Provides actionable hedge recommendations
- Integrates with circuit breakers for automatic de-risking

Include: architecture, scenario generation, latency requirements, and alert design.
```

### Prompt 10: Liquidity Risk Engine
```
Design a comprehensive liquidity risk management system. Current gap: I model slippage but don't manage liquidity risk holistically.

Should cover:
- Position-level liquidation time estimation
- Portfolio-level fire sale analysis
- Crowding detection (who else holds similar positions?)
- Funding liquidity vs market liquidity
- Stress liquidity (what happens in a vol spike?)
- Optimal liquidation sequencing

Output: data sources, models, monitoring dashboard, and integration points.
```

---

## 🏗️ INFRASTRUCTURE

### Prompt 11: Multi-Region Deployment
```
My quant platform runs in a single region. Design multi-region architecture for:

- Sub-millisecond data distribution
- Active-active trading (different strategies per region)
- Disaster recovery with <1 minute failover
- Data sovereignty compliance (EU data stays in EU)
- Cost optimization (spot instances for backtest, dedicated for live)

Current stack: FastAPI, Postgres, Redis, TimescaleDB, Docker/K8s

Provide: architecture diagram, data flow, latency analysis, and cost estimates.
```

### Prompt 12: GPU Cluster for ML Training
```
Design a GPU cluster architecture for continuous ML model training and inference.

Requirements:
- Train multiple models in parallel (hyperparameter search)
- Real-time inference (<10ms for 1000 predictions)
- Model versioning and A/B testing
- Cost-efficient (use cloud spot/preemptible)
- Handle GPU failures gracefully

Current setup: Single RTX 4050, want to scale to cloud

Include: hardware recommendations, orchestration (Ray? Kubeflow?), and cost model.
```

---

## 💰 MONETIZATION / BUSINESS

### Prompt 13: SaaS Pricing Model
```
I'm turning my quant platform into a SaaS product. Current features:
- Backtesting as a service
- Signal marketplace
- Paper trading
- Full trading infrastructure

Design a pricing model that:
- Has free tier for user acquisition
- Scales with usage (AUM, trades, compute)
- Captures value from successful strategies
- Prevents gaming/abuse
- Competes with QuantConnect, Alpaca, etc.

Include: tier structure, pricing math, and competitive positioning.
```

### Prompt 14: Prop Firm Module
```
Design a prop firm management module for my platform. Should enable:

- Trader onboarding with evaluation challenges
- Risk limit assignment per trader
- Real-time P&L and drawdown monitoring
- Profit split calculations
- Account scaling rules
- Trader performance attribution
- Compliance/audit trail

Reference: FTMO, MFF, TopStep models. How do I build this better?
```

---

## 🔮 CUTTING EDGE

### Prompt 15: LLM-Powered Trading Assistant
```
Design an LLM-powered trading assistant that integrates with my quant platform.

Capabilities:
- Natural language strategy queries ("show me momentum strategies that work in high vol")
- Voice-activated trade execution with confirmation
- Explain model decisions in plain English
- Generate strategy ideas from market commentary
- Summarize overnight developments

Safety requirements:
- Human confirmation for all trades
- Hallucination detection
- Audit log of all LLM interactions

Architecture: local LLM vs API? RAG over docs? Tool use?
```

### Prompt 16: Quantum Computing Readiness
```
Quantum computing will eventually impact quant finance. How should I prepare my platform?

Areas to explore:
- Portfolio optimization (QAOA)
- Monte Carlo speedup
- Cryptography migration (post-quantum)
- Quantum ML for pattern recognition
- Timeline expectations (what's real vs hype?)

I'm not implementing now, but want architecture that's quantum-ready.
```

### Prompt 17: Decentralized Trading Infrastructure
```
How could blockchain/DeFi technology improve my centralized quant platform?

Consider:
- On-chain settlement for instant P&L
- Decentralized signal marketplace (smart contracts)
- Zero-knowledge proofs for strategy verification
- DAO governance for platform decisions
- Tokenized strategy shares

Be practical: what's valuable vs what's just crypto hype?
```

---

## 📊 ANALYTICS & VISUALIZATION

### Prompt 18: Interactive Strategy Lab
```
Design an interactive "strategy lab" UI for my quant platform.

Features:
- Drag-and-drop strategy builder (visual programming)
- Real-time backtest as you edit
- Side-by-side strategy comparison
- What-if parameter sensitivity
- Shareable strategy templates

Tech: React + TypeScript frontend already exists. What components/libraries?
```

### Prompt 19: Executive Dashboard
```
Design an executive-level dashboard for portfolio oversight.

Audience: CIO, risk committee, investors (not quants)

Should show:
- Portfolio health at a glance
- Key risk metrics simplified
- Performance attribution (what's working?)
- Alerts requiring attention
- Comparison to benchmarks

Principles: less is more, actionable insights, no jargon
```

---

## 🔒 SECURITY & COMPLIANCE

### Prompt 20: SEC/FINRA Compliance Module
```
Design a compliance module for a quant trading platform targeting US markets.

Requirements:
- Pre-trade compliance checks (restricted lists, concentration limits)
- Post-trade reporting (OATS, CAT, 13F, 13H)
- Best execution documentation
- Audit trail for all decisions
- Surveillance for manipulative patterns

I need to understand: what's legally required vs best practice?
```

---

## 🎯 QUICK WINS

### Prompt 21: Platform Hardening
```
Review my quant platform architecture and identify quick wins for reliability:

Current stack:
- Python backend (FastAPI)
- React frontend
- Postgres + TimescaleDB + Redis
- Docker + K8s deployment
- GitHub Actions CI/CD

What are the top 10 reliability improvements I should make? Focus on:
- Data integrity
- Failover handling
- Monitoring blind spots
- Common quant platform failure modes
```

### Prompt 22: Performance Optimization
```
My quant platform processes 100K+ events/second during backtests. Where should I focus optimization?

Current bottlenecks I suspect:
- Pandas operations
- Database writes
- Feature calculations
- Model inference

What profiling approach and which optimizations (Cython, Numba, async, better data structures) would give biggest gains?
```

---

*Generated for QUANT_INDUSTRY_V1 - use these to push the platform to the next level* 🚀
