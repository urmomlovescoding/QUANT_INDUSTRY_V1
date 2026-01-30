# Route Consolidation Recommendations

## Current State Analysis

### Issues Identified

1. **Duplicate Endpoints** - Same functionality exposed at different paths
2. **Inconsistent Prefixes** - Mix of `/api/`, `/api/v1/`, no prefix
3. **Two Backend Entry Points** - `api/main.py` vs `backend/main.py` (8000 vs duplicate)
4. **Scattered Route Files** - 11 route files + monolithic backend/main.py
5. **No API Versioning Strategy** - Some `/v1/`, most unversioned

---

## Consolidation Strategy

### Target Architecture
```
/api/v2/                          # New versioned API
├── /health                       # System health
├── /system/                      # System management
├── /market/                      # Market data
├── /trading/                     # Orders, positions, signals
├── /portfolio/                   # Portfolio management
├── /risk/                        # Risk management
├── /brain/                       # ML/AI brain
├── /research/                    # Research & data
├── /options/                     # Options & GEX
├── /backtest/                    # Backtesting
├── /accounting/                  # Tax & reconciliation
└── /admin/                       # Admin functions

/ws/v2/                           # WebSocket channels
├── /unified                      # Multiplexed channel
├── /market                       # Market data stream
├── /signals                      # Signal stream
└── /risk                         # Risk alerts
```

---

## Domain-Specific Recommendations

### 1. Market Data (15 endpoints → 8)

**Current:**
```
GET /api/market/status
GET /api/market/tickers
GET /api/market/quote/{symbol}
GET /api/market/bars/{symbol}
GET /api/market/snapshot/{symbol}
GET /api/market/sectors
GET /api/market/movers
GET /api/charts/ohlcv/{symbol}           # Duplicate of bars
GET /api/charts/indicators/{symbol}
GET /api/live/quote/{symbol}             # Duplicate
GET /api/live/historical/{symbol}        # Duplicate
POST /api/quotes                         # Batch quotes
```

**Consolidated:**
```
GET  /api/v2/market/status               # Market hours
GET  /api/v2/market/quotes               # Batch quotes (query: symbols=)
GET  /api/v2/market/quotes/{symbol}      # Single quote
GET  /api/v2/market/bars/{symbol}        # OHLCV data
GET  /api/v2/market/indicators/{symbol}  # Technical indicators
GET  /api/v2/market/sectors              # Sector performance
GET  /api/v2/market/movers               # Top movers
GET  /api/v2/market/snapshot/{symbol}    # Full snapshot (quote + indicators)
```

### 2. Trading/Signals (42 endpoints → 15)

**Current (fragmented across files):**
```
# Signals
GET /api/signals
GET /api/signals/active
POST /api/signals/{id}/execute
POST /api/signals/{id}/dismiss
GET /api/brain-v6/signals
POST /api/brain-v6/generate-signal

# Orders
GET /api/orders
POST /api/orders
DELETE /api/orders/{id}

# Positions
GET /api/positions
GET /api/portfolio/positions
GET /api/portfolio/position/{symbol}
DELETE /api/portfolio/position/{symbol}
POST /api/portfolio/trade

# Broker
GET /api/broker/status
GET /api/broker/account
GET /api/broker/positions
POST /api/broker/order
```

**Consolidated:**
```
# Signals
GET  /api/v2/trading/signals             # List signals (query: status=active)
POST /api/v2/trading/signals/generate    # Generate new signal
POST /api/v2/trading/signals/{id}/execute
POST /api/v2/trading/signals/{id}/dismiss

# Orders
GET  /api/v2/trading/orders              # List orders
POST /api/v2/trading/orders              # Submit order
DELETE /api/v2/trading/orders/{id}       # Cancel order

# Positions
GET  /api/v2/trading/positions           # List positions
GET  /api/v2/trading/positions/{symbol}  # Get position
DELETE /api/v2/trading/positions/{symbol} # Close position

# Broker
GET  /api/v2/trading/broker/status       # Broker connection status
GET  /api/v2/trading/broker/account      # Account info
```

### 3. Brain/ML (103 endpoints → 25)

**Current (extremely fragmented):**
```
# Brain routes (13)
/brain/status, /brain/initialize, /brain/signal/*, /brain/bots/*, /brain/pipeline/*

# Brain V6 (22)  
/api/brain-v6/status, /api/brain-v6/signal/*, /api/brain-v6/train, /api/brain-v6/config, etc.

# BEAST (3)
/api/beast/status, /api/beast/train/*, /api/beast/predict/*

# RL (3)
/api/rl/status, /api/rl/train/*, /api/rl/action/*

# DL (3)
/api/dl/status, /api/dl/train/*, /api/dl/predict/*

# Evolution (3)
/api/evolution/status, /api/evolution/evolve/*, /api/evolution/best

# Neural (4)
/api/neural/analysis/*, /api/neural/predictions/*, /api/neural/regime

# ML (3)
/api/ml/predict/*, /api/ml/regime

# Regime (4)
/api/regime/status, /api/regime/detect/*, /api/regime/history/*

# Feedback (6)
/api/feedback/status, /api/feedback/metrics, /api/feedback/record, etc.

# Agents (3)
/api/agents/status, /api/agents/consensus, /api/agents/portfolio

# Memory (3)
/api/memory/status, /api/memory/store, /api/memory/search
```

