# PHASE 1: System Architecture Map

**Document Version:** 1.0.0
**Date:** 2026-01-22
**Status:** COMPLETE

---

## Executive Summary

This document captures the complete system architecture for QUANT_INDUSTRY_V1, an institutional-grade quantitative trading platform. The architecture addresses all critical issues identified in the v2.1 audit while maintaining compatibility with the existing Tkinter UI.

---

## 1. High-Level System Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUANT_INDUSTRY_V1                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   Data Layer    │───▶│   Brain Layer   │───▶│ Execution Layer │         │
│  │                 │    │                 │    │                 │         │
│  │ • Fetchers      │    │ • Features      │    │ • Risk Engine   │         │
│  │ • Validators    │    │ • Supervised    │    │ • Order Manager │         │
│  │ • Cache         │    │ • RL Engine     │    │ • Broker API    │         │
│  │ • Quality Gates │    │ • Meta-Learner  │    │ • Kill Switch   │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                  │
│           ▼                      ▼                      ▼                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                     SQLite Database (DAL)                        │       │
│  │  • market_bars • signals • trades • models • audit_log • etc.   │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                      │                      │                  │
│           ▼                      ▼                      ▼                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   UI Layer      │    │ Services Layer  │    │ Analytics Layer │         │
│  │                 │    │                 │    │                 │         │
│  │ • Tkinter (now) │    │ • Health Check  │    │ • Performance   │         │
│  │ • Tauri (next)  │    │ • Self-Grader   │    │ • Attribution   │         │
│  │ • Dashboards    │    │ • Scheduler     │    │ • Risk Reports  │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow Paths

### 2.1 Market Data Pipeline

```
External APIs (Alpaca/Yahoo/Polygon)
         │
         ▼
┌────────────────────┐
│    Rate Limiter    │ ← 200 req/min, token bucket
│    (utils/retry)   │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Data Fetcher      │ ← Primary + Fallback sources
│  (data/fetcher)    │ ← Automatic retry with backoff
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Data Validator    │ ← OHLC validation
│  (data/validator)  │ ← Quality scoring
└────────┬───────────┘   ← Outlier detection
         │
         ├──────────────────┐
         ▼                  ▼
┌────────────────┐  ┌──────────────────┐
│  Cache (RAM)   │  │  SQLite (disk)   │
│  TTL: 5 min    │  │  market_bars     │
└────────────────┘  └──────────────────┘
```

### 2.2 Signal Generation Pipeline

```
Market Data
     │
     ▼
┌─────────────────────┐
│  Feature Computer   │ ← 40+ technical indicators
│  (brain/features)   │ ← Reproducible hashing
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Regime Detector    │ ← HMM / Clustering / Rules
│  (brain/regime)     │ ← Stability constraints
└─────────┬───────────┘
          │
          ├────────────────────────┬────────────────────────┐
          ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Supervised    │    │    RL Engine    │    │   Rule-Based    │
│   Ensemble      │    │    (PPO/A2C)    │    │   Fallback      │
│ • XGBoost       │    │ • Policy        │    │ • Momentum      │
│ • LightGBM      │    │ • Value         │    │ • Mean Rev      │
│ • RandomForest  │    │ • Rewards       │    │                 │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                ▼
                    ┌─────────────────────┐
                    │    Meta-Learner     │ ← Regime-adaptive weights
                    │    (brain/meta)     │ ← Calibration
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Signal Output     │ ← Direction, Strength
                    │                     │ ← Confidence, Explanation
                    └─────────────────────┘
```

### 2.3 Execution Pipeline

```
Signal
   │
   ▼
┌──────────────────────┐
│  Pre-Trade Risk      │ ← Position limits
│  (risk/pre_trade)    │ ← Exposure checks
└──────────┬───────────┘   ← Correlation limits
           │
           ▼
┌──────────────────────┐
│  Position Sizer      │ ← Kelly Criterion
│  (risk/sizing)       │ ← Volatility scaling
└──────────┬───────────┘   ← Max position cap
           │
           ▼
┌──────────────────────┐
│  Order Generator     │ ← Market/Limit/Stop
│  (execution/orders)  │ ← Time-in-force
└──────────┬───────────┘
           │
           ├───────────────────────┐
           ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Broker API      │    │  Paper Broker    │
│  (Alpaca Live)   │    │  (Simulation)    │
└──────────┬───────┘    └──────────┬───────┘
           │                       │
           └───────────┬───────────┘
                       ▼
           ┌──────────────────────┐
           │  Execution Logger    │ ← Audit trail
           │  (db/audit_log)      │ ← Slippage tracking
           └──────────────────────┘
```

