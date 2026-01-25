# Platform Bot Behavioral Specifications

**Generated**: 2026-01-24
**Gate**: 2 (Bot Behavioral Spec)
**Milestone**: B (Bot Cloning)

## Overview

This document specifies the exact behavioral contracts that bots in quant-platform exhibit. These specifications must be replicated exactly in quant_industry_v1 for `APP_MODE=platform_compat` before any improvements are made.

---

## 1. TPT AGGRESSIVE BOT

### Source Files
- `/c/quant-platform/execution/tpt_aggressive_bot.py`
- `/c/quant-platform/brain/tpt_aggressive.py`

### 1.1 TPT Rules (IMMUTABLE CONSTRAINTS)

```python
@dataclass
class TPTRules:
    name: str = "Take Profit Trader"
    initial_balance: float = 50000.0
    balance_floor: float = 48000.0       # HARD: Cannot go below
    profit_target: float = 3000.0        # Must achieve
    max_contracts: int = 6               # HARD: Never exceed
    min_trading_days: int = 5            # Must trade 5 days minimum
    max_single_day_pct: float = 0.50     # HARD: 50% consistency rule
    trading_end_time: str = "17:00"      # HARD: Must be flat by 17:00 EST

    permitted_products: List[str] = [
        # Index Futures
        'ES', 'MES', 'NQ', 'MNQ', 'YM', 'MYM', 'RTY', 'M2K',
        # Commodities
        'CL', 'MCL', 'GC', 'MGC', 'SI', 'SIL',
        # Treasuries
        'ZB', 'ZN', 'ZF', 'ZT',
        # Currencies
        '6E', 'M6E', '6J', 'M6J', '6B', 'M6B', '6A', 'M6A', '6C', 'M6C',
    ]
```

### 1.2 Contract Multipliers

| Symbol | Multiplier ($/point) | Symbol | Multiplier ($/point) |
|--------|---------------------|--------|---------------------|
| ES | $50.00 | MES | $5.00 |
| NQ | $20.00 | MNQ | $2.00 |
| YM | $5.00 | MYM | $0.50 |
| RTY | $50.00 | M2K | $5.00 |
| CL | $1000.00 | MCL | $100.00 |
| GC | $100.00 | MGC | $10.00 |
| SI | $5000.00 | SIL | $1000.00 |
| ZB | $1000.00 | ZN | $1000.00 |
| 6E | $125000.00 | 6B | $62500.00 |

### 1.3 TPTTracker Behavioral Contract

```
INPUTS:
- symbol: str (futures symbol)
- contracts: int (number of contracts)
- direction: str ('LONG' | 'SHORT')
- price: float (execution price)

STATE:
- current_balance: float (starts at $50,000)
- open_positions: Dict[symbol -> {direction, contracts, price, time}]
- total_contracts: int
- daily_pnl: Dict[date -> pnl]
- trading_days: Set[date]
- status: str ('ACTIVE' | 'PASSED' | 'FAILED')

INVARIANTS:
1. total_contracts <= 6 (ALWAYS)
2. current_balance >= $48,000 OR status = 'FAILED'
3. No positions after 17:00 EST
4. No weekend trading (except Sunday 18:00+)
5. No counter positions (if LONG ES, cannot SHORT ES)

METHODS:

can_trade(symbol, contracts, direction) -> (bool, str)
  PRE: status == 'ACTIVE'
  CHECKS:
    - total_contracts + contracts <= 6
    - symbol base in permitted_products
    - no counter position exists
    - current time < 17:00 EST
    - not weekend (unless Sunday 18:00+)
  RETURNS: (allowed, reason)

open_position(symbol, contracts, direction, price) -> bool
  PRE: can_trade(symbol, contracts, direction) == True
  POST:
    - open_positions[symbol] created/updated
    - total_contracts += contracts
    - trading_days.add(today)
    - state persisted to disk
  SIDE_EFFECTS: Logs "OPEN: {direction} {contracts} {symbol} @ {price}"

close_position(symbol, contracts, price) -> (bool, pnl)
  PRE: symbol in open_positions
  POST:
    - PnL calculated: (price - entry) * contracts * multiplier * direction_sign
    - current_balance += pnl
    - daily_pnl[today] += pnl
    - If position fully closed: remove from open_positions
    - total_contracts -= contracts
    - Check failure condition (balance < floor)
    - Check pass condition (profit >= target AND days >= 5 AND consistency ok)
  SIDE_EFFECTS: Logs "CLOSE: {contracts} {symbol} @ {price} | PnL: ${pnl}"

_check_consistency() -> bool
  RULE: No single day profit > 50% of total profit
  FORMULA: biggest_day <= (current_balance - initial_balance) * 0.50
```