**Consolidated:**
```
# Brain Core
GET  /api/v2/brain/status                # Overall brain status
POST /api/v2/brain/initialize            # Initialize brain
GET  /api/v2/brain/config                # Get config
PUT  /api/v2/brain/config                # Update config

# Signals & Predictions
GET  /api/v2/brain/signals               # Get active signals
POST /api/v2/brain/signals/generate      # Generate signal
GET  /api/v2/brain/predict/{symbol}      # Get prediction
GET  /api/v2/brain/analyze/{symbol}      # Full analysis

# Training
POST /api/v2/brain/train                 # Train models
GET  /api/v2/brain/training/history      # Training history
POST /api/v2/brain/auto-train/start      # Start auto-training
POST /api/v2/brain/auto-train/stop       # Stop auto-training

# Regime Detection
GET  /api/v2/brain/regime                # Current regime
GET  /api/v2/brain/regime/history        # Regime history

# Feedback Loop
GET  /api/v2/brain/feedback/status       # Feedback status
POST /api/v2/brain/feedback/record       # Record trade feedback
GET  /api/v2/brain/feedback/metrics      # Feedback metrics

# Multi-Agent
GET  /api/v2/brain/agents/status         # Agent status
POST /api/v2/brain/agents/consensus      # Get consensus

# Models (unified)
GET  /api/v2/brain/models                # List all models (BEAST, RL, DL, Evolution)
GET  /api/v2/brain/models/{type}/status  # Model status by type
POST /api/v2/brain/models/{type}/train   # Train specific model
GET  /api/v2/brain/models/{type}/predict # Get prediction from model
```

### 4. Risk Management (18 endpoints → 10)

**Current:**
```
GET /api/risk/metrics
GET /api/risk/safety
GET /api/risk/limits
GET /api/risk/exposure
GET /api/risk/sector-exposure
GET /api/risk/correlation
GET /api/risk/correlation/{symbol}
GET /api/risk/report
GET /api/risk/var
GET /api/risk/summary
GET /api/risk/alerts
POST /api/risk/check-trade
POST /api/risk/alerts/{key}/acknowledge
POST /api/risk/montecarlo/simulate
GET /api/correlation/matrix
GET /api/kill-switch
POST /api/kill-switch/activate
POST /api/kill-switch/deactivate
```

**Consolidated:**
```
# Risk Metrics
GET  /api/v2/risk/summary                # Combined metrics + safety + limits
GET  /api/v2/risk/exposure               # Position exposure
GET  /api/v2/risk/correlation            # Correlation matrix (query: symbol=)
GET  /api/v2/risk/var                    # Value at Risk report

# Risk Alerts
GET  /api/v2/risk/alerts                 # Active alerts
POST /api/v2/risk/alerts/{id}/ack        # Acknowledge alert

# Risk Checks
POST /api/v2/risk/check                  # Pre-trade risk check
POST /api/v2/risk/montecarlo             # Monte Carlo simulation

# Kill Switch
GET  /api/v2/risk/kill-switch            # Status
POST /api/v2/risk/kill-switch/activate   # Engage
POST /api/v2/risk/kill-switch/release    # Release
```

### 5. System/Settings (44 endpoints → 15)

**Current (scattered):**
```
GET /api/health
GET /api/system/status
GET /api/system/health
GET /api/system/memory
GET /api/system/resources
GET /api/system/ml-capabilities
POST /api/system/clear-cache
GET /api/data-mode
POST /api/data-mode
GET /api/data-integrity/status
GET /api/data-integrity/price/{symbol}
GET /api/data/staleness
GET /api/data/staleness/{symbol}
GET /api/settings
POST /api/settings
PUT /api/settings
GET /api/settings/presets
POST /api/settings/preset/{name}
GET /api/settings/api-keys
POST /api/settings/api-keys
POST /api/settings/api-keys/{provider}
GET /api/settings/api-keys/{provider}/test
GET /api/settings/test-connection/{provider}
GET /api/connections
POST /api/connections
POST /api/connections/{id}/test
DELETE /api/connections/{id}
GET /api/modules/status
GET /api/slide-doctrine
GET /api/slide-doctrine/models
GET /api/slide-doctrine/audit
GET /api/learning/*
```