---

## 3. API Boundaries

### 3.1 External APIs

| API | Purpose | Rate Limit | Fallback |
|-----|---------|------------|----------|
| Alpaca Markets | Primary data + Execution | 200/min | Yahoo |
| Yahoo Finance | Fallback data | Soft | None |
| Polygon.io | Alternative data | 5/min | Yahoo |

### 3.2 Internal Module Interfaces

```python
# Core Interfaces (core/interfaces.py)

class DataProvider(ABC):
    def fetch(symbol, timeframe, start, end) -> MarketData
    def get_latest(symbol, timeframe) -> MarketData
    def validate(data) -> Tuple[bool, List[str]]

class FeatureComputer(ABC):
    def compute(data, feature_names) -> FeatureVector
    def get_feature_names() -> List[str]
    def get_feature_hash(features) -> str

class SignalGenerator(ABC):
    def generate(symbol, features, regime) -> Signal
    def generate_batch(symbols, features_list, regime) -> List[Signal]

class Executor(ABC):
    def execute(signal, position_size) -> ExecutionResult
    def cancel_order(order_id) -> bool
    def get_positions() -> Dict[Symbol, float]

class RiskManager(ABC):
    def check_pre_trade(signal, proposed_size) -> RiskAssessment
    def calculate_position_size(signal, equity) -> float
    def check_kill_switch() -> Tuple[bool, Optional[str]]
```

---

## 4. Module Dependencies

```
                          ┌─────────┐
                          │  core   │
                          │ (types, │
                          │ errors) │
                          └────┬────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
    ┌─────────┐          ┌─────────┐          ┌─────────┐
    │ config  │          │  utils  │          │   db    │
    │         │          │         │          │  (DAL)  │
    └────┬────┘          └────┬────┘          └────┬────┘
         │                    │                    │
         └──────────┬─────────┴──────────┬─────────┘
                    │                    │
         ┌──────────┴─────────┐         │
         │                    │         │
         ▼                    ▼         │
    ┌─────────┐          ┌─────────┐    │
    │  data   │◀─────────│  brain  │◀───┘
    │         │          │         │
    └────┬────┘          └────┬────┘
         │                    │
         │    ┌───────────────┘
         │    │
         ▼    ▼
    ┌─────────────┐
    │  execution  │
    │             │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐     ┌─────────────┐
    │    risk     │◀───▶│  services   │
    └─────────────┘     └─────────────┘
           │
           ▼
    ┌─────────────┐
    │     ui      │
    └─────────────┘
```

---

## 5. Bottlenecks & Fragilities Identified

### 5.1 Critical Issues (From v2.1 Audit)

| Issue | Severity | Resolution |
|-------|----------|------------|
| Missing file implementations | CRITICAL | Created all core modules |
| State persistence | CRITICAL | SQLite + checkpoints |
| Data validation layer | HIGH | data/validator.py |
| RL reward tuning | HIGH | Configurable rewards |
| Kelly criterion issues | HIGH | Proper half-Kelly |

### 5.2 Technical Debt Items

| Item | Effort | Priority |
|------|--------|----------|
| Complete test coverage | 80 hrs | P0 |
| Hyperparameter optimization | 40 hrs | P1 |
| Performance profiling | 20 hrs | P1 |
| Documentation | 40 hrs | P2 |

### 5.3 Performance Bottlenecks

1. **Feature Computation**: O(symbols × features) - Mitigated by caching
2. **Database I/O**: Addressed by WAL mode + indexing
3. **Model Inference**: Batch processing supported
4. **UI Updates**: Background threading required

---