### 1.4 TPTAggressiveStrategy Behavioral Contract

```
PARAMETERS:
- daily_target: $800.00
- daily_max: $900.00 (stop trading to protect consistency)
- daily_min: $600.00 (minimum average needed)
- preferred_contracts: 4
- max_risk_per_trade: $200.00
- min_rr_ratio: 1.5
- target_rr_ratio: 2.0

STOP POINTS (per contract):
- ES: 2.0 points ($100/contract)
- MES: 4.0 points ($20/contract)
- NQ: 5.0 points ($100/contract)
- MNQ: 10.0 points ($20/contract)
- YM: 20.0 points ($100/contract)
- CL: 0.10 points ($100/contract)
- GC: 2.0 points ($200/contract)

DECISION LOGIC:

should_trade_now() -> (bool, str)
  CHECKS:
    1. tracker.status == 'ACTIVE'
    2. current time in trading hours
    3. not at daily_max profit
  RETURNS: (should_trade, reason)

evaluate_signal(signal, confidence, symbol) -> (bool, str)
  INPUT:
    - signal: 'BUY' | 'SELL' | 'HOLD'
    - confidence: 0.0 - 1.0
    - symbol: str
  RULES:
    - signal != 'HOLD'
    - confidence >= threshold (adaptive based on drawdown)
    - Risk per trade <= max_risk_per_trade
    - Not at daily max
  RETURNS: (take_trade, reason)

calculate_position_size(symbol, signal_confidence) -> int
  FORMULA:
    base_risk = max_risk_per_trade
    adjusted_risk = base_risk * confidence_factor * drawdown_factor
    contracts = adjusted_risk / (stop_points[symbol] * multiplier[symbol])
    contracts = min(contracts, 6 - tracker.total_contracts)
    contracts = max(1, contracts)
  RETURNS: contracts (int, 1-6)
```

### 1.5 TPTBot Main Loop

```
INITIALIZATION:
1. Create TPTTracker (loads state from disk)
2. Create TPTAggressiveStrategy(tracker)
3. Set execution_mode (PAPER | NINJATRADER | ALPACA)
4. Initialize ML brains (FuturesPropFirmBrain, UnifiedBrain)
5. Set watchlist = ['ES', 'NQ', 'MES', 'MNQ']
6. Set scan_interval = 30 seconds

MAIN LOOP (_run_loop):
  WHILE is_running:
    1. Check should_trade_now()
    2. IF should_trade:
       - FOR each symbol in watchlist:
         - Skip if position exists
         - Skip if at max contracts
         - Get signal from ML brain (priority order):
           a. FuturesPropFirmBrain.get_prediction()
           b. UnifiedBrain.get_ensemble_signal()
           c. Simple technical analysis fallback
         - Evaluate signal
         - IF take_trade: execute_trade()
    3. Monitor open positions
    4. Wait scan_interval

EOD MONITOR (_eod_monitor):
  EVERY 60 seconds:
    1. Get EST time
    2. IF time >= 16:45: flatten_all("EOD cutoff")
    3. IF time >= 16:30: warn about positions

FLATTEN ALL:
  FOR each symbol in open_positions:
    - Close at market
    - Notify callbacks
```

---

## 2. EXECUTION MODES

### Source File
- `/c/quant-platform/execution/executor.py`

### 2.1 ExecutionMode Enum

```python
class ExecutionMode(Enum):
    SIGNAL_ONLY = "signal_only"   # Generate signals, no execution
    AUTO_PAPER = "auto_paper"     # Auto-execute on paper account
    AUTO_LIVE = "auto_live"       # Auto-execute with real money
```

### 2.2 Behavioral Contracts by Mode

#### SIGNAL_ONLY Mode
```
BEHAVIOR:
- Signals generated normally
- ExecutionDecision created with was_executed=False
- No broker calls made
- All decisions logged for analysis

USE CASE:
- Backtesting
- Strategy development
- Shadow mode validation
```

#### AUTO_PAPER Mode
```
BEHAVIOR:
- Signals generated normally
- ExecutionDecision created
- Paper broker adapter called
- Simulated fills recorded
- P&L tracked in memory (not real)

USE CASE:
- Forward testing
- Canary deployments
- New strategy validation
```

