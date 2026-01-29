"""
Shadow Mode Framework
=====================
P1: Unified shadow execution for safe testing of intelligence layers.

Shadow mode allows:
- Running new strategies alongside live without execution
- Comparing shadow decisions to live decisions
- Automatic promotion based on performance
- A/B testing of model changes

All new intelligence layers start in shadow mode.

Rollback Plan: Delete this file, components run independently.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
import sqlite3
import threading

logger = logging.getLogger(__name__)


class ShadowStatus(Enum):
    """Status of a shadow component."""
    SHADOW = "shadow"           # Logging only, no impact
    PARALLEL = "parallel"       # Running alongside live, decisions compared
    CANDIDATE = "candidate"     # Performing well, ready for promotion
    PROMOTED = "promoted"       # Graduated to live
    REJECTED = "rejected"       # Failed tests, won't be promoted


class PromotionCriteria(Enum):
    """Criteria for promoting from shadow to live."""
    PERFORMANCE = "performance"         # Beats current by X%
    CONSISTENCY = "consistency"         # Consistent positive performance
    SAFETY = "safety"                   # No safety violations
    STATISTICAL = "statistical"         # Statistically significant improvement


@dataclass
class ShadowComponent:
    """A component running in shadow mode."""
    component_id: str
    component_name: str
    version: str
    status: ShadowStatus
    created_at: datetime
    
    # Performance tracking
    decisions_count: int = 0
    correct_decisions: int = 0
    total_shadow_pnl: float = 0.0
    
    # Comparison to live
    live_comparison_count: int = 0
    agreed_with_live: int = 0
    outperformed_live: int = 0
    
    # Promotion tracking
    promotion_score: float = 0.0
    promotion_checks_passed: List[str] = field(default_factory=list)
    promotion_checks_failed: List[str] = field(default_factory=list)
    
    # Metadata
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_name": self.component_name,
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "decisions_count": self.decisions_count,
            "correct_decisions": self.correct_decisions,
            "accuracy": self.correct_decisions / self.decisions_count if self.decisions_count > 0 else 0,
            "total_shadow_pnl": self.total_shadow_pnl,
            "live_comparison_count": self.live_comparison_count,
            "agreement_rate": self.agreed_with_live / self.live_comparison_count if self.live_comparison_count > 0 else 0,
            "outperformance_rate": self.outperformed_live / self.live_comparison_count if self.live_comparison_count > 0 else 0,
            "promotion_score": self.promotion_score,
        }


@dataclass
class ShadowDecision:
    """A decision made by a shadow component."""
    decision_id: str
    component_id: str
    timestamp: datetime
    symbol: str
    
    # The decision
    decision_type: str  # 'signal', 'risk', 'exit', etc.
    decision_value: Any  # The actual decision
    confidence: float
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Comparison (filled in later)
    live_decision: Optional[Any] = None
    agreed_with_live: bool = False
    
    # Outcome (filled in later)
    outcome_known: bool = False
    was_correct: bool = False
    shadow_pnl: float = 0.0
    live_pnl: float = 0.0


@dataclass
class PromotionCheck:
    """Result of a promotion criteria check."""
    criteria: PromotionCriteria
    passed: bool
    score: float
    threshold: float
    details: str


class ShadowModeManager:
    """
    Manages shadow mode for all intelligence layers.
    
    Usage:
    1. Register a component with register_shadow_component()
    2. Record decisions with record_shadow_decision()
    3. Compare with live using compare_to_live()
    4. Record outcomes with record_outcome()
    5. Check promotion readiness with check_promotion()
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("decision_intelligence/shadow_mode.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Components registry
        self.components: Dict[str, ShadowComponent] = {}
        
        # Decision buffer (in-memory)
        self.pending_decisions: Dict[str, ShadowDecision] = {}
        
        # Promotion thresholds
        self.promotion_thresholds = {
            PromotionCriteria.PERFORMANCE: 0.1,        # 10% better than live
            PromotionCriteria.CONSISTENCY: 0.6,        # 60% of days positive
            PromotionCriteria.SAFETY: 0.0,             # No safety violations
            PromotionCriteria.STATISTICAL: 0.95,       # 95% confidence
        }
        
        # Minimum samples for promotion
        self.min_decisions_for_promotion = 100
        self.min_days_for_promotion = 7
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize
        self._init_db()
        self._load_components()
        
        logger.info("ShadowModeManager initialized")
    
    def _init_db(self) -> None:
        """Initialize database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS shadow_components (
                    component_id TEXT PRIMARY KEY,
                    component_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decisions_count INTEGER DEFAULT 0,
                    correct_decisions INTEGER DEFAULT 0,
                    total_shadow_pnl REAL DEFAULT 0.0,
                    live_comparison_count INTEGER DEFAULT 0,
                    agreed_with_live INTEGER DEFAULT 0,
                    outperformed_live INTEGER DEFAULT 0,
                    promotion_score REAL DEFAULT 0.0,
                    config_json TEXT
                );
                
                CREATE TABLE IF NOT EXISTS shadow_decisions (
                    decision_id TEXT PRIMARY KEY,
                    component_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT,
                    decision_type TEXT NOT NULL,
                    decision_value_json TEXT,
                    confidence REAL,
                    context_json TEXT,
                    live_decision_json TEXT,
                    agreed_with_live INTEGER,
                    outcome_known INTEGER DEFAULT 0,
                    was_correct INTEGER,
                    shadow_pnl REAL,
                    live_pnl REAL,
                    FOREIGN KEY (component_id) REFERENCES shadow_components(component_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_decisions_component ON shadow_decisions(component_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON shadow_decisions(timestamp);
            """)
    
    def _load_components(self) -> None:
        """Load registered components."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM shadow_components")
                
                for row in cursor.fetchall():
                    component = ShadowComponent(
                        component_id=row[0],
                        component_name=row[1],
                        version=row[2],
                        status=ShadowStatus(row[3]),
                        created_at=datetime.fromisoformat(row[4]),
                        decisions_count=row[5],
                        correct_decisions=row[6],
                        total_shadow_pnl=row[7],
                        live_comparison_count=row[8],
                        agreed_with_live=row[9],
                        outperformed_live=row[10],
                        promotion_score=row[11],
                        config=json.loads(row[12]) if row[12] else {},
                    )
                    self.components[component.component_id] = component
                
                logger.info(f"Loaded {len(self.components)} shadow components")
        except Exception as e:
            logger.error(f"Error loading components: {e}")
    
    # =========================================================================
    # COMPONENT MANAGEMENT
    # =========================================================================
    
    def register_shadow_component(
        self,
        component_name: str,
        version: str,
        config: Dict = None,
    ) -> ShadowComponent:
        """
        Register a new component for shadow mode testing.
        
        Args:
            component_name: Name of the component
            version: Version identifier
            config: Component configuration
        
        Returns:
            Registered ShadowComponent
        """
        component_id = f"{component_name}_{version}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        component = ShadowComponent(
            component_id=component_id,
            component_name=component_name,
            version=version,
            status=ShadowStatus.SHADOW,
            created_at=datetime.now(timezone.utc),
            config=config or {},
        )
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO shadow_components
                (component_id, component_name, version, status, created_at, config_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                component.component_id,
                component.component_name,
                component.version,
                component.status.value,
                component.created_at.isoformat(),
                json.dumps(component.config),
            ))
        
        self.components[component_id] = component
        logger.info(f"Registered shadow component: {component_id}")
        
        return component
    
    def get_component(self, component_id: str) -> Optional[ShadowComponent]:
        """Get a registered component."""
        return self.components.get(component_id)
    
    def list_components(self, status: ShadowStatus = None) -> List[ShadowComponent]:
        """List components, optionally filtered by status."""
        if status:
            return [c for c in self.components.values() if c.status == status]
        return list(self.components.values())
    
    # =========================================================================
    # DECISION RECORDING
    # =========================================================================
    
    def record_shadow_decision(
        self,
        component_id: str,
        decision_type: str,
        decision_value: Any,
        confidence: float,
        symbol: str = None,
        context: Dict = None,
    ) -> str:
        """
        Record a decision made by a shadow component.
        
        Args:
            component_id: Which shadow component made this decision
            decision_type: Type of decision (signal, risk, exit, etc.)
            decision_value: The actual decision value
            confidence: Decision confidence (0-1)
            symbol: Trading symbol if applicable
            context: Additional context
        
        Returns:
            Decision ID
        """
        if component_id not in self.components:
            logger.warning(f"Unknown component: {component_id}")
            return ""
        
        decision_id = f"sd_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        decision = ShadowDecision(
            decision_id=decision_id,
            component_id=component_id,
            timestamp=datetime.now(timezone.utc),
            symbol=symbol or "",
            decision_type=decision_type,
            decision_value=decision_value,
            confidence=confidence,
            context=context or {},
        )
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO shadow_decisions
                (decision_id, component_id, timestamp, symbol, decision_type,
                 decision_value_json, confidence, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.decision_id,
                decision.component_id,
                decision.timestamp.isoformat(),
                decision.symbol,
                decision.decision_type,
                json.dumps(decision.decision_value),
                decision.confidence,
                json.dumps(decision.context),
            ))
        
        # Track in pending for outcome recording
        with self._lock:
            self.pending_decisions[decision_id] = decision
        
        # Update component stats
        component = self.components[component_id]
        component.decisions_count += 1
        self._save_component(component)
        
        return decision_id
    
    def compare_to_live(
        self,
        decision_id: str,
        live_decision: Any,
    ) -> bool:
        """
        Compare a shadow decision to the live decision.
        
        Args:
            decision_id: Shadow decision to compare
            live_decision: What the live system decided
        
        Returns:
            True if decisions agreed
        """
        with self._lock:
            if decision_id not in self.pending_decisions:
                return False
            
            decision = self.pending_decisions[decision_id]
        
        decision.live_decision = live_decision
        decision.agreed_with_live = self._decisions_agree(
            decision.decision_value,
            live_decision,
        )
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE shadow_decisions
                SET live_decision_json = ?, agreed_with_live = ?
                WHERE decision_id = ?
            """, (
                json.dumps(live_decision),
                1 if decision.agreed_with_live else 0,
                decision_id,
            ))
        
        # Update component stats
        component = self.components[decision.component_id]
        component.live_comparison_count += 1
        if decision.agreed_with_live:
            component.agreed_with_live += 1
        self._save_component(component)
        
        return decision.agreed_with_live
    
    def _decisions_agree(self, shadow: Any, live: Any) -> bool:
        """Check if two decisions agree."""
        # Handle different types
        if isinstance(shadow, dict) and isinstance(live, dict):
            # Compare direction for signal decisions
            if "direction" in shadow and "direction" in live:
                return shadow["direction"] == live["direction"]
            # Compare action for exit decisions
            if "action" in shadow and "action" in live:
                return shadow["action"] == live["action"]
        
        # Direct comparison
        return shadow == live
    
    # =========================================================================
    # OUTCOME RECORDING
    # =========================================================================
    
    def record_outcome(
        self,
        decision_id: str,
        was_correct: bool,
        shadow_pnl: float,
        live_pnl: float = None,
    ) -> None:
        """
        Record the outcome of a decision.
        
        Args:
            decision_id: Decision to update
            was_correct: Whether the shadow decision was correct
            shadow_pnl: P&L if shadow decision had been executed
            live_pnl: Actual P&L from live decision
        """
        with self._lock:
            if decision_id not in self.pending_decisions:
                logger.warning(f"Decision not found: {decision_id}")
                return
            
            decision = self.pending_decisions[decision_id]
        
        decision.outcome_known = True
        decision.was_correct = was_correct
        decision.shadow_pnl = shadow_pnl
        decision.live_pnl = live_pnl or 0.0
        
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE shadow_decisions
                SET outcome_known = 1, was_correct = ?, shadow_pnl = ?, live_pnl = ?
                WHERE decision_id = ?
            """, (
                1 if was_correct else 0,
                shadow_pnl,
                live_pnl,
                decision_id,
            ))
        
        # Update component stats
        component = self.components[decision.component_id]
        if was_correct:
            component.correct_decisions += 1
        component.total_shadow_pnl += shadow_pnl
        
        # Check if shadow outperformed
        if live_pnl is not None and shadow_pnl > live_pnl:
            component.outperformed_live += 1
        
        self._save_component(component)
        
        # Clean up pending
        with self._lock:
            del self.pending_decisions[decision_id]
    
    # =========================================================================
    # PROMOTION LOGIC
    # =========================================================================
    
    def check_promotion(self, component_id: str) -> List[PromotionCheck]:
        """
        Check if a component is ready for promotion to live.
        
        Returns list of check results.
        """
        if component_id not in self.components:
            return []
        
        component = self.components[component_id]
        checks = []
        
        # Check minimum sample size
        if component.decisions_count < self.min_decisions_for_promotion:
            checks.append(PromotionCheck(
                criteria=PromotionCriteria.STATISTICAL,
                passed=False,
                score=component.decisions_count / self.min_decisions_for_promotion,
                threshold=1.0,
                details=f"Need {self.min_decisions_for_promotion} decisions, have {component.decisions_count}",
            ))
            return checks
        
        # Check minimum time
        days_active = (datetime.now(timezone.utc) - component.created_at).days
        if days_active < self.min_days_for_promotion:
            checks.append(PromotionCheck(
                criteria=PromotionCriteria.STATISTICAL,
                passed=False,
                score=days_active / self.min_days_for_promotion,
                threshold=1.0,
                details=f"Need {self.min_days_for_promotion} days, active for {days_active}",
            ))
            return checks
        
        # Performance check
        if component.live_comparison_count > 0:
            outperformance_rate = component.outperformed_live / component.live_comparison_count
            checks.append(PromotionCheck(
                criteria=PromotionCriteria.PERFORMANCE,
                passed=outperformance_rate >= self.promotion_thresholds[PromotionCriteria.PERFORMANCE],
                score=outperformance_rate,
                threshold=self.promotion_thresholds[PromotionCriteria.PERFORMANCE],
                details=f"Outperformed live {outperformance_rate:.1%} of the time",
            ))
        
        # Consistency check
        consistency = self._calculate_consistency(component_id)
        checks.append(PromotionCheck(
            criteria=PromotionCriteria.CONSISTENCY,
            passed=consistency >= self.promotion_thresholds[PromotionCriteria.CONSISTENCY],
            score=consistency,
            threshold=self.promotion_thresholds[PromotionCriteria.CONSISTENCY],
            details=f"Positive P&L {consistency:.1%} of days",
        ))
        
        # Safety check
        safety_violations = self._count_safety_violations(component_id)
        checks.append(PromotionCheck(
            criteria=PromotionCriteria.SAFETY,
            passed=safety_violations == 0,
            score=1.0 if safety_violations == 0 else 0.0,
            threshold=0.0,
            details=f"{safety_violations} safety violations",
        ))
        
        # Update component
        component.promotion_checks_passed = [c.criteria.value for c in checks if c.passed]
        component.promotion_checks_failed = [c.criteria.value for c in checks if not c.passed]
        component.promotion_score = sum(c.score for c in checks) / len(checks) if checks else 0
        self._save_component(component)
        
        return checks
    
    def _calculate_consistency(self, component_id: str) -> float:
        """Calculate percentage of days with positive P&L."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DATE(timestamp) as day, SUM(shadow_pnl) as daily_pnl
                FROM shadow_decisions
                WHERE component_id = ? AND outcome_known = 1
                GROUP BY DATE(timestamp)
            """, (component_id,))
            
            days = cursor.fetchall()
            
            if not days:
                return 0.0
            
            positive_days = sum(1 for _, pnl in days if pnl and pnl > 0)
            return positive_days / len(days)
    
    def _count_safety_violations(self, component_id: str) -> int:
        """Count safety violations (e.g., decisions that would have hit stops)."""
        with sqlite3.connect(self.db_path) as conn:
            # Count decisions with large negative P&L
            cursor = conn.execute("""
                SELECT COUNT(*) FROM shadow_decisions
                WHERE component_id = ? AND shadow_pnl < -0.05
            """, (component_id,))
            
            return cursor.fetchone()[0]
    
    def promote_component(self, component_id: str) -> bool:
        """
        Promote a component from shadow to live.
        
        Returns True if promotion successful.
        """
        if component_id not in self.components:
            return False
        
        component = self.components[component_id]
        
        # Run promotion checks
        checks = self.check_promotion(component_id)
        all_passed = all(c.passed for c in checks)
        
        if not all_passed:
            logger.warning(f"Promotion checks failed for {component_id}")
            return False
        
        # Update status
        component.status = ShadowStatus.PROMOTED
        self._save_component(component)
        
        logger.info(f"Component {component_id} promoted to LIVE")
        return True
    
    def reject_component(self, component_id: str, reason: str) -> None:
        """Reject a component from promotion."""
        if component_id not in self.components:
            return
        
        component = self.components[component_id]
        component.status = ShadowStatus.REJECTED
        component.promotion_checks_failed.append(f"Rejected: {reason}")
        self._save_component(component)
        
        logger.info(f"Component {component_id} rejected: {reason}")
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _save_component(self, component: ShadowComponent) -> None:
        """Save component to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE shadow_components
                SET status = ?, decisions_count = ?, correct_decisions = ?,
                    total_shadow_pnl = ?, live_comparison_count = ?,
                    agreed_with_live = ?, outperformed_live = ?, promotion_score = ?
                WHERE component_id = ?
            """, (
                component.status.value,
                component.decisions_count,
                component.correct_decisions,
                component.total_shadow_pnl,
                component.live_comparison_count,
                component.agreed_with_live,
                component.outperformed_live,
                component.promotion_score,
                component.component_id,
            ))
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_shadow_report(self, component_id: str) -> Dict[str, Any]:
        """Get comprehensive report for a shadow component."""
        if component_id not in self.components:
            return {}
        
        component = self.components[component_id]
        checks = self.check_promotion(component_id)
        
        return {
            "component": component.to_dict(),
            "promotion_checks": [
                {
                    "criteria": c.criteria.value,
                    "passed": c.passed,
                    "score": c.score,
                    "threshold": c.threshold,
                    "details": c.details,
                }
                for c in checks
            ],
            "ready_for_promotion": all(c.passed for c in checks),
            "days_active": (datetime.now(timezone.utc) - component.created_at).days,
        }
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """Get summary of shadow vs live performance."""
        summary = {
            "total_components": len(self.components),
            "by_status": defaultdict(int),
            "total_shadow_decisions": 0,
            "total_agreed_with_live": 0,
            "total_outperformed": 0,
            "cumulative_shadow_pnl": 0.0,
        }
        
        for component in self.components.values():
            summary["by_status"][component.status.value] += 1
            summary["total_shadow_decisions"] += component.decisions_count
            summary["total_agreed_with_live"] += component.agreed_with_live
            summary["total_outperformed"] += component.outperformed_live
            summary["cumulative_shadow_pnl"] += component.total_shadow_pnl
        
        summary["by_status"] = dict(summary["by_status"])
        
        return summary


# =============================================================================
# SINGLETON
# =============================================================================

_shadow_manager: Optional[ShadowModeManager] = None


def get_shadow_manager() -> ShadowModeManager:
    """Get or create the ShadowModeManager singleton."""
    global _shadow_manager
    if _shadow_manager is None:
        _shadow_manager = ShadowModeManager()
    return _shadow_manager
