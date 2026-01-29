"""
AI Control Plane
=================
P0 Critical: Central coordinator for all AI decision components.

This is the brain's brain - it orchestrates:
- Regime detection → Strategy selection
- Strategy signals → Risk validation
- Risk approval → Execution
- Execution outcomes → Learning feedback

SHADOW MODE: Enabled by default. Set shadow_mode=False only for live trading.

Rollback Plan: Delete this file, system falls back to independent components.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import json
import threading

logger = logging.getLogger(__name__)


class ControlPlaneMode(Enum):
    """Operating mode of the control plane."""
    SHADOW = "shadow"         # Log decisions but don't execute
    PAPER = "paper"           # Execute on paper trading only
    LIVE = "live"             # Full live trading
    DISABLED = "disabled"     # Completely disabled


class ComponentStatus(Enum):
    """Health status of a component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class ComponentHealth:
    """Health of a registered component."""
    name: str
    status: ComponentStatus
    last_heartbeat: datetime
    error_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class DecisionContext:
    """Context passed through the decision pipeline."""
    context_id: str
    timestamp: datetime
    symbol: str
    
    # Regime context
    regime: str = "unknown"
    regime_confidence: float = 0.0
    
    # Signal context
    signal_direction: Optional[str] = None  # 'LONG', 'SHORT', None
    signal_confidence: float = 0.0
    signal_source: str = ""
    
    # Risk context
    risk_approved: bool = False
    risk_adjusted_size: float = 0.0
    risk_warnings: List[str] = field(default_factory=list)
    
    # Execution context
    execution_allowed: bool = False
    execution_mode: str = "shadow"
    
    # Trace
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_decision(self, component: str, decision: str, reason: str, data: Dict = None):
        """Add a decision to the trace."""
        self.decisions.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "decision": decision,
            "reason": reason,
            "data": data or {},
        })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "regime": self.regime,
            "regime_confidence": self.regime_confidence,
            "signal_direction": self.signal_direction,
            "signal_confidence": self.signal_confidence,
            "signal_source": self.signal_source,
            "risk_approved": self.risk_approved,
            "risk_adjusted_size": self.risk_adjusted_size,
            "risk_warnings": self.risk_warnings,
            "execution_allowed": self.execution_allowed,
            "execution_mode": self.execution_mode,
            "decisions": self.decisions,
        }


@dataclass
class ControlPlaneState:
    """Current state of the control plane."""
    mode: ControlPlaneMode
    is_active: bool
    kill_switch_engaged: bool
    
    # Component health
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    
    # Metrics
    decisions_today: int = 0
    trades_today: int = 0
    shadow_decisions_today: int = 0
    
    # Recent contexts
    recent_contexts: List[str] = field(default_factory=list)  # Last 100 context IDs
    
    # Safety
    last_safety_check: Optional[datetime] = None
    safety_violations: List[str] = field(default_factory=list)