#### AUTO_LIVE Mode
```
BEHAVIOR:
- Signals generated normally
- Risk engine MUST approve
- Kill switch MUST be off
- Real broker adapter called
- Real money on the line
- All fills tracked
- Alerts on failures

USE CASE:
- Production trading
- Only after SHADOW + CANARY stages
```

---

## 3. BRAIN-TO-BOT BRIDGE

### Source File
- `/c/quant-platform/core/brain_bot_bridge.py`

### 3.1 Deployment Stages

```python
class DeploymentStage(Enum):
    TRAINING = "training"       # Model training in Brain
    VALIDATION = "validation"   # Offline validation
    SHADOW = "shadow"           # Shadow mode (parallel, no trades)
    CANARY = "canary"           # Small % of traffic
    PRODUCTION = "production"   # Full production
    ROLLBACK = "rollback"       # Rolling back
```

### 3.2 Stage Transitions

```
                    ┌─────────────────────────────────────────────┐
                    │           DEPLOYMENT PIPELINE               │
                    └─────────────────────────────────────────────┘

    ┌──────────┐    ┌────────────┐    ┌────────┐    ┌────────┐    ┌────────────┐
    │ TRAINING │───→│ VALIDATION │───→│ SHADOW │───→│ CANARY │───→│ PRODUCTION │
    └──────────┘    └────────────┘    └────────┘    └────────┘    └────────────┘
         │               │                │              │              │
         │               │                │              │              │
         ▼               ▼                ▼              ▼              ▼
    [Brain trains]  [Offline test]  [No trades]   [5% traffic]   [100% traffic]
    [Hyperparams]   [Sharpe>1.5?]   [Compare]     [Monitor]      [Full load]
                                    [signals]     [health]
                                                                        │
                                                                        │ IF UNHEALTHY
                                                                        ▼
                                                               ┌──────────────┐
                                                               │   ROLLBACK   │
                                                               └──────────────┘
                                                                        │
                                                                        ▼
                                                               [Previous model]
                                                               [restored]
```

### 3.3 Stage Requirements

| Stage | Min Duration | Success Criteria | Auto-Promote |
|-------|-------------|------------------|--------------|
| TRAINING | N/A | Loss converged | No |
| VALIDATION | 1 day | Sharpe > 1.5, Win rate > 55% | No |
| SHADOW | 3 days | Signal accuracy > 50% | Yes if healthy |
| CANARY | 2 days | No degradation | Yes if healthy |
| PRODUCTION | Ongoing | Health checks pass | N/A |

### 3.4 Health Monitoring

```python
class ModelHealth(Enum):
    HEALTHY = "healthy"       # All metrics normal
    DEGRADED = "degraded"     # Some warnings
    UNHEALTHY = "unhealthy"   # Must rollback
    UNKNOWN = "unknown"       # Not enough data
```

**Health Check Rules:**
```
HEALTHY IF:
  - Win rate >= 50%
  - Sharpe ratio >= 1.0
  - Max drawdown <= 15%
  - No consecutive losses > 5
  - Execution latency < 100ms

DEGRADED IF:
  - Win rate in [40%, 50%)
  - Sharpe ratio in [0.5, 1.0)
  - Max drawdown in [15%, 20%)

UNHEALTHY IF:
  - Win rate < 40%
  - Sharpe ratio < 0.5
  - Max drawdown > 20%
  - Consecutive losses > 10
  - Critical error occurred
```

### 3.5 Rollback Contract

```
TRIGGER CONDITIONS:
1. health == UNHEALTHY
2. Manual trigger
3. Kill switch activated
4. Consecutive health check failures > threshold

ROLLBACK PROCEDURE:
1. Set stage = ROLLBACK
2. Load previous_deployment_id model
3. Swap model atomically
4. Log rollback_reason
5. Alert operators
6. Set rolled_back_at timestamp
7. Continue monitoring
```

### 3.6 Execution Feedback Loop

```python
@dataclass
class ExecutionFeedback:
    feedback_id: str
    timestamp: datetime
    model_id: str

    # Trade info
    symbol: str
    action: str
    predicted_direction: float
    actual_return: float
    pnl: float

    # Timing
    decision_latency_ms: float
    execution_latency_ms: float

    # Features (for replay/retraining)
    features: Dict[str, float]

    # Context
    regime: str
    volatility: float
    spread: float
```

**Feedback Flow:**
```
Bot executes trade
        │
        ▼
ExecutionFeedback created
        │
        ▼
Sent to Bridge.receive_feedback()
        │
        ▼
Stored in feedback_buffer
        │
        ▼
Aggregated for Brain retraining
        │
        ▼
Brain incorporates lessons
        │
        ▼
New model enters TRAINING stage
```

