# DATA PROVENANCE LEDGER

**Last Updated: 2026-01-25**

This document tracks the origin and trustworthiness of all data in the system.

---

## Data Source Classification

| Classification | Symbol | Meaning |
|----------------|--------|---------|
| LIVE_VERIFIED | ✅ | Real-time data from verified API |
| LIVE_UNVERIFIED | 🟡 | Real-time but quality uncertain |
| CACHED | 📦 | Previously fetched, within TTL |
| STALE | ⏰ | Cached beyond TTL |
| FALLBACK | ⚠️ | Synthetic/last-known prices |
| SIMULATED | 🔴 | Random/fake data |
| UNAVAILABLE | ❌ | No data available |

---

## 1. MARKET DATA PROVENANCE

### Real-Time Quotes

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/market/quote/{symbol}` | AlpacaDataSource | ✅ LIVE_VERIFIED | Primary source |
| `/api/market/quote/{symbol}` | TradierDataSource | ✅ LIVE_VERIFIED | Fallback #1 |
| `/api/market/quote/{symbol}` | YahooDataSource | 🟡 LIVE_UNVERIFIED | Fallback #2, delayed |
| `/api/market/quote/{symbol}` | FinnhubDataSource | 🟡 LIVE_UNVERIFIED | Fallback #3 |
| `/api/market/quote/{symbol}` | FallbackDataSource | ⚠️ FALLBACK | Last resort synthetic |

### Historical Data (OHLCV)

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/charts/ohlcv/{symbol}` | Yahoo Finance | ✅ LIVE_VERIFIED | yfinance library |
| `/api/charts/ohlcv/{symbol}` | Alpaca | ✅ LIVE_VERIFIED | Historical bars API |

### Market Status

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/market/status` | market_hours.py | ✅ LIVE_VERIFIED | Real-time calculation |

---

## 2. TRADING DATA PROVENANCE

### Positions

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/positions` | AlpacaBroker | ✅ LIVE_VERIFIED | If connected |
| `/api/positions` | TradingService | 🟡 PAPER | Paper trading simulation |
| `/api/positions` | Fallback | 🔴 SIMULATED | Hardcoded demo positions |

### Orders

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/orders` | TradingService | 🟡 PAPER | Paper trading |
| POST `/api/orders` | AlpacaBroker | ✅ LIVE_VERIFIED | If live mode |

### Signals

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/signals` | PropFirmBrainV6 | ✅ LIVE_VERIFIED | Real ML signals |
| WebSocket signals | random.choice() | 🔴 SIMULATED | **BUG: Random signals** |

---

## 3. RESEARCH DATA PROVENANCE

### Institutional Holdings (13F)

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/research/13f/{symbol}` | random.randint() | 🔴 SIMULATED | **BUG: Fake data** |

**Required Fix:** Connect to SEC EDGAR API or FINRA API

### SEC Filings

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/research/sec-filings/{symbol}` | random.choice() | 🔴 SIMULATED | **BUG: Fake data** |

**Required Fix:** Connect to SEC EDGAR API

### Dark Pool Data

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/research/dark-pool/{symbol}` | random.randint() | 🔴 SIMULATED | **BUG: Fake data** |

**Required Fix:** Connect to FINRA ATS data

### Earnings Data

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/research/earnings/{symbol}` | random.uniform() | 🔴 SIMULATED | **BUG: Fake data** |

**Required Fix:** Connect to earnings API (Alpha Vantage, FMP)

---

## 4. OPTIONS DATA PROVENANCE

### Options Chain

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/options/chain/{symbol}` | TradierDataSource | ✅ LIVE_VERIFIED | If API key set |
| `/api/options/chain/{symbol}` | Generated | ⚠️ FALLBACK | Black-Scholes synthetic |

### Options Flow

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/options/flow` | OptionsService.get_unusual_flow() | ✅ LIVE_VERIFIED | From chain data |
| `/api/options/flow` | random.choice() | 🔴 SIMULATED | **Fallback is random** |

---

## 5. NEWS & SENTIMENT PROVENANCE

### News

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/news/{symbol}` | NewsAPI | ✅ LIVE_VERIFIED | If API key set |

### Sentiment

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/news/sentiment/{symbol}` | random.uniform() | 🔴 SIMULATED | **BUG: Fake data** |

**Required Fix:** Use NLP sentiment analysis on real news

---

## 6. ML/BRAIN DATA PROVENANCE

### Brain Status

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/brain-v6/status` | PropFirmBrainV6 | ✅ LIVE_VERIFIED | Real state |

### Brain Metrics

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/brain-v6/metrics` | random.uniform() | 🔴 SIMULATED | **BUG: Fake accuracy** |

