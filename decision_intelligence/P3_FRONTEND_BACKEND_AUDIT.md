# P3: Frontend-Backend Connection Audit

**Date:** 2025-01-13

## Summary

The frontend-backend connection is **generally solid** with good foundations:
- ✅ Centralized API client with error handling
- ✅ WebSocket hooks with auto-reconnection
- ✅ Loading states and skeleton loaders
- ✅ Error display components
- ✅ Zustand state management with proper patterns

## Issues Identified

### Critical Issues

1. **WebSocket URL Hardcoded** 
   - Location: `frontend/src/hooks/useWebSocket.ts`
   - Issue: `ws://${window.location.hostname}:8000/ws/connect` hardcoded
   - Fix: Use environment variable

2. **Missing API Types for New Decision Intelligence Endpoints**
   - Location: `frontend/src/api/client.ts`
   - Issue: No types for `/api/decision-intelligence/*` endpoints
   - Fix: Add types and API methods

### Medium Issues

3. **API Base URL Empty by Default**
   - Location: `frontend/src/api/client.ts`
   - Issue: `API_BASE_URL` defaults to empty string
   - Fix: Add sensible default or require env variable

4. **Hardcoded Fallback Values in Dashboard**
   - Location: `frontend/src/views/Dashboard.tsx`
   - Issue: Some metrics show hardcoded values when data unavailable
   - Fix: Show proper "No data" states or 0

5. **No Connection Status Indicator in UI**
   - Issue: User has no visual indicator of backend/WebSocket connection
   - Fix: Add connection status component

### Low Priority Issues

6. **Some Backend Endpoints Not Exposed**
   - New endpoints in `backend/main.py` not in frontend API client
   - `/api/data-mode`, `/api/data-integrity/*`, etc.

7. **No Offline/Disconnection Recovery UI**
   - When backend disconnects, no user-friendly message

## Backend Endpoints Audit

### Exposed to Frontend (in client.ts)
- ✅ `/api/health` - Health check
- ✅ `/api/market/tickers` - Market tickers
- ✅ `/api/market/quote/{symbol}` - Single quote
- ✅ `/api/market/status` - Market status
- ✅ `/api/brain-v6/status` - Brain status
- ✅ `/api/signals` - Trading signals
- ✅ `/api/positions` - Positions
- ✅ `/api/portfolio` - Portfolio
- ✅ `/api/risk/metrics` - Risk metrics
- ✅ `/api/options/chain/{symbol}` - Options chain
- ✅ `/api/charts/ohlcv/{symbol}` - OHLCV data
- ✅ `/api/screener/scan` - Stock screener
- ✅ `/api/backtest/run` - Backtesting
- ✅ `/api/news` - News feed

### Missing from Frontend (need to add)
- ❌ `/api/data-mode` - Data mode management
- ❌ `/api/data-integrity/*` - Data integrity
- ❌ `/api/system/memory` - Memory monitor
- ❌ `/api/data/staleness` - Data staleness
- ❌ Decision Intelligence endpoints (new)

## WebSocket Channels Audit

### Implemented
- ✅ `market_data` - Real-time prices
- ✅ `order_book` - Level 2 data
- ✅ `signals` - Trading signals
- ✅ `portfolio` - Portfolio updates
- ✅ `risk` - Risk metrics
- ✅ `executions` - Order executions
- ✅ `alerts` - System alerts
- ✅ `system` - System status

### Issues
- WebSocket reconnection works but no UI feedback
- No indication when WS is connecting/reconnected

## Fixes Applied

### Fix 1: Environment-based WebSocket URL
### Fix 2: Add Decision Intelligence API types
### Fix 3: Add Connection Status component
### Fix 4: Add missing API methods
