# Decision Intelligence Platform

**An AI-native framework for autonomous trading decisions with full explainability.**

## Overview

The Decision Intelligence platform provides:

- 🧠 **AI Control Plane** - Centralized AI decision coordination with kill switch
- 📊 **Decision Trace** - Full audit trail with graph-based decision tracking
- 📈 **Exit Value Learning** - Reinforcement learning for optimal exit timing
- 👥 **Shadow Mode** - Safe A/B testing of new strategies without risk
- 🔄 **Self-Improvement** - Autonomous system improvement triggered by drift

## Quick Start

```python
from decision_intelligence import (
    get_control_plane,
    get_decision_trace,
    get_exit_value_learner,
    get_shadow_manager,
    get_self_improvement_orchestrator,
    ControlPlaneMode,
)

# Initialize AI Control Plane
control_plane = get_control_plane()

# Check system status
status = control_plane.get_status()
print(f"Mode: {status['mode']}, Active: {status['is_active']}")

# Register a component
control_plane.register_component("my_strategy")

# Create decision context
context = control_plane.create_context(
    symbol="AAPL",
    regime="trending_bull",
    regime_confidence=0.85,
    signal={"direction": "LONG", "confidence": 0.72}
)

# Record a decision
control_plane.record_decision(
    context_id=context["context_id"],
    component="my_strategy",
    decision="ENTER_LONG",
    reason="Strong momentum + regime confirmation",
    data={"entry_price": 185.50}
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Control Plane                            │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ Mode Control │ Kill Switch  │ Context Mgmt │ Safety Check │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                     Decision Modules                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Decision     │  │ Exit Value   │  │ Shadow       │          │
│  │ Trace        │  │ Learner      │  │ Manager      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                     Self-Improvement                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Monitor → Analyze → Propose → Validate → Deploy             ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. AI Control Plane (`ai_control_plane.py`)

Central coordination for all AI decisions.

**Modes:**
- `SHADOW` - Decisions logged but not executed
- `PAPER` - Paper trading with virtual execution
- `LIVE` - Real execution enabled
- `DISABLED` - All AI decision-making halted

**Key Features:**
- Global kill switch for emergency stop
- Safety checks before any live action
- Decision context management
- Component registration and health monitoring

```python
# Mode transitions
control_plane.set_mode(ControlPlaneMode.PAPER)

# Emergency stop
control_plane.engage_kill_switch("Market volatility spike")

# Safety check before execution
if control_plane.check_safety():
    execute_trade(order)
```

### 2. Decision Trace (`decision_trace.py`)

Graph-based decision audit trail using NetworkX.

**Features:**
- Full decision path reconstruction
- Pattern analysis (success/failure patterns)
- Graph visualization support
- Time-based queries

```python
trace = get_decision_trace()

# Add decision node
trace.add_decision(
    context_id="ctx_123",
    component="regime_detector",
    decision="REGIME_BULL",
    outcome="correct",
    metadata={"confidence": 0.92}
)

# Get full decision path
path = trace.get_decision_path("ctx_123")

# Analyze failure patterns
patterns = trace.analyze_failure_patterns(lookback_days=30)
```

### 3. Exit Value Learning (`exit_value_learning.py`)

Reinforcement learning for optimal exit timing.

**State Space:**
- Regime (bull/bear/sideways/volatile)
- Time in trade (discretized buckets)
- Unrealized P&L (discretized buckets)
- Volatility (low/medium/high)
- Direction (LONG/SHORT)

**Actions:**
- HOLD - Keep position open
- EXIT - Close position

```python
learner = get_exit_value_learner()

# Get exit recommendation
state = learner.discretize_state(
    regime="trending_bull",
    time_in_trade_minutes=45,
    unrealized_pnl_pct=2.5,
    current_volatility=0.015,
    avg_volatility=0.012,
    direction="LONG"
)

recommendation = learner.recommend_action(state, unrealized_pnl=2.5)

if recommendation.action == "exit":
    close_position()
```

### 4. Shadow Mode (`shadow_mode.py`)

Safe testing of new strategies alongside production.

**Workflow:**
1. Deploy component in shadow mode
2. Record both shadow and live decisions
3. Compare performance over time
4. Promote to live if validated

```python
manager = get_shadow_manager()

# Create shadow component
component = manager.create_shadow(
    name="improved_momentum",
    version="v2.1",
    initial_status=ShadowStatus.SHADOW
)

# Record shadow decision
manager.record_shadow_decision(
    component_id=component.component_id,
    context_id="ctx_123",
    decision="ENTER_LONG",
    confidence=0.78,
    expected_outcome=0.05
)

# Compare to live
comparison = manager.get_comparison_summary()

# Promote when validated
if component.promotion_score > 0.7:
    manager.promote_component(component.component_id)
