# QUANT INDUSTRY V1 - Development Roadmap

This roadmap outlines the path from current state to production-grade quantitative trading platform.

---

## Current State Assessment

### Completed P0 Fixes (This Session)
1. **Hardcoded API Keys Removed** - Secrets now load from environment variables
2. **Timezone Utility Added** - `utc_now()` ensures deterministic timestamps
3. **SafetyGuard Added to Alpaca** - Live and paper trades go through safety checks
4. **Thread Safety in Executor** - Order tracking protected by RLock

### Remaining Critical Issues
- 95% of ML/brain modules untested
- 434 instances of `datetime.now()` need migration to `utc_now()`
- Lookahead bias risk in feature store
- Rate limiter holds lock during sleep

---

## Milestone A: Stabilize (2-3 weeks)

**Goal**: Achieve reliable, deterministic operation with proper testing.

### Deliverables

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Add tests for brain modules | P0 | L | Pending |
| Migrate `datetime.now()` → `utc_now()` | P0 | M | Pending |
| Fix rate limiter lock contention | P1 | S | Pending |
| Add OHLC validation to Quote contract | P1 | S | Pending |
| Consolidate market hours logic | P2 | S | Pending |
| Add idempotency to order submission | P0 | M | Pending |

### Success Criteria
- [ ] 70%+ test coverage on brain modules
- [ ] All timestamps use `utc_now()` or explicit timezone
- [ ] Rate limiter non-blocking
- [ ] No duplicate orders possible
- [ ] CI passes on all PRs

### Technical Risks
- Brain module complexity makes testing challenging
- Migration to `utc_now()` may break existing saved data
- Idempotency requires persistent order ID tracking

---

## Milestone B: Research → Backtest Parity (3-4 weeks)

**Goal**: Ensure research signals produce identical results in backtesting.

### Deliverables

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Enforce `lag_periods >= 1` in feature store | P0 | S | Pending |
| Add determinism controls (global seed manager) | P0 | M | Pending |
| Create backtest reproducibility test suite | P1 | M | Pending |
| Standardize data model (OHLCV + metadata) | P1 | M | Pending |
| Add Parquet support for large datasets | P2 | M | Pending |
| Build factor pipeline standardization | P2 | L | Pending |
| Add PnL attribution reporting | P2 | M | Pending |

### Success Criteria
- [ ] Same signal inputs → same signal outputs (100% reproducible)
- [ ] Backtest results match research notebook results
- [ ] No lookahead bias in any feature
- [ ] Feature store supports Parquet export
- [ ] Clear PnL attribution by factor/strategy

### Technical Risks
- Existing research may have hidden lookahead bias
- Determinism hard to achieve with external API calls
- Legacy pickle files need migration

---

## Milestone C: Paper Trading Validation (2-3 weeks)

**Goal**: Prove system works correctly with paper trading before live.

### Deliverables

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Add order lifecycle state machine | P0 | M | Pending |
| Implement retry logic with exponential backoff | P1 | S | Done (partial) |
| Add idempotent order submission | P0 | M | Pending |
| Create paper trading reconciliation | P1 | M | Pending |
| Add observability (OpenTelemetry traces) | P2 | M | Pending |
| Build position reconciliation against broker | P1 | M | Pending |

### Success Criteria
- [ ] Orders have clear state machine (NEW → SUBMITTED → PARTIAL → FILLED)
- [ ] Failed orders retry with backoff
- [ ] No duplicate orders ever
- [ ] Positions match broker positions
- [ ] Full trace from signal to fill

### Technical Risks
- Broker API rate limits may cause issues
- WebSocket reconnection handling
- Time synchronization with broker

---

## Milestone D: Live Execution Readiness (4-6 weeks)

**Goal**: Production-ready live trading with full safety controls.

### Deliverables

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| Complete SafetyGuard integration | P0 | M | In Progress |
| Add real-time P&L monitoring | P0 | M | Pending |
| Implement circuit breaker patterns | P1 | M | Done (partial) |
| Add audit logging (JSONL) | P1 | S | Done (partial) |
| Create runbook for incidents | P2 | S | Pending |
| Add alerting (Discord/Telegram/Slack) | P2 | M | Pending |
| Build dashboard for monitoring | P2 | L | Pending |

### Success Criteria
- [ ] Kill switch stops all trading within 1 second
- [ ] Daily loss limit enforced automatically
- [ ] Full audit trail of every decision
- [ ] Alerts fire on anomalies
- [ ] Runbook covers common failure modes

### Technical Risks
- Live market conditions differ from paper
- API failures during critical moments
- Slippage estimation accuracy

---

## Architecture Improvements (Ongoing)

### Short-term (This Month)
1. **Clean Strategy Interface**
   ```python
   class Strategy(ABC):
       def generate_signal(self, data: pd.DataFrame) -> Signal
       def update(self, fill: Fill) -> None
   ```

2. **Typed Configuration** (Pydantic Settings)
   ```python
   class TradingConfig(BaseSettings):
       max_daily_loss: float = 2000.0
       max_position_pct: float = 0.05
   ```

3. **Unified Data Model**
   ```python
   @dataclass
   class OHLCV:
       timestamp: datetime  # Always UTC
       open: float
       high: float
       low: float
       close: float
       volume: int
   ```

### Medium-term (This Quarter)
1. Event-driven backtesting engine
2. Multi-asset support (futures, options, crypto)
3. Distributed training for ML models
4. Real-time feature computation

### Long-term (This Year)
1. Multi-broker execution
2. Market making strategies
3. HFT-grade latency optimization
4. Kubernetes deployment

---

## Testing Strategy

### Unit Tests (Target: 80% coverage)
- All utility functions
- All data transformations
- All signal generation logic

### Integration Tests (Target: 70% coverage)
- API endpoints
- Database operations
- Broker adapters (mocked)

### Parity Tests (Already strong)
- Platform compatibility
- Golden data comparisons

### End-to-End Tests (Target: Key flows)
- Signal → Risk → Execution → Fill
- Paper trading round-trip
- Kill switch activation

---

## How to Run

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Tests
```bash
# All tests
python run_tests.py

# Quick tests (skip slow)
python run_tests.py --quick

# Specific module
python run_tests.py --module brain

# With coverage
python run_tests.py --coverage
```

### Desktop (Electron)
```bash
START.bat
```

---

## Contributing

1. Create feature branch from `develop`
2. Write tests for new code
3. Ensure CI passes
4. Request review
5. Squash and merge

---

## Contact

For questions about this roadmap, open an issue or reach out to the maintainers.

---

*Last updated: February 4, 2026*