class AIControlPlane:
    """
    Central AI Control Plane.
    
    Coordinates all AI components in a safe, observable manner.
    Default mode is SHADOW - decisions are logged but not executed.
    
    Architecture:
    ```
    ┌─────────────────────────────────────────────────────────────┐
    │                    AI CONTROL PLANE                         │
    │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   │
    │  │ Regime  │ → │Strategy │ → │  Risk   │ → │Execution│   │
    │  │Detector │   │Selector │   │Governor │   │ Engine  │   │
    │  └─────────┘   └─────────┘   └─────────┘   └─────────┘   │
    │       ↓             ↓             ↓             ↓         │
    │  ┌───────────────────────────────────────────────────┐   │
    │  │              DECISION TRACE LOGGER                 │   │
    │  └───────────────────────────────────────────────────┘   │
    │                          ↓                                │
    │  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐  │
    │  │  Feedback   │ ← │   Market     │ ← │   Drift      │  │
    │  │    Loop     │   │   Memory     │   │  Detector    │  │
    │  └─────────────┘   └──────────────┘   └──────────────┘  │
    └─────────────────────────────────────────────────────────────┘
    ```
    """
    
    def __init__(
        self,
        mode: ControlPlaneMode = ControlPlaneMode.SHADOW,
        state_dir: Path = None,
    ):
        self.mode = mode
        self.state_dir = state_dir or Path("decision_intelligence/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.state = ControlPlaneState(
            mode=mode,
            is_active=True,
            kill_switch_engaged=False,
        )
        
        # Component registry
        self._components: Dict[str, Any] = {}
        self._component_callbacks: Dict[str, Callable] = {}
        
        # Decision contexts (in-memory cache)
        self._contexts: Dict[str, DecisionContext] = {}
        self._context_lock = threading.Lock()
        
        # Safety interlocks
        self._safety_checks: List[Callable[[DecisionContext], bool]] = []
        
        # Event callbacks
        self._on_decision: List[Callable] = []
        self._on_safety_violation: List[Callable] = []
        
        # Load persisted state
        self._load_state()
        
        logger.info(f"AIControlPlane initialized in {mode.value} mode")
    
    # =========================================================================
    # CONVENIENCE PROPERTIES
    # =========================================================================
    
    @property
    def is_active(self) -> bool:
        """Check if the control plane is active."""
        return self.state.is_active
    
    @property
    def kill_switch_engaged(self) -> bool:
        """Check if the kill switch is engaged."""
        return self.state.kill_switch_engaged
    
    @property
    def decision_trace(self):
        """Get the decision trace component."""
        return self.get_component("decision_trace")
    
    @property
    def exit_learner(self):
        """Get the exit value learner component."""
        return self.get_component("exit_learner")
    
    @property
    def shadow_manager(self):
        """Get the shadow mode manager component."""
        return self.get_component("shadow_manager")
    
    # =========================================================================
    # COMPONENT REGISTRATION
    # =========================================================================
    
    def register_component(
        self,
        name: str,
        component: Any,
        health_check: Callable[[], ComponentStatus] = None,
    ) -> None:
        """
        Register a component with the control plane.
        
        Args:
            name: Unique component name
            component: The component instance
            health_check: Optional function to check component health
        """
        self._components[name] = component
        if health_check:
            self._component_callbacks[name] = health_check
        
        self.state.components[name] = ComponentHealth(
            name=name,
            status=ComponentStatus.HEALTHY,
            last_heartbeat=datetime.now(timezone.utc),
        )
        
        logger.info(f"Registered component: {name}")
    
    def get_component(self, name: str) -> Optional[Any]:
        """Get a registered component."""
        return self._components.get(name)
    
    # =========================================================================
    # SAFETY INTERLOCKS
    # =========================================================================
    
    def add_safety_check(self, check: Callable[[DecisionContext], bool]) -> None:
        """
        Add a safety interlock check.
        
        The check should return True if safe to proceed, False otherwise.
        """
        self._safety_checks.append(check)
    
    def engage_kill_switch(self, reason: str) -> None:
        """Engage the global kill switch."""
        self.state.kill_switch_engaged = True
        self.state.safety_violations.append(f"{datetime.now().isoformat()}: {reason}")
        
        # Notify kill switch component if registered
        kill_switch = self.get_component("kill_switch")
        if kill_switch:
            kill_switch.activate(reason, triggered_by="ai_control_plane")
        
        logger.critical(f"KILL SWITCH ENGAGED: {reason}")
        
        for callback in self._on_safety_violation:
            try:
                callback(reason)
            except Exception as e:
                logger.error(f"Safety callback error: {e}")
    
    def release_kill_switch(self, reason: str = "Manual release") -> None:
        """Release the kill switch (requires explicit action)."""
        self.state.kill_switch_engaged = False
        logger.warning(f"Kill switch released: {reason}")
    
    def _run_safety_checks(self, context: DecisionContext) -> bool:
        """Run all safety checks."""
        if self.state.kill_switch_engaged:
            context.add_decision(
                "control_plane", "BLOCKED", "Kill switch engaged", {}
            )
            return False
        
        for check in self._safety_checks:
            try:
                if not check(context):
                    context.add_decision(
                        "control_plane", "BLOCKED", "Safety check failed", {}
                    )
                    return False
            except Exception as e:
                logger.error(f"Safety check error: {e}")
                # Fail safe - if check errors, block the action
                return False
        
        return True
    
    # =========================================================================
    # DECISION PIPELINE
    # =========================================================================
    
    def create_context(self, symbol: str) -> DecisionContext:
        """Create a new decision context."""
        context_id = f"ctx_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        context = DecisionContext(
            context_id=context_id,
            timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            execution_mode=self.mode.value,
        )
        
        with self._context_lock:
            self._contexts[context_id] = context
            # Keep last 1000 contexts
            if len(self._contexts) > 1000:
                oldest = list(self._contexts.keys())[0]
                del self._contexts[oldest]
        
        return context
    
    def process_decision(
        self,
        context: DecisionContext,
        market_data: Dict[str, Any] = None,
    ) -> DecisionContext:
        """
        Process a decision through the full pipeline.
        
        Pipeline:
        1. Regime Detection
        2. Strategy Signal Generation
        3. Risk Validation
        4. Execution Decision
        5. Trace Logging
        
        Args:
            context: Decision context
            market_data: Current market data
        
        Returns:
            Updated context with all decisions traced
        """
        market_data = market_data or {}
        
        # Step 0: Safety check
        if not self._run_safety_checks(context):
            return context
        
        # Step 1: Regime Detection
        context = self._detect_regime(context, market_data)
        
        # Step 2: Strategy Signal
        context = self._generate_signal(context, market_data)
        
        # Step 3: Risk Validation
        context = self._validate_risk(context)
        
        # Step 4: Execution Decision
        context = self._decide_execution(context)
        
        # Step 5: Log to trace
        self._log_decision(context)
        
        # Update metrics
        self.state.decisions_today += 1
        if self.mode == ControlPlaneMode.SHADOW:
            self.state.shadow_decisions_today += 1
        
        # Notify callbacks
        for callback in self._on_decision:
            try:
                callback(context)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")
        
        return context
    
    def _detect_regime(
        self,
        context: DecisionContext,
        market_data: Dict[str, Any],
    ) -> DecisionContext:
        """Step 1: Detect market regime."""
        regime_detector = self.get_component("regime_detector")
        
        if regime_detector:
            try:
                result = regime_detector.detect_regime(market_data)
                context.regime = result.current_state.regime.value
                context.regime_confidence = result.current_state.confidence
                
                context.add_decision(
                    "regime_detector",
                    f"REGIME:{context.regime}",
                    f"Detected with {context.regime_confidence:.1%} confidence",
                    {"regime": context.regime, "confidence": context.regime_confidence},
                )
            except Exception as e:
                logger.error(f"Regime detection error: {e}")
                context.regime = "unknown"
                context.add_decision("regime_detector", "ERROR", str(e), {})
        else:
            context.regime = "unknown"
            context.add_decision("regime_detector", "SKIP", "Component not registered", {})
        
        return context
    
    def _generate_signal(
        self,
        context: DecisionContext,
        market_data: Dict[str, Any],
    ) -> DecisionContext:
        """Step 2: Generate trading signal."""
        # Try multiple signal sources
        signal_sources = ["trading_brain", "strategy_orchestrator", "algo_bot"]
        
        for source_name in signal_sources:
            source = self.get_component(source_name)
            if source and hasattr(source, "generate_signal"):
                try:
                    signal = source.generate_signal(
                        symbol=context.symbol,
                        regime=context.regime,
                        market_data=market_data,
                    )
                    
                    if signal and signal.get("direction"):
                        context.signal_direction = signal["direction"]
                        context.signal_confidence = signal.get("confidence", 0.5)
                        context.signal_source = source_name
                        
                        context.add_decision(
                            source_name,
                            f"SIGNAL:{context.signal_direction}",
                            f"Confidence {context.signal_confidence:.1%}",
                            signal,
                        )
                        return context
                except Exception as e:
                    logger.error(f"Signal generation error from {source_name}: {e}")
        
        context.add_decision("signal", "NO_SIGNAL", "No signal generated", {})
        return context
    
    def _validate_risk(self, context: DecisionContext) -> DecisionContext:
        """Step 3: Validate with risk governor."""
        if not context.signal_direction:
            context.risk_approved = False
            return context
        
        risk_engine = self.get_component("risk_engine")
        kill_switch = self.get_component("kill_switch")
        
        # Check kill switch first
        if kill_switch and kill_switch.check():
            context.risk_approved = False
            context.add_decision(
                "kill_switch", "BLOCKED", "Kill switch is active", {}
            )
            return context
        
        # Check with risk engine
        if risk_engine:
            try:
                result = risk_engine.check_trade(
                    ticker=context.symbol,
                    direction=context.signal_direction,
                    size_pct=0.05,  # Default size, will be adjusted
                    confidence=context.signal_confidence,
                )
                
                context.risk_approved = result.approved
                context.risk_adjusted_size = result.adjusted_size_pct
                context.risk_warnings = result.warnings
                
                context.add_decision(
                    "risk_engine",
                    "APPROVED" if result.approved else "REJECTED",
                    result.reason,
                    result.to_dict(),
                )
            except Exception as e:
                logger.error(f"Risk validation error: {e}")
                context.risk_approved = False
                context.add_decision("risk_engine", "ERROR", str(e), {})
        else:
            # No risk engine - default approve in shadow mode only
            if self.mode == ControlPlaneMode.SHADOW:
                context.risk_approved = True
                context.risk_adjusted_size = 0.05
                context.add_decision(
                    "risk_engine", "DEFAULT_APPROVE", "Shadow mode default", {}
                )
            else:
                context.risk_approved = False
                context.add_decision(
                    "risk_engine", "REJECTED", "No risk engine in live mode", {}
                )
        
        return context
    
    def _decide_execution(self, context: DecisionContext) -> DecisionContext:
        """Step 4: Final execution decision."""
        if not context.risk_approved:
            context.execution_allowed = False
            context.add_decision(
                "control_plane", "NO_EXECUTE", "Risk not approved", {}
            )
            return context
        
        # Mode-based execution decision
        if self.mode == ControlPlaneMode.SHADOW:
            context.execution_allowed = False
            context.execution_mode = "shadow"
            context.add_decision(
                "control_plane", "SHADOW_ONLY", "Shadow mode - logged only", {}
            )
        elif self.mode == ControlPlaneMode.PAPER:
            context.execution_allowed = True
            context.execution_mode = "paper"
            context.add_decision(
                "control_plane", "PAPER_EXECUTE", "Paper trading execution", {}
            )
        elif self.mode == ControlPlaneMode.LIVE:
            context.execution_allowed = True
            context.execution_mode = "live"
            context.add_decision(
                "control_plane", "LIVE_EXECUTE", "Live trading execution", {}
            )
        else:
            context.execution_allowed = False
            context.add_decision(
                "control_plane", "DISABLED", "Control plane disabled", {}
            )
        
        return context
    
    def _log_decision(self, context: DecisionContext) -> None:
        """Log decision to trace store."""
        trace_logger = self.get_component("decision_trace")
        
        if trace_logger:
            try:
                trace_logger.log_context(context)
            except Exception as e:
                logger.error(f"Trace logging error: {e}")
        
        # Also log to file
        trace_file = self.state_dir / "decision_trace.jsonl"
        try:
            with open(trace_file, "a") as f:
                f.write(json.dumps(context.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"File trace logging error: {e}")
    
    # =========================================================================
    # FEEDBACK INTEGRATION
    # =========================================================================
    
    def record_outcome(
        self,
        context_id: str,
        outcome: str,
        pnl: float,
        metadata: Dict = None,
    ) -> None:
        """
        Record the outcome of a decision for feedback learning.
        
        Args:
            context_id: The context that led to this outcome
            outcome: 'win', 'loss', 'breakeven'
            pnl: Realized P&L
            metadata: Additional outcome data
        """
        feedback_loop = self.get_component("feedback_loop")
        market_memory = self.get_component("market_memory")
        
        # Get original context
        context = self._contexts.get(context_id)
        
        if feedback_loop:
            try:
                # Create trade result for feedback
                from backend.brain.feedback_loop import TradeResult, TradeOutcome
                
                result = TradeResult(
                    trade_id=context_id,
                    symbol=context.symbol if context else "unknown",
                    direction=context.signal_direction if context else "unknown",
                    entry_price=metadata.get("entry_price", 0) if metadata else 0,
                    exit_price=metadata.get("exit_price", 0) if metadata else 0,
                    entry_time=context.timestamp if context else datetime.now(timezone.utc),
                    exit_time=datetime.now(timezone.utc),
                    quantity=metadata.get("quantity", 0) if metadata else 0,
                    pnl=pnl,
                    pnl_pct=metadata.get("pnl_pct", 0) if metadata else 0,
                    outcome=TradeOutcome(outcome),
                    strategy=context.signal_source if context else "unknown",
                    signal_confidence=context.signal_confidence if context else 0,
                    regime_at_entry=context.regime if context else "unknown",
                )
                
                feedback_loop.record_trade(result)
                logger.info(f"Outcome recorded for {context_id}: {outcome}, PnL=${pnl:.2f}")
            except Exception as e:
                logger.error(f"Feedback recording error: {e}")
        
        if market_memory and context:
            try:
                # Store as market episode
                from backend.core.market_memory import MarketEpisode
                
                episode = MarketEpisode(
                    episode_id=context_id,
                    timestamp=context.timestamp,
                    episode_type="trade",
                    symbol=context.symbol,
                    timeframe="intraday",
                    regime=context.regime,
                    volatility=0.0,
                    trend_strength=0.0,
                    price_at_start=metadata.get("entry_price", 0) if metadata else 0,
                    price_at_end=metadata.get("exit_price", 0) if metadata else 0,
                    price_change_pct=metadata.get("pnl_pct", 0) if metadata else 0,
                    duration_bars=metadata.get("duration_bars", 0) if metadata else 0,
                    outcome=outcome,
                    pnl_impact=pnl,
                )
                
                market_memory.store_episode(episode)
            except Exception as e:
                logger.error(f"Memory storage error: {e}")
    
    # =========================================================================
    # HEALTH & MONITORING
    # =========================================================================
    
    def check_health(self) -> Dict[str, Any]:
        """Check health of all components."""
        health_report = {
            "control_plane": {
                "mode": self.mode.value,
                "is_active": self.state.is_active,
                "kill_switch_engaged": self.state.kill_switch_engaged,
            },
            "components": {},
            "overall_status": "healthy",
        }
        
        unhealthy_count = 0
        
        for name, callback in self._component_callbacks.items():
            try:
                status = callback()
                self.state.components[name].status = status
                self.state.components[name].last_heartbeat = datetime.now(timezone.utc)
                
                health_report["components"][name] = {
                    "status": status.value,
                    "last_heartbeat": self.state.components[name].last_heartbeat.isoformat(),
                }
                
                if status in [ComponentStatus.UNHEALTHY, ComponentStatus.OFFLINE]:
                    unhealthy_count += 1
            except Exception as e:
                self.state.components[name].status = ComponentStatus.UNHEALTHY
                self.state.components[name].last_error = str(e)
                self.state.components[name].error_count += 1
                unhealthy_count += 1
                
                health_report["components"][name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        
        # Determine overall status
        if self.state.kill_switch_engaged:
            health_report["overall_status"] = "kill_switch_engaged"
        elif unhealthy_count > len(self._component_callbacks) / 2:
            health_report["overall_status"] = "degraded"
        elif unhealthy_count > 0:
            health_report["overall_status"] = "partial"
        
        self.state.last_safety_check = datetime.now(timezone.utc)
        
        return health_report
    
    def get_status(self) -> Dict[str, Any]:
        """Get current control plane status."""
        return {
            "mode": self.mode.value,
            "is_active": self.state.is_active,
            "kill_switch_engaged": self.state.kill_switch_engaged,
            "decisions_today": self.state.decisions_today,
            "trades_today": self.state.trades_today,
            "shadow_decisions_today": self.state.shadow_decisions_today,
            "components_registered": list(self._components.keys()),
            "safety_checks_count": len(self._safety_checks),
            "contexts_cached": len(self._contexts),
        }
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _load_state(self) -> None:
        """Load persisted state."""
        state_file = self.state_dir / "control_plane_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                
                # Restore critical state
                if data.get("kill_switch_engaged"):
                    self.state.kill_switch_engaged = True
                    logger.warning("Kill switch was engaged - maintaining state")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
    
    def _save_state(self) -> None:
        """Save state to disk."""
        state_file = self.state_dir / "control_plane_state.json"
        try:
            data = {
                "mode": self.mode.value,
                "kill_switch_engaged": self.state.kill_switch_engaged,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def reset_daily(self) -> None:
        """Reset daily counters."""
        self.state.decisions_today = 0
        self.state.trades_today = 0
        self.state.shadow_decisions_today = 0
        logger.info("Daily counters reset")
    
    def set_mode(self, mode: ControlPlaneMode) -> None:
        """
        Set the control plane mode.
        
        Args:
            mode: The new mode to set
        """
        old_mode = self.mode
        self.mode = mode
        self.state.mode = mode
        
        # Update is_active based on mode
        self.state.is_active = mode in (
            ControlPlaneMode.LIVE,
            ControlPlaneMode.PAPER,
        )
        
        logger.info(f"Control plane mode changed: {old_mode.value} -> {mode.value}")
        self._save_state()
    
    def _reset_for_testing(self) -> None:
        """
        Reset the control plane state for testing.
        Clears all state and components.
        """
        self.state = ControlPlaneState(
            mode=self.mode,
            is_active=self.mode in (ControlPlaneMode.LIVE, ControlPlaneMode.PAPER),
            kill_switch_engaged=False,
        )
        self._components.clear()
        self._component_callbacks.clear()
        self._contexts.clear()
        self._safety_checks.clear()
        self._on_decision.clear()
        self._on_safety_violation.clear()
        logger.info("Control plane reset for testing")


# =============================================================================
# SINGLETON
# =============================================================================

_control_plane: Optional[AIControlPlane] = None


def get_control_plane(
    mode: ControlPlaneMode = ControlPlaneMode.SHADOW,
) -> AIControlPlane:
    """Get or create the AI Control Plane singleton."""
    global _control_plane
    if _control_plane is None:
        _control_plane = AIControlPlane(mode=mode)
    return _control_plane


def reset_control_plane() -> None:
    """Reset the control plane (for testing)."""
    global _control_plane
    _control_plane = None