```

### 5. Self-Improvement (`self_improvement.py`)

Autonomous system improvement triggered by drift detection.

**Improvement Phases:**
1. `DETECTING` - Monitoring for drift
2. `ANALYZING` - Analyzing what needs improvement
3. `PROPOSING` - Generating improvement proposal
4. `VALIDATING` - Testing in shadow mode
5. `DEPLOYING` - Rolling out improvement

```python
orchestrator = get_self_improvement_orchestrator()

# Monitor and trigger
cycle = orchestrator.monitor_and_trigger()

if cycle:
    print(f"Improvement triggered: {cycle.trigger}")

# Get status
status = orchestrator.get_status()
print(f"Phase: {status['current_phase']}")
print(f"Cycles completed: {status['total_cycles']}")
```

## API Endpoints

All modules are exposed via REST API:

```
# Control Plane
GET  /api/decision-intelligence/control-plane/status
GET  /api/decision-intelligence/control-plane/health
POST /api/decision-intelligence/control-plane/kill-switch
POST /api/decision-intelligence/control-plane/kill-switch/release

# Decision Trace
GET  /api/decision-intelligence/trace/stats
GET  /api/decision-intelligence/trace/path/{context_id}
GET  /api/decision-intelligence/trace/failure-patterns
GET  /api/decision-intelligence/trace/success-patterns

# Exit Learning
GET  /api/decision-intelligence/exit-learning/stats
POST /api/decision-intelligence/exit-learning/recommend/{position_id}
GET  /api/decision-intelligence/exit-learning/value-surface/{regime}

# Shadow Mode
GET  /api/decision-intelligence/shadow/components
GET  /api/decision-intelligence/shadow/report/{component_id}
GET  /api/decision-intelligence/shadow/comparison
POST /api/decision-intelligence/shadow/promote/{component_id}

# Self-Improvement
GET  /api/decision-intelligence/self-improvement/status
GET  /api/decision-intelligence/self-improvement/history
POST /api/decision-intelligence/self-improvement/trigger
POST /api/decision-intelligence/self-improvement/check-drift
```

## Configuration

Environment variables:

```bash
# Control Plane
DECISION_INTEL_DEFAULT_MODE=shadow  # shadow|paper|live|disabled
DECISION_INTEL_KILL_SWITCH_DEFAULT=false

# Exit Learning
EXIT_LEARNER_ALPHA=0.1          # Learning rate
EXIT_LEARNER_GAMMA=0.95         # Discount factor
EXIT_LEARNER_EXPLORATION=0.1    # ε-greedy exploration

# Shadow Mode
SHADOW_MIN_COMPARISONS=100      # Min comparisons before promotion
SHADOW_MIN_ACCURACY=0.55        # Min accuracy for promotion
SHADOW_MIN_OUTPERFORMANCE=0.02  # Min outperformance rate

# Self-Improvement
IMPROVEMENT_DRIFT_THRESHOLD=0.15    # Drift trigger threshold
IMPROVEMENT_VALIDATION_DAYS=14      # Days to validate
IMPROVEMENT_THRESHOLD=0.05          # Required improvement
```

## Safety Guarantees

1. **Kill Switch** - Instant halt of all AI decisions
2. **Mode Separation** - Clear boundary between shadow/paper/live
3. **Audit Trail** - Every decision traceable via graph
4. **Validation Period** - New strategies must prove themselves
5. **Rollback** - Self-improvement can be reverted

## Integration Example

Full integration with trading loop:

```python
from decision_intelligence import (
    get_control_plane,
    get_exit_value_learner,
)

control_plane = get_control_plane()
exit_learner = get_exit_value_learner()

def trading_loop():
    while True:
        # Check if AI decisions are allowed
        if not control_plane.check_safety():
            logger.warning("AI decisions halted")
            time.sleep(60)
            continue
        
        # Get current context
        context = control_plane.create_context(
            symbol=current_symbol,
            regime=detect_regime(),
            regime_confidence=regime_confidence,
            signal=get_latest_signal()
        )
        
        # Check existing positions for exit
        for position in get_positions():
            recommendation = exit_learner.recommend_action(
                state=get_position_state(position),
                unrealized_pnl=position.unrealized_pnl_pct
            )
            
            if recommendation.action == "exit":
                control_plane.record_decision(
                    context_id=context["context_id"],
                    component="exit_learner",
                    decision="EXIT",
                    reason=recommendation.reason,
                    data=recommendation.to_dict()
                )
                close_position(position)
        
        # Process new signals
        if should_enter(context):
            control_plane.record_decision(
                context_id=context["context_id"],
                component="entry_logic",
                decision="ENTER",
                reason="Signal + regime alignment",
                data={"signal": context["signal"]}
            )
            enter_position(context)
        
        time.sleep(1)
```

## Testing

Run tests:

```bash
pytest tests/decision_intelligence/ -v
```

## License

Proprietary - Internal use only.
