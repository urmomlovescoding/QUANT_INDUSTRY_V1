# QUANT INDUSTRY V1 - Improvement Prompt for Claude

## Context
You are improving QUANT INDUSTRY V1, an institutional-grade algorithmic trading platform with:
- 100 Python files, ~48,000 lines of code
- React/TypeScript frontend with 60+ components
- ML/DL/RL models for trading
- Real-time order book analysis
- Monte Carlo stress testing
- Portfolio optimization (HRP, Black-Litterman)
- Live trading orchestration

## Current Test Results: 8/8 PASSED
- Core imports: PASS
- ML modules: PASS  
- Portfolio/HFT: PASS
- Data/Features: PASS
- Trading Orchestrator: PASS
- Slippage Model: PASS (7.9 bps)
- Monte Carlo: PASS (VaR95=-18.9%)
- Order Book: PASS (5 bps spread)

## CRITICAL IMPROVEMENTS NEEDED

### 1. Integration Tests (Priority: CRITICAL)
Create comprehensive integration tests for:
```python
# backend/tests/test_integration_full.py
- RealisticBacktestEngine with AlmgrenChrissSlippageModel
- TradingOrchestrator end-to-end workflow
- FeatureStore -> ML Model -> Signal pipeline
- WalkForwardValidator with actual strategy
- RegimeAwareEnsemble switching logic
```

### 2. Error Handling & Recovery (Priority: CRITICAL)
Add robust error handling to:
```python
# backend/data/unified_api.py
- Exponential backoff retry logic
- Connection pooling
- Timeout handling
- Graceful degradation

# backend/trading/orchestrator.py  
- Circuit breaker pattern
- Position recovery on restart
- Order state persistence
```

### 3. API Endpoints for New Features (Priority: HIGH)
Create FastAPI endpoints for:
```python
# backend/api/routes/
- POST /api/montecarlo/simulate
- GET /api/portfolio/optimize/{method}
- POST /api/features/compute
- GET /api/orderbook/{symbol}/metrics
- POST /api/calibration/record
- GET /api/regime/current
```

### 4. Frontend Enhancements (Priority: HIGH)
Update React components:
```typescript
// New views needed:
- MonteCarloView: Interactive stress testing with charts
- PortfolioOptimizerView: Efficient frontier visualization
- OrderBookView: Real-time depth chart
- FeatureStoreView: Feature monitoring dashboard
- CalibrationView: Model confidence tracking

// Improvements to Dashboard.tsx:
- Add regime indicator widget
- Monte Carlo VaR widget
- Order book imbalance indicator
- Real-time slippage tracker
```

### 5. WebSocket Real-Time Updates (Priority: HIGH)
Implement WebSocket streaming for:
```python
# backend/api/websocket.py
- Order book updates
- Position changes
- Signal generation events
- Risk metric changes
- Regime transitions
```

### 6. Configuration Management (Priority: MEDIUM)
```python
# backend/config/unified_config.py
- Pydantic settings management
- Environment-based config
- Secrets handling
- Config validation
```

### 7. Model Persistence (Priority: MEDIUM)
```python
# backend/ml/model_registry.py
- Save/load trained models
- Version tracking
- A/B test support
- Rollback capability
```

## Code Quality Requirements
- Type hints on all functions
- Docstrings with examples
- Unit tests for new code
- Logging with structured format
- Error messages that help debugging

## Files to Create/Modify

### New Files:
1. `backend/tests/test_integration_full.py` - Full integration tests
2. `backend/api/routes/advanced.py` - New API endpoints
3. `backend/api/websocket.py` - WebSocket handlers
4. `backend/config/unified_config.py` - Unified configuration
5. `backend/ml/model_registry.py` - Model persistence
6. `frontend/src/views/MonteCarloView.tsx` - Monte Carlo UI
7. `frontend/src/views/OrderBookView.tsx` - Order book visualization
8. `frontend/src/components/widgets/RegimeWidget.tsx` - Regime indicator
9. `frontend/src/components/widgets/RiskWidget.tsx` - VaR/risk display

### Modify:
1. `backend/data/unified_api.py` - Add retry logic
2. `backend/trading/orchestrator.py` - Add circuit breaker
3. `frontend/src/views/Dashboard.tsx` - Add new widgets
4. `backend/api/main.py` - Register new routes

## Output Format
Provide complete, working code files. Each file should:
1. Have proper imports
2. Include type hints
3. Have docstrings
4. Include error handling
5. Be production-ready

Start with the integration tests, then API endpoints, then frontend.