**Consolidated:**
```
# Health
GET  /api/v2/health                      # Simple health check
GET  /api/v2/health/detailed             # Full system status

# System
GET  /api/v2/system/status               # System resources (CPU, mem, GPU)
GET  /api/v2/system/modules              # Module availability
POST /api/v2/system/cache/clear          # Clear caches

# Data Integrity
GET  /api/v2/system/data-mode            # Current data mode
PUT  /api/v2/system/data-mode            # Set data mode
GET  /api/v2/system/data-quality         # Data freshness/staleness

# Settings
GET  /api/v2/settings                    # All settings
PUT  /api/v2/settings                    # Update settings
GET  /api/v2/settings/presets            # Available presets
POST /api/v2/settings/presets/{name}     # Apply preset

# API Keys
GET  /api/v2/settings/api-keys           # API key status
PUT  /api/v2/settings/api-keys/{provider} # Update API key
POST /api/v2/settings/api-keys/{provider}/test # Test connection
```

### 6. Options & GEX (9 endpoints → 6)

**Current:**
```
GET /api/options/chain/{symbol}
GET /api/options/gex/{symbol}
GET /api/options/flow
GET /api/gex/{symbol}                    # Duplicate
GET /api/v1/options-flow/unusual
GET /api/v1/options-flow/gamma-exposure/{symbol}
GET /api/v1/options-flow/dark-pool
GET /api/v1/options-flow/signals
GET /api/v1/options-flow/smart-money
```

**Consolidated:**
```
GET  /api/v2/options/chain/{symbol}      # Options chain
GET  /api/v2/options/gex/{symbol}        # Gamma exposure
GET  /api/v2/options/flow                # Options flow (query: unusual, sweep, smart_money)
GET  /api/v2/options/dark-pool           # Dark pool activity
GET  /api/v2/options/signals             # Flow-derived signals
GET  /api/v2/options/smart-money         # Institutional activity
```

---

## WebSocket Consolidation

**Current (fragmented):**
```
WS /ws/connect              # Generic
WS /ws/unified              # Multiplexed (main)
WS /ws/market               # Market data
WS /ws/market/{symbol}      # Symbol-specific
WS /ws/orderbook/{symbol}   # Order book
WS /ws/signals              # Signals
WS /ws/trades               # Executions
WS /ws/flow                 # Options flow
WS /ws/brain                # Brain updates
WS /ws/risk                 # Risk alerts
WS /ws/system               # System events
WS /ws/executions           # Duplicate of trades
```

**Consolidated:**
```
WS /ws/v2/stream            # Unified stream with channel subscription
                            # Channels: market, signals, positions, risk, brain, system
                            # Subscribe: { "action": "subscribe", "channels": ["market", "risk"] }
                            # Filter: { "action": "filter", "channel": "market", "symbols": ["SPY", "QQQ"] }
```

---

## Migration Path

### Step 1: Create v2 Router Structure
```python
# api/v2/__init__.py
from fastapi import APIRouter
from .health import router as health_router
from .market import router as market_router
from .trading import router as trading_router
# ... etc

api_v2 = APIRouter(prefix="/api/v2")
api_v2.include_router(health_router, tags=["health"])
api_v2.include_router(market_router, prefix="/market", tags=["market"])
api_v2.include_router(trading_router, prefix="/trading", tags=["trading"])
```

### Step 2: Implement Adapters
```python
# Redirect old endpoints to new
@app.get("/api/market/status")
async def old_market_status():
    return RedirectResponse(url="/api/v2/market/status", status_code=307)
```

### Step 3: Deprecation Headers
```python
@app.get("/api/signals/active", deprecated=True)
async def old_signals_active(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2025-03-01"
    response.headers["Link"] = '</api/v2/trading/signals?status=active>; rel="successor-version"'
    return await get_active_signals()
```

### Step 4: Update Frontend Gradually
```typescript
// api/client.ts
const API_VERSION = import.meta.env.VITE_API_VERSION || 'v1'
const API_BASE = `/api/${API_VERSION}`

// Feature flag for v2 migration
const useV2 = {
  market: true,
  trading: false,  // Enable when ready
  brain: false,
}
```

---

## Summary

| Domain | Current | Consolidated | Reduction |
|--------|---------|--------------|-----------|
| Market Data | 15 | 8 | 47% |
| Trading/Signals | 42 | 15 | 64% |
| Brain/ML | 103 | 25 | 76% |
| Risk | 18 | 10 | 44% |
| System/Settings | 44 | 15 | 66% |
| Options | 9 | 6 | 33% |
| WebSocket | 12 | 1 (unified) | 92% |
| **Total** | **359** | **~100** | **72%** |

### Key Benefits
1. **Single entry point** - Consolidate api/ and backend/ into one
2. **Consistent versioning** - All endpoints under /api/v2/
3. **Logical grouping** - Domain-driven organization
4. **Reduced duplication** - Merge redundant endpoints
5. **Unified WebSocket** - Single connection with channel subscriptions
6. **Better discoverability** - OpenAPI docs reflect actual structure