## 6. Security Concerns Addressed

| Concern | Mitigation |
|---------|------------|
| API key exposure | Environment variables + encrypted storage |
| Pickle deserialization | JSON for config, pickle only for models with validation |
| Input validation | Symbol whitelist + validation utilities |
| Audit trail | Comprehensive audit_log table |

---

## 7. Folder Structure

```
QUANT_INDUSTRY_V1/
├── core/                 # Core types, interfaces, exceptions
│   ├── __init__.py
│   ├── interfaces.py     # Abstract base classes
│   ├── types.py          # Common data types
│   ├── exceptions.py     # Exception hierarchy
│   └── context.py        # Run context management
├── config/               # Configuration management
│   ├── __init__.py
│   └── settings.py       # Settings with validation
├── db/                   # Database access layer
│   ├── __init__.py
│   ├── schema.sql        # SQLite schema
│   ├── dal.py            # Database manager
│   ├── models.py         # ORM-like models
│   └── repositories.py   # Data access patterns
├── data/                 # Market data handling
│   ├── __init__.py
│   ├── fetcher.py        # Data fetching
│   ├── validator.py      # Data validation
│   └── cache.py          # Caching layer
├── brain/                # ML/AI components
│   ├── __init__.py
│   ├── features.py       # Feature computation
│   ├── supervised/       # Supervised models
│   ├── rl/               # Reinforcement learning
│   ├── meta/             # Meta-learning
│   └── regime.py         # Regime detection
├── execution/            # Trade execution
│   ├── __init__.py
│   ├── broker.py         # Broker interface
│   ├── paper.py          # Paper trading
│   └── orders.py         # Order management
├── risk/                 # Risk management
│   ├── __init__.py
│   ├── engine.py         # Risk engine
│   ├── limits.py         # Limit checking
│   └── sizing.py         # Position sizing
├── ui/                   # User interface
│   ├── __init__.py
│   ├── tkinter/          # Current Tkinter UI
│   ├── components/       # Reusable components
│   └── views/            # Screen views
├── services/             # Background services
│   ├── __init__.py
│   ├── health.py         # Health monitoring
│   ├── grader.py         # Self-grading
│   └── scheduler.py      # Task scheduling
├── strategies/           # Strategy plugins
├── analytics/            # Performance analytics
├── tests/                # Test suites
│   ├── unit/
│   ├── integration/
│   └── golden/
├── docs/                 # Documentation
├── scripts/              # Utility scripts
├── migrations/           # Database migrations
├── logs/                 # Log files
├── models/               # Saved model files
├── checkpoints/          # Training checkpoints
└── requirements.txt      # Python dependencies
```

---

## 8. Rollback Plan

### Database
- WAL mode ensures atomic operations
- Point-in-time recovery via journal
- Migration scripts reversible

### Models
- Version-controlled in models table
- Shadow mode for testing
- One-click rollback to previous version

### Configuration
- Config hashing for tracking
- Git versioning recommended
- Settings saved per run

---

## 9. Tests Required

### Unit Tests (P0)
- [ ] Data validation functions
- [ ] Feature computation
- [ ] Position sizing calculations
- [ ] Risk limit checks

### Integration Tests (P1)
- [ ] Data pipeline end-to-end
- [ ] Signal generation pipeline
- [ ] Order execution flow

### Golden Tests (P2)
- [ ] Known signal outputs
- [ ] Expected feature values
- [ ] Risk assessment scenarios

---

## 10. Failure Modes

| Component | Failure Mode | Recovery |
|-----------|--------------|----------|
| Data Fetcher | API timeout | Fallback to secondary source |
| Data Fetcher | Rate limit | Exponential backoff |
| Model | Inference error | Use rule-based fallback |
| Execution | Order rejected | Log, notify, do not retry |
| Database | Connection lost | Retry with backoff |
| Kill Switch | Triggered | Stop all trading, notify |

---

## Approval

- [ ] Architecture approved
- [ ] Schema approved
- [ ] Interface contracts approved
- [ ] Security review passed

---

*Document generated by QUANT_INDUSTRY_V1 Phase 1 Audit*