**Required Fix:** Use actual trade outcomes

### Brain Signals

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/brain-v6/signal/{symbol}` | PropFirmBrainV6 | ✅ LIVE_VERIFIED | Real ML |

### ML Logs

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/ml/logs` | random.choice() | 🔴 SIMULATED | **BUG: Fake logs** |

---

## 7. SYSTEM DATA PROVENANCE

### Health

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/health` | HealthService | ✅ LIVE_VERIFIED | Real system metrics |
| `/api/system/resources` | psutil + random | 🟡 MIXED | **Some random values** |

### Connector Status

| Endpoint | Data Source | Provenance | Notes |
|----------|-------------|------------|-------|
| `/api/connectors/status` | random.randint() | 🔴 SIMULATED | **BUG: Fake latency** |

---

## 8. WEBSOCKET DATA PROVENANCE

### Market Updates

| Channel | Data Source | Provenance | Notes |
|---------|-------------|------------|-------|
| `market` | random.uniform() | 🔴 SIMULATED | **BUG: Fake prices** |

### Signal Updates

| Channel | Data Source | Provenance | Notes |
|---------|-------------|------------|-------|
| `signals` | random.choice() | 🔴 SIMULATED | **BUG: Fake signals** |

### Trade Updates

| Channel | Data Source | Provenance | Notes |
|---------|-------------|------------|-------|
| `trades` | random.choice() | 🔴 SIMULATED | **BUG: Fake trades** |

### Flow Updates

| Channel | Data Source | Provenance | Notes |
|---------|-------------|------------|-------|
| `flow` | random.randint() | 🔴 SIMULATED | **BUG: Fake flow** |

---

## 9. DATA INTEGRITY RULES

### Rule 1: No Random in Production Paths
```python
# BAD - Never do this in production endpoints
"eps_estimate": round(random.uniform(0.5, 5), 2)

# GOOD - Return real data or explicit unavailability
"eps_estimate": earnings_api.get_estimate(symbol) or {"status": "UNAVAILABLE"}
```

### Rule 2: Always Label Data Source
```python
# BAD - No source information
return {"price": 150.00}

# GOOD - Include provenance
return {"price": 150.00, "source": "alpaca", "timestamp": "...", "is_live": True}
```

### Rule 3: Distinguish Modes
```python
class DataMode(Enum):
    LIVE = "live"           # Real broker, real money
    PAPER = "paper"         # Paper trading, real prices
    BACKTEST = "backtest"   # Historical simulation
    SIMULATION = "simulation"  # All fake data (demo)
```

### Rule 4: Single Source of Truth
```python
# BAD - Multiple price sources
price1 = data_service.get_quote(symbol).price
price2 = MARKET_DATA[symbol]["price"]  # Might be stale

# GOOD - Single authoritative function
price = get_price_truth(symbol)  # Always consistent
```

---

## 10. PROVENANCE ENFORCEMENT CHECKLIST

### Before Each Release

- [ ] No `random.` in non-simulation endpoints
- [ ] All quotes have `.source` field
- [ ] All API responses have `data_mode` field
- [ ] WebSocket messages labeled with source
- [ ] Fallback data clearly marked as "FALLBACK"
- [ ] Stale data includes `last_updated` timestamp
- [ ] Unavailable data returns `{"status": "UNAVAILABLE"}` not random

### Data Quality Gates

- [ ] Price sanity check: 0 < price < 100000
- [ ] Volume sanity check: volume >= 0
- [ ] OHLCV check: high >= low
- [ ] Timestamp check: not in future
- [ ] Source check: known valid source

---

## 11. MIGRATION PLAN

### Phase 1: Add Source Labeling
Add `source` and `is_live` to all data responses.

### Phase 2: Remove Random from Production
Replace all `random.` calls with real data or explicit "UNAVAILABLE".

### Phase 3: Add Data Mode
Implement global `DATA_MODE` with enforcement.

### Phase 4: Audit All Paths
Run data provenance tests to verify no simulation leakage.

---

## Summary Statistics

| Category | Real Data | Simulated | Mixed |
|----------|-----------|-----------|-------|
| Market Data | 5 endpoints | 0 | 1 |
| Trading Data | 3 endpoints | 0 | 2 |
| Research Data | 0 endpoints | 5 | 0 |
| Options Data | 2 endpoints | 0 | 1 |
| News Data | 1 endpoints | 1 | 0 |
| ML Data | 3 endpoints | 2 | 0 |
| System Data | 1 endpoints | 1 | 1 |
| WebSocket | 0 channels | 4 | 0 |
| **TOTAL** | **15** | **13** | **5** |

**Simulated data must be eliminated from production paths.**
