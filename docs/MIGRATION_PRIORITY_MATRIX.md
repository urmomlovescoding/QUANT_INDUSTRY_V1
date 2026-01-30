# Migration Priority Matrix

## Overview
Based on frontend usage analysis across 120+ TypeScript/TSX files, this matrix prioritizes API endpoints for migration based on actual usage patterns, business criticality, and technical dependencies.

---

## Priority Tiers

### 🔴 P0 - Critical (Migrate First)
*Core functionality that would break the app if unavailable*

| Endpoint | Usage Count | Used In | Notes |
|----------|-------------|---------|-------|
| `GET /api/health` | 15+ | Layout, SystemMonitor, Header | Health checks everywhere |
| `GET /api/system/status` | 10+ | Dashboard, SystemMonitor | System status polling |
| `GET /api/market/status` | 12+ | MarketStatus, Header, Dashboard | Market hours check |
| `GET /api/market/tickers` | 8+ | Dashboard, Header, watchlist | Core price display |
| `GET /api/positions` | 10+ | Positions, Portfolio, RightPanel | Position management |
| `GET /api/portfolio` | 8+ | Portfolio, Dashboard | Portfolio overview |
| `GET /api/signals/active` | 7+ | Signals, Dashboard, RightPanel | Active trading signals |
| `GET /api/risk/metrics` | 6+ | RiskEngine, Dashboard | Risk monitoring |
| `GET /api/risk/safety` | 5+ | SafetyGuard, Dashboard | Safety status |
| `WS /ws/unified` | 5+ | useWebSocket hook | Real-time data stream |

### 🟠 P1 - High (Migrate Week 1)
*Actively used in multiple views/components*

| Endpoint | Usage Count | Used In | Notes |
|----------|-------------|---------|-------|
| `GET /api/brain-v6/status` | 6+ | TradingBrain, AlgoBot, Dashboard | Brain status |
| `GET /api/brain-v6/signals` | 5+ | TradingBrain, Signals | ML signals |
| `POST /api/brain-v6/train` | 3+ | TradingBrain, MLTraining | Model training |
| `GET /api/settings` | 5+ | Settings, various | App settings |
| `GET /api/settings/api-keys` | 4+ | Settings, APIConnector | API key management |
| `POST /api/backtest/run` | 4+ | Backtesting, QuantPlatform | Backtest execution |
| `GET /api/strategies` | 4+ | Strategies, Backtesting | Strategy list |
| `GET /api/portfolio/performance` | 4+ | Performance, Portfolio | Performance metrics |
| `GET /api/portfolio/holdings` | 3+ | Portfolio, Holdings13F | Holdings list |
| `GET /api/ml/regime` | 4+ | RegimeDetect, TradingBrain | Regime detection |
| `POST /api/confirm-trade` | 3+ | TradeConfirm, QuickTrade | AI trade confirmation |
| `GET /api/feedback/status` | 3+ | Dashboard, TradingBrain | Feedback loop status |

### 🟡 P2 - Medium (Migrate Week 2)
*Used in specific feature views*

| Endpoint | Usage Count | Used In | Notes |
|----------|-------------|---------|-------|
| `GET /api/news` | 3+ | News, Dashboard | News feed |
| `GET /api/research/earnings` | 2+ | Earnings | Earnings calendar |
| `GET /api/options/chain/{symbol}` | 2+ | OptionsLab | Options chain |
| `GET /api/gex/{symbol}` | 2+ | GEXAnalysis | Gamma exposure |
| `GET /api/options/flow` | 2+ | FlowScanner | Options flow |
| `GET /api/screener/scan` | 2+ | Screener | Stock screener |
| `GET /api/orders` | 2+ | Positions, Trading | Order management |
| `POST /api/orders` | 2+ | QuickTrade, TradeConfirm | Order submission |
| `GET /api/trades/closed` | 2+ | Performance, Trades | Trade history |
| `GET /api/benchmark` | 2+ | Benchmark | Benchmark tracking |
| `GET /api/pairs` | 2+ | PairsTrading | Pairs trading |
| `POST /api/monte-carlo/run` | 2+ | MonteCarlo | Monte Carlo sim |

### 🟢 P3 - Low (Migrate Week 3+)
*Specialized features, lower usage*

