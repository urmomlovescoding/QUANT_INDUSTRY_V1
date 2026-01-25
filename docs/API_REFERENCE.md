# QUANT INDUSTRY API Reference

## Overview

The QUANT INDUSTRY API provides programmatic access to all trading platform features including market data, portfolio management, trading signals, and ML/AI analysis.

**Base URL**: `http://localhost:8000`
**API Docs (Swagger)**: `http://localhost:8000/docs`
**API Docs (ReDoc)**: `http://localhost:8000/redoc`

---

## Authentication

Currently the API does not require authentication for local development. In production, API keys should be configured via environment variables.

---

## Response Format

### Success Response
```json
{
  "data": { ... },
  "timestamp": "2026-01-24T12:00:00.000Z"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE",
    "status": 400,
    "details": {},
    "timestamp": "2026-01-24T12:00:00.000Z"
  }
}
```

---

## Rate Limits

| Endpoint Type | Limit |
|--------------|-------|
| Standard API | 600 requests/minute |
| Training endpoints | 2-5 requests/minute |
| WebSocket | Unlimited |

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Endpoints

### Health & Status

#### GET /api/health
Health check with market status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-24T12:00:00",
  "market": {
    "session": "closed",
    "is_open": false,
    "is_weekend": true,
    "reason": "Weekend - Markets Closed"
  }
}
```

#### GET /api/system/health
Detailed system health check.

#### GET /api/system/status
System status including available services.

#### GET /api/system/resources
System resource usage (CPU, memory).

#### GET /api/system/ml-capabilities
Available ML/AI capabilities.

---

### Market Data

#### GET /api/market/status
Current market hours status.

**Response:**
```json
{
  "session": "regular",
  "is_open": true,
  "is_pre_market": false,
  "is_after_hours": false,
  "is_weekend": false,
  "is_holiday": false,
  "current_time_et": "2026-01-26 12:00:00 ET",
  "next_close": "2026-01-26 16:00:00 ET",
  "reason": "Regular Trading Hours"
}
```

#### GET /api/market/quote/{symbol}
Get quote for a symbol.

**Parameters:**
- `symbol` (path): Stock symbol (e.g., "SPY")

**Response:**
```json
{
  "symbol": "SPY",
  "price": 688.44,
  "change": 2.50,
  "change_pct": 0.36,
  "open": 687.00,
  "high": 690.00,
  "low": 686.00,
  "bid": 688.40,
  "ask": 688.48,
  "volume": 50000000,
  "prev_close": 685.94,
  "source": "alpaca",
  "market_session": "regular",
  "is_market_open": true
}
```

#### GET /api/market/tickers
Get list of tracked tickers.

#### GET /api/market/sectors
Get sector performance data.

#### GET /api/market/movers
Get top market movers.

---

### Charts & Technical Data

#### GET /api/charts/ohlcv/{symbol}
Get OHLCV candlestick data.

**Parameters:**
- `symbol` (path): Stock symbol
- `days` (query, optional): Number of days (default: 30)
- `interval` (query, optional): Candle interval (1m, 5m, 15m, 1h, 1d)

**Response:**
```json
{
  "symbol": "SPY",
  "data": [
    {
      "timestamp": "2026-01-24T09:30:00",
      "open": 687.00,
      "high": 688.50,
      "low": 686.50,
      "close": 688.00,
      "volume": 1000000
    }
  ]
}
```

#### GET /api/charts/indicators/{symbol}
Get technical indicators for a symbol.

---

### Portfolio

#### GET /api/positions
Get current positions.

#### GET /api/portfolio/holdings
Get portfolio holdings with details.

#### GET /api/portfolio/performance
Get portfolio performance metrics.

---

### Trading Signals

#### GET /api/signals/active
Get currently active trading signals.

**Response:**
```json
{
  "signals": [
    {
      "symbol": "SPY",
      "signal": "BUY",
      "strength": 0.85,
      "entry_price": 688.00,
      "stop_loss": 680.00,
      "take_profit": 700.00,
      "confidence": 0.78,
      "timestamp": "2026-01-24T12:00:00"
    }
  ]
}
```

---

### PropFirm Brain V6 (ML/AI)

#### GET /api/brain-v6/status
Get brain status and capabilities.

**Response:**
```json
{
  "enabled": true,
  "model_loaded": true,
  "last_trained": "2026-01-20T15:30:00",
  "accuracy": 0.72,
  "total_trades": 150,
  "win_rate": 0.65
}
```

#### GET /api/brain-v6/signal/{symbol}
Get AI-generated trading signal.

**Parameters:**
- `symbol` (path): Stock symbol

**Response:**
```json
{
  "symbol": "SPY",
  "action": "BUY",
  "confidence": 0.78,
  "position_size": 0.02,
  "entry_price": 688.00,
  "stop_loss": 680.00,
  "take_profit": 700.00,
  "regime": "TRENDING_UP",
  "reasoning": "Strong momentum with favorable regime"
}
```

#### POST /api/brain-v6/train
Trigger brain training.

**Body:**
```json
{
  "symbols": ["SPY", "QQQ"],
  "epochs": 100,
  "use_gpu": true
}
```

#### GET /api/brain-v6/config
Get brain configuration.

#### POST /api/brain-v6/config
Update brain configuration.

#### GET /api/brain-v6/rulesets
Get available trading rulesets.

#### POST /api/brain-v6/set-ruleset
Set active ruleset.

---

### Backtesting

#### POST /api/backtest/run
Run a backtest.

**Body:**
```json
{
  "symbol": "SPY",
  "strategy": "momentum",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000,
  "parameters": {
    "lookback": 20,
    "threshold": 0.02
  }
}
```

**Response:**
```json
{
  "total_return": 0.25,
  "sharpe_ratio": 1.8,
  "max_drawdown": -0.08,
  "win_rate": 0.62,
  "total_trades": 45,
  "equity_curve": [...],
  "trades": [...]
}
```

---

### Options

#### GET /api/options/chain/{symbol}
Get options chain for a symbol.

#### GET /api/options/gex/{symbol}
Get Gamma Exposure (GEX) analysis.

---

### Settings

#### GET /api/settings
Get current settings.

#### POST /api/settings
Update settings.

#### GET /api/settings/presets
Get available UI presets.

#### POST /api/settings/preset/{preset_name}
Apply a preset.

#### GET /api/settings/api-keys
Get API key configuration (masked).

#### POST /api/settings/api-keys
Update API keys.

---

### WebSocket Endpoints

#### WS /ws/market
Real-time market data stream.

**Subscribe:**
```json
{"action": "subscribe", "symbols": ["SPY", "QQQ"]}
```

**Unsubscribe:**
```json
{"action": "unsubscribe", "symbols": ["SPY"]}
```

#### WS /ws/quotes
Real-time quote updates.

#### WS /ws/brain
Brain signal updates.

#### WS /ws/portfolio
Portfolio updates.

---

## Error Codes

| Code | Description |
|------|-------------|
| NOT_FOUND | Resource not found |
| VALIDATION_ERROR | Input validation failed |
| SERVICE_UNAVAILABLE | External service unavailable |
| RATE_LIMIT_EXCEEDED | Too many requests |
| DATA_ERROR | Data fetch/processing error |
| AUTH_REQUIRED | Authentication required |
| CONFIG_ERROR | Configuration error |
| INTERNAL_ERROR | Internal server error |

---

## Examples

### Python
```python
import requests

# Get quote
resp = requests.get("http://localhost:8000/api/market/quote/SPY")
quote = resp.json()
print(f"SPY Price: ${quote['price']}")

# Get brain signal
resp = requests.get("http://localhost:8000/api/brain-v6/signal/SPY")
signal = resp.json()
print(f"Signal: {signal['action']} with {signal['confidence']:.0%} confidence")
```

### JavaScript
```javascript
// Get quote
const resp = await fetch('http://localhost:8000/api/market/quote/SPY');
const quote = await resp.json();
console.log(`SPY Price: $${quote.price}`);

// WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/market');
ws.onopen = () => {
  ws.send(JSON.stringify({action: 'subscribe', symbols: ['SPY', 'QQQ']}));
};
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

### cURL
```bash
# Health check
curl http://localhost:8000/api/health

# Get quote
curl http://localhost:8000/api/market/quote/SPY

# Get brain signal
curl http://localhost:8000/api/brain-v6/signal/SPY

# Run backtest
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"symbol": "SPY", "strategy": "momentum"}'
```