---

## 4. KILL SWITCH

### Source File
- `/c/quant-platform/execution/kill_switch.py`

### 4.1 Kill Switch Contract

```python
kill_switch = KillSwitch()

GLOBAL STATE:
- is_active: bool = False (default)
- reason: str = ""
- activated_at: Optional[datetime]

METHODS:

activate(reason: str) -> None
  POST:
    - is_active = True
    - reason = reason
    - activated_at = now()
    - All open positions FLATTENED
    - All pending orders CANCELLED
    - ALERT sent to operators

deactivate() -> None
  PRE: Manual confirmation required
  POST:
    - is_active = False
    - reason = ""
    - activated_at = None

check() -> bool
  RETURNS: is_active
  NOTE: Called before EVERY trade execution
```

### 4.2 Auto-Activation Triggers

```
TRIGGER CONDITIONS:
1. Daily loss > threshold (e.g., $2,000)
2. Consecutive losses > 5
3. Model health == UNHEALTHY
4. System error rate > 10%
5. Data feed disconnected > 30 seconds
6. Broker connection lost
7. Manual trigger via UI
```

---

## 5. SIGNAL GENERATION PRIORITY

### 5.1 Brain Priority Order

```
FOR each symbol:
  1. TRY FuturesPropFirmBrain.get_prediction()
     - Uses deep learning ensemble
     - Returns (signal, confidence, contracts, details)
     - IF signal != 'HOLD' AND confidence > 0.5: RETURN

  2. TRY UnifiedBrain.get_ensemble_signal()
     - Uses strategy ensemble
     - Returns (signal, confidence, strategies)
     - IF signal != 'HOLD' AND confidence > threshold: RETURN

  3. FALLBACK to simple_analysis()
     - Uses basic technical indicators
     - RSI, SMA crossover, MACD
     - Returns (signal, confidence, details)
```

### 5.2 Signal Evaluation

```
INPUT: (signal, confidence, symbol)

EVALUATION:
1. signal must be 'BUY' or 'SELL' (not 'HOLD')
2. confidence >= adaptive_threshold
   - Base: 0.60
   - Increase if in drawdown
   - Decrease if ahead of target
3. Risk check: potential_loss <= max_risk_per_trade
4. Daily P&L check: not at daily_max
5. Time check: within trading hours

OUTPUT: (take_trade: bool, reason: str)
```

---

## 6. DATA PERSISTENCE

### 6.1 State Files

| File | Content | Location |
|------|---------|----------|
| `tpt_state.json` | TPT evaluation state | `analytics/tpt_state.json` |
| `model_deployments.json` | Deployment history | `models/deployments.json` |
| `execution_feedback.json` | Trade feedback | `analytics/feedback.json` |
| `kill_switch_log.json` | Kill switch events | `logs/kill_switch.json` |

### 6.2 Persistence Contract

```
STATE PERSISTENCE:
- Save after EVERY state change
- Load on initialization
- Handle missing files gracefully (create defaults)
- Handle corrupt files (log error, use defaults)
- Use atomic writes (write to temp, then rename)
```

---

## SELF-GRADE SCORECARD - Gate 2

| Criterion | Status | Evidence |
|-----------|--------|----------|
| TPT Rules documented | PASS | TPTRules dataclass specified |
| Contract multipliers listed | PASS | All multipliers in table |
| TPTTracker behavioral contract | PASS | Inputs, state, invariants, methods |
| TPTAggressiveStrategy contract | PASS | Parameters, decision logic, sizing |
| TPTBot main loop documented | PASS | Initialization, loop, EOD monitor |
| ExecutionMode enum specified | PASS | SIGNAL_ONLY, AUTO_PAPER, AUTO_LIVE |
| Brain-to-Bot Bridge stages | PASS | 6 stages with transitions |
| Health monitoring rules | PASS | HEALTHY/DEGRADED/UNHEALTHY |
| Rollback contract | PASS | Triggers and procedure |
| Feedback loop specified | PASS | ExecutionFeedback dataclass |
| Kill switch contract | PASS | Activation, deactivation, triggers |
| Signal priority order | PASS | 3-level brain priority |
| Data persistence | PASS | Files and persistence rules |

**Gate 2 Status: PASSED**
**Milestone B Status: IN PROGRESS** (Specs complete, implementation needed)

**Next**: Gate 3 - Parity Harness (Deterministic golden tests)