| Domain | Endpoints | Used In | Notes |
|--------|-----------|---------|-------|
| Decision Intelligence | 12 endpoints | TradingBrain (conditional) | Shadow mode, exit learning |
| Cross-Exchange Arb | 8 endpoints | ArbDashboard | Specialized arbitrage |
| Microstructure | 7 endpoints | MicrostructureDashboard | Order flow analysis |
| PropFirm | 25 endpoints | (Future feature) | Prop firm management |
| Tax/Reconciliation | 27 endpoints | TaxLots | Accounting features |
| ICT/TPT | 5 endpoints | TPTDashboard | Trading strategies |

---

## Frontend API Client Analysis

### Centralized API Modules (from `api/client.ts`)
```
healthApi       → 2 endpoints
marketApi       → 7 endpoints  
brainApi        → 5 endpoints
feedbackApi     → 2 endpoints
signalsApi      → 4 endpoints
portfolioApi    → 4 endpoints
tradingApi      → 4 endpoints
riskApi         → 3 endpoints
backtestApi     → 3 endpoints
optionsApi      → 3 endpoints
researchApi     → 5 endpoints
settingsApi     → 4 endpoints
screenerApi     → 2 endpoints
neuralApi       → 3 endpoints
decisionIntelApi → 12 endpoints
dataIntegrityApi → 5 endpoints
```

### Hook-Based API Calls
| Hook | Endpoints Called | Polling Interval |
|------|------------------|------------------|
| `useBrain` | `/brain/*` (6 endpoints) | 30s |
| `useCrossExchange` | `/api/v1/arbitrage/*` (5 endpoints) | 5s |
| `useMicrostructure` | `/api/v1/microstructure/*` (4 endpoints) | 2s |
| `useOptionsFlow` | `/api/v1/options-flow/*` (5 endpoints) | 10s |
| `useNewsEvents` | `/api/v1/news-events/*` (5 endpoints) | 60s |
| `useWebSocket` | `/ws/*` (7 channels) | Real-time |

---

## Migration Dependencies

### Must Migrate Together (Atomic Groups)
```
Group 1: Core Trading
├── /api/positions
├── /api/portfolio
├── /api/orders
├── /api/signals/active
└── /ws/unified (positions channel)

Group 2: Brain V6
├── /api/brain-v6/status
├── /api/brain-v6/signals
├── /api/brain-v6/train
├── /api/brain-v6/config
└── /api/feedback/status

Group 3: Market Data
├── /api/market/status
├── /api/market/tickers
├── /api/market/quote/{symbol}
├── /api/charts/ohlcv/{symbol}
└── /ws/market

Group 4: Risk Management
├── /api/risk/metrics
├── /api/risk/safety
├── /api/risk/exposure
├── /api/kill-switch/*
└── /ws/risk
```

---

## Recommended Migration Order

### Phase 1: Foundation (Days 1-3)
1. Health & System (`/api/health`, `/api/system/*`)
2. Market Data (`/api/market/*`, `/api/charts/*`)
3. WebSocket Infrastructure (`/ws/*`)

### Phase 2: Core Trading (Days 4-7)
1. Portfolio & Positions (`/api/portfolio/*`, `/api/positions`)
2. Signals (`/api/signals/*`)
3. Orders (`/api/orders/*`)
4. Risk (`/api/risk/*`)

### Phase 3: ML/Brain (Days 8-10)
1. Brain V6 (`/api/brain-v6/*`)
2. ML endpoints (`/api/ml/*`, `/api/neural/*`)
3. Feedback loop (`/api/feedback/*`)

### Phase 4: Features (Days 11-14)
1. Settings & Config (`/api/settings/*`)
2. Backtest (`/api/backtest/*`)
3. Options (`/api/options/*`, `/api/gex/*`)

### Phase 5: Specialized (Days 15+)
1. Research (`/api/research/*`)
2. Decision Intelligence
3. Microstructure/Options Flow
4. PropFirm/Tax/Reconciliation

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| WebSocket migration breaks real-time | Critical | Test WS channels individually first |
| Brain V6 state lost | High | Preserve model checkpoints |
| Position data inconsistency | Critical | Add reconciliation checks |
| Settings migration loses user prefs | Medium | Export/import settings |
| Historical data gaps | Medium | Backfill from source APIs |

---

## Success Metrics

- [ ] All P0 endpoints responding <100ms
- [ ] WebSocket reconnection <5s
- [ ] Zero data loss during migration
- [ ] Frontend builds without API errors
- [ ] All integration tests passing
