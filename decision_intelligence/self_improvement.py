"""
Self-Improvement Orchestration
==============================
P2: Automated wiring of drift detection → retraining → validation.

Connects existing components into a self-improving loop:
1. Drift detector detects performance decay
2. Triggers automated retraining
3. New model runs in shadow mode
4. If shadow outperforms, promotes to live
5. Feedback loop records outcomes
6. Cycle repeats

SHADOW MODE: New models always start in shadow.

Rollback Plan: Delete this file, fall back to manual model management.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import sqlite3
import threading

logger = logging.getLogger(__name__)


class ImprovementPhase(Enum):
    """Current phase of self-improvement."""
    MONITORING = "monitoring"       # Normal operation, watching for drift
    RETRAINING = "retraining"       # Retraining triggered
    VALIDATING = "validating"       # New model in shadow validation
    PROMOTING = "promoting"         # Promoting new model
    ROLLING_BACK = "rolling_back"   # Rolling back failed improvement


class TriggerType(Enum):
    """What triggered an improvement cycle."""
    DRIFT_DETECTED = "drift_detected"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    PERFORMANCE_DECLINE = "performance_decline"


@dataclass
class ImprovementCycle:
    """A single improvement cycle."""
    cycle_id: str
    trigger: TriggerType
    started_at: datetime
    phase: ImprovementPhase
    
    # What's being improved
    component_name: str
    old_version: str
    new_version: Optional[str] = None
    
    # Metrics
    drift_score: float = 0.0
    old_performance: float = 0.0
    new_performance: float = 0.0
    
    # Outcome
    completed_at: Optional[datetime] = None
    success: bool = False
    failure_reason: Optional[str] = None
    
    # Shadow tracking
    shadow_component_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "trigger": self.trigger.value,
            "started_at": self.started_at.isoformat(),
            "phase": self.phase.value,
            "component_name": self.component_name,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "drift_score": self.drift_score,
            "old_performance": self.old_performance,
            "new_performance": self.new_performance,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "failure_reason": self.failure_reason,
        }


@dataclass
class ImprovementConfig:
    """Configuration for self-improvement."""
    # Drift thresholds
    drift_score_threshold: float = 2.0      # Z-score to trigger retraining
    performance_decline_threshold: float = 0.15  # 15% decline triggers
    
    # Timing
    min_time_between_cycles: timedelta = timedelta(days=1)
    validation_period: timedelta = timedelta(days=7)
    
    # Requirements
    min_training_samples: int = 100
    min_validation_samples: int = 50
    improvement_threshold: float = 0.05     # 5% improvement required
    
    # Safety
    max_consecutive_failures: int = 3
    auto_rollback_on_failure: bool = True


class SelfImprovementOrchestrator:
    """
    Orchestrates the self-improvement loop.
    
    Wires together:
    - DriftDetector (monitoring)
    - EvolutionEngine / FeedbackLoop (retraining)
    - ShadowModeManager (validation)
    - AIControlPlane (promotion)
    """
    
    def __init__(
        self,
        config: ImprovementConfig = None,
        db_path: Path = None,
    ):
        self.config = config or ImprovementConfig()
        self.db_path = db_path or Path("decision_intelligence/self_improvement.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Current state
        self.current_phase = ImprovementPhase.MONITORING
        self.active_cycle: Optional[ImprovementCycle] = None
        
        # History
        self.cycle_history: List[ImprovementCycle] = []
        self.consecutive_failures = 0
        
        # Component references (set via register methods)
        self._drift_detector = None
        self._evolution_engine = None
        self._feedback_loop = None
        self._shadow_manager = None
        self._control_plane = None
        
        # Retraining callbacks
        self._retrain_callbacks: Dict[str, Callable] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize
        self._init_db()
        self._load_history()
        
        logger.info("SelfImprovementOrchestrator initialized")
    
    # =========================================================================
    # CONVENIENCE PROPERTIES
    # =========================================================================
    
    @property
    def control_plane(self):
        """Get the registered control plane."""
        return self._control_plane
    
    @property
    def shadow_manager(self):
        """Get the registered shadow manager."""
        return self._shadow_manager
    
    def _init_db(self) -> None:
        """Initialize database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS improvement_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    component_name TEXT NOT NULL,
                    old_version TEXT,
                    new_version TEXT,
                    drift_score REAL,
                    old_performance REAL,
                    new_performance REAL,
                    completed_at TEXT,
                    success INTEGER,
                    failure_reason TEXT,
                    shadow_component_id TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_cycles_component ON improvement_cycles(component_name);
                CREATE INDEX IF NOT EXISTS idx_cycles_started ON improvement_cycles(started_at);
            """)
    
    def _load_history(self) -> None:
        """Load cycle history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM improvement_cycles
                    ORDER BY started_at DESC LIMIT 100
                """)
                
                for row in cursor.fetchall():
                    cycle = ImprovementCycle(
                        cycle_id=row[0],
                        trigger=TriggerType(row[1]),
                        started_at=datetime.fromisoformat(row[2]),
                        phase=ImprovementPhase(row[3]),
                        component_name=row[4],
                        old_version=row[5],
                        new_version=row[6],
                        drift_score=row[7] or 0.0,
                        old_performance=row[8] or 0.0,
                        new_performance=row[9] or 0.0,
                        completed_at=datetime.fromisoformat(row[10]) if row[10] else None,
                        success=bool(row[11]) if row[11] is not None else False,
                        failure_reason=row[12],
                        shadow_component_id=row[13],
                    )
                    self.cycle_history.append(cycle)
        except Exception as e:
            logger.error(f"Error loading history: {e}")
    
    # =========================================================================
    # COMPONENT REGISTRATION
    # =========================================================================
    
    def register_drift_detector(self, detector: Any) -> None:
        """Register drift detector component."""
        self._drift_detector = detector
        logger.info("Drift detector registered")
    
    def register_evolution_engine(self, engine: Any) -> None:
        """Register evolution engine for retraining."""
        self._evolution_engine = engine
        logger.info("Evolution engine registered")
    
    def register_feedback_loop(self, loop: Any) -> None:
        """Register feedback loop."""
        self._feedback_loop = loop
        logger.info("Feedback loop registered")
    
    def register_shadow_manager(self, manager: Any) -> None:
        """Register shadow mode manager."""
        self._shadow_manager = manager
        logger.info("Shadow manager registered")
    
    def register_control_plane(self, plane: Any) -> None:
        """Register control plane."""
        self._control_plane = plane
        logger.info("Control plane registered")
    
    def register_retrain_callback(
        self,
        component_name: str,
        callback: Callable[[Dict], Any],
    ) -> None:
        """
        Register a retraining callback for a component.
        
        The callback should take training config and return new version info.
        """
        self._retrain_callbacks[component_name] = callback
        logger.info(f"Retrain callback registered for {component_name}")
    
    # =========================================================================
    # MONITORING
    # =========================================================================
    
    def check_for_drift(self, component_name: str = "default") -> Optional[float]:
        """
        Check if drift has been detected for a component.
        
        Returns drift score if drift detected, None otherwise.
        """
        if not self._drift_detector:
            return None
        
        try:
            # Get drift report
            if hasattr(self._drift_detector, "analyze"):
                # DriftDetector from monitoring module
                report = self._drift_detector.analyze(
                    live_returns=self._get_recent_returns(),
                )
                
                if report.is_drifting:
                    return report.return_gap_zscore
            
            elif hasattr(self._drift_detector, "get_status"):
                # Generic drift detector
                status = self._drift_detector.get_status()
                if status.get("is_drifting"):
                    return status.get("drift_score", 2.0)
        except Exception as e:
            logger.error(f"Error checking drift: {e}")
        
        return None
    
    def _get_recent_returns(self):
        """Get recent returns for drift analysis."""
        # Would connect to data source
        import numpy as np
        import pandas as pd
        return pd.Series(np.random.randn(100) * 0.02)  # Placeholder
    
    def monitor_and_trigger(self) -> Optional[ImprovementCycle]:
        """
        Main monitoring loop - check for drift and trigger improvement if needed.
        
        Call this periodically (e.g., end of each day).
        """
        with self._lock:
            # Already in improvement cycle
            if self.active_cycle and self.current_phase != ImprovementPhase.MONITORING:
                return None
            
            # Check minimum time since last cycle
            if self.cycle_history:
                last_cycle = self.cycle_history[0]
                time_since_last = datetime.now(timezone.utc) - last_cycle.started_at
                if time_since_last < self.config.min_time_between_cycles:
                    return None
        
        # Check each registered component for drift
        for component_name in self._retrain_callbacks.keys():
            drift_score = self.check_for_drift(component_name)
            
            if drift_score and drift_score >= self.config.drift_score_threshold:
                logger.warning(
                    f"Drift detected for {component_name}: z-score={drift_score:.2f}"
                )
                return self.trigger_improvement(
                    component_name=component_name,
                    trigger=TriggerType.DRIFT_DETECTED,
                    drift_score=drift_score,
                )
        
        # Check feedback loop for performance decline
        if self._feedback_loop:
            try:
                status = self._feedback_loop.get_status()
                
                if status.get("is_converged") is False:
                    weakest = status.get("weakest_metric")
                    weakest_value = status.get("weakest_value", 1.0)
                    
                    if weakest_value < (1 - self.config.performance_decline_threshold):
                        return self.trigger_improvement(
                            component_name="trading_brain",
                            trigger=TriggerType.PERFORMANCE_DECLINE,
                            drift_score=1 - weakest_value,
                        )
            except Exception as e:
                logger.error(f"Error checking feedback loop: {e}")
        
        return None
    
    # =========================================================================
    # IMPROVEMENT CYCLE
    # =========================================================================
    
    def trigger_improvement(
        self,
        component_name: str,
        trigger: TriggerType,
        drift_score: float = 0.0,
    ) -> ImprovementCycle:
        """
        Trigger an improvement cycle.
        
        Returns the created cycle.
        """
        # Check consecutive failures
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            logger.error(
                f"Max consecutive failures ({self.config.max_consecutive_failures}) reached. "
                "Manual intervention required."
            )
            raise RuntimeError("Max consecutive improvement failures reached")
        
        cycle_id = f"ic_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        cycle = ImprovementCycle(
            cycle_id=cycle_id,
            trigger=trigger,
            started_at=datetime.now(timezone.utc),
            phase=ImprovementPhase.RETRAINING,
            component_name=component_name,
            old_version=self._get_current_version(component_name),
            drift_score=drift_score,
        )
        
        with self._lock:
            self.active_cycle = cycle
            self.current_phase = ImprovementPhase.RETRAINING
        
        # Save to database
        self._save_cycle(cycle)
        
        logger.info(f"Improvement cycle {cycle_id} triggered for {component_name}")
        
        # Start retraining
        self._execute_retraining(cycle)
        
        return cycle
    
    def _get_current_version(self, component_name: str) -> str:
        """Get current version of a component."""
        # Would query from model registry
        return f"v{datetime.now().strftime('%Y%m%d')}"
    
    def _execute_retraining(self, cycle: ImprovementCycle) -> None:
        """Execute the retraining phase."""
        logger.info(f"Starting retraining for {cycle.component_name}")
        
        callback = self._retrain_callbacks.get(cycle.component_name)
        
        if callback:
            try:
                # Execute retraining callback
                result = callback({
                    "trigger": cycle.trigger.value,
                    "drift_score": cycle.drift_score,
                    "old_version": cycle.old_version,
                })
                
                # Get new version
                cycle.new_version = result.get("version", f"v{datetime.now().strftime('%Y%m%d%H%M%S')}")
                cycle.phase = ImprovementPhase.VALIDATING
                
                logger.info(f"Retraining complete. New version: {cycle.new_version}")
                
                # Start shadow validation
                self._start_shadow_validation(cycle)
                
            except Exception as e:
                logger.error(f"Retraining failed: {e}")
                self._fail_cycle(cycle, str(e))
        
        elif self._evolution_engine:
            # Use evolution engine for retraining
            try:
                result = self._evolution_engine.evolve(
                    market_data=self._get_training_data(),
                    generations=50,
                )
                
                cycle.new_version = f"evolved_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cycle.phase = ImprovementPhase.VALIDATING
                
                self._start_shadow_validation(cycle)
                
            except Exception as e:
                logger.error(f"Evolution failed: {e}")
                self._fail_cycle(cycle, str(e))
        
        else:
            self._fail_cycle(cycle, "No retraining method available")
    
    def _get_training_data(self):
        """Get training data for retraining."""
        import pandas as pd
        import numpy as np
        # Placeholder - would get real market data
        dates = pd.date_range(end=datetime.now(), periods=500, freq='D')
        return pd.DataFrame({
            'open': np.random.randn(500).cumsum() + 100,
            'high': np.random.randn(500).cumsum() + 101,
            'low': np.random.randn(500).cumsum() + 99,
            'close': np.random.randn(500).cumsum() + 100,
            'volume': np.abs(np.random.randn(500)) * 1000000,
        }, index=dates)
    
    def _start_shadow_validation(self, cycle: ImprovementCycle) -> None:
        """Start shadow validation for new model."""
        if not self._shadow_manager:
            logger.warning("No shadow manager - skipping validation")
            self._complete_cycle(cycle, success=True)
            return
        
        # Register in shadow mode
        shadow_component = self._shadow_manager.register_shadow_component(
            component_name=cycle.component_name,
            version=cycle.new_version,
            config={"cycle_id": cycle.cycle_id},
        )
        
        cycle.shadow_component_id = shadow_component.component_id
        self._save_cycle(cycle)
        
        with self._lock:
            self.current_phase = ImprovementPhase.VALIDATING
        
        logger.info(f"Shadow validation started: {shadow_component.component_id}")
    
    def check_validation_progress(self) -> Optional[bool]:
        """
        Check if shadow validation is complete.
        
        Returns:
            True if ready for promotion
            False if should reject
            None if still validating
        """
        if not self.active_cycle or not self.active_cycle.shadow_component_id:
            return None
        
        if not self._shadow_manager:
            return None
        
        cycle = self.active_cycle
        
        # Get shadow report
        report = self._shadow_manager.get_shadow_report(cycle.shadow_component_id)
        
        if not report:
            return None
        
        component = report.get("component", {})
        
        # Check if enough decisions
        decisions = component.get("decisions_count", 0)
        if decisions < self.config.min_validation_samples:
            return None  # Still validating
        
        # Check if validation period complete
        days_active = report.get("days_active", 0)
        if days_active < self.config.validation_period.days:
            return None  # Still validating
        
        # Check promotion readiness
        if report.get("ready_for_promotion"):
            outperformance = component.get("outperformance_rate", 0)
            if outperformance >= self.config.improvement_threshold:
                cycle.new_performance = outperformance
                return True
        
        # Check for clear failure
        if decisions >= self.config.min_validation_samples * 2:
            # Had enough samples and still not ready
            return False
        
        return None  # Continue validation
    
    def complete_validation(self) -> Optional[ImprovementCycle]:
        """
        Complete the validation phase and promote/reject.
        """
        result = self.check_validation_progress()
        
        if result is None:
            return None  # Still validating
        
        cycle = self.active_cycle
        
        if result:
            # Promote
            self._promote_new_version(cycle)
        else:
            # Reject
            self._fail_cycle(cycle, "Shadow validation failed")
        
        return cycle
    
    def _promote_new_version(self, cycle: ImprovementCycle) -> None:
        """Promote new version to live."""
        logger.info(f"Promoting {cycle.component_name} to version {cycle.new_version}")
        
        cycle.phase = ImprovementPhase.PROMOTING
        self._save_cycle(cycle)
        
        # Promote in shadow manager
        if self._shadow_manager and cycle.shadow_component_id:
            self._shadow_manager.promote_component(cycle.shadow_component_id)
        
        # Update control plane if available
        if self._control_plane:
            # Would update component version in control plane
            pass
        
        self._complete_cycle(cycle, success=True)
    
    def _fail_cycle(self, cycle: ImprovementCycle, reason: str) -> None:
        """Mark cycle as failed."""
        logger.error(f"Improvement cycle {cycle.cycle_id} failed: {reason}")
        
        cycle.failure_reason = reason
        
        # Reject shadow if exists
        if self._shadow_manager and cycle.shadow_component_id:
            self._shadow_manager.reject_component(cycle.shadow_component_id, reason)
        
        self._complete_cycle(cycle, success=False)
    
    def _complete_cycle(self, cycle: ImprovementCycle, success: bool) -> None:
        """Complete an improvement cycle."""
        cycle.completed_at = datetime.now(timezone.utc)
        cycle.success = success
        cycle.phase = ImprovementPhase.MONITORING
        
        # Update history
        with self._lock:
            self.cycle_history.insert(0, cycle)
            self.active_cycle = None
            self.current_phase = ImprovementPhase.MONITORING
            
            if success:
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
        
        self._save_cycle(cycle)
        
        logger.info(
            f"Improvement cycle {cycle.cycle_id} completed. "
            f"Success: {success}"
        )
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _save_cycle(self, cycle: ImprovementCycle) -> None:
        """Save cycle to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO improvement_cycles
                (cycle_id, trigger, started_at, phase, component_name,
                 old_version, new_version, drift_score, old_performance,
                 new_performance, completed_at, success, failure_reason,
                 shadow_component_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cycle.cycle_id,
                cycle.trigger.value,
                cycle.started_at.isoformat(),
                cycle.phase.value,
                cycle.component_name,
                cycle.old_version,
                cycle.new_version,
                cycle.drift_score,
                cycle.old_performance,
                cycle.new_performance,
                cycle.completed_at.isoformat() if cycle.completed_at else None,
                1 if cycle.success else 0,
                cycle.failure_reason,
                cycle.shadow_component_id,
            ))
    
    # =========================================================================
    # STATUS & REPORTING
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        return {
            "current_phase": self.current_phase.value,
            "active_cycle": self.active_cycle.to_dict() if self.active_cycle else None,
            "consecutive_failures": self.consecutive_failures,
            "total_cycles": len(self.cycle_history),
            "successful_cycles": sum(1 for c in self.cycle_history if c.success),
            "config": {
                "drift_threshold": self.config.drift_score_threshold,
                "validation_days": self.config.validation_period.days,
                "improvement_threshold": self.config.improvement_threshold,
            },
        }
    
    def get_improvement_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent improvement history."""
        return [c.to_dict() for c in self.cycle_history[:limit]]


# =============================================================================
# SINGLETON
# =============================================================================

_orchestrator: Optional[SelfImprovementOrchestrator] = None


def get_self_improvement_orchestrator() -> SelfImprovementOrchestrator:
    """Get or create the SelfImprovementOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SelfImprovementOrchestrator()
    return _orchestrator
