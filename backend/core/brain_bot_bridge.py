"""
Brain-to-Bot Bridge
===================
P0 Critical Feature: Connects ML Brain to Algo Bot execution.

Implements exact parity with quant-platform/core/brain_bot_bridge.py

The ML Brain is the "playground" where:
- Models train and experiment
- Strategies are tested
- Hyperparameters tuned
- Ensemble weights optimized

The Algo Bot is the "execution" where:
- Trades happen in real-time
- Money is on the line
- Latency matters
- Safety is critical

This bridge ensures:
1. Learning updates flow from Brain -> Bot
2. Bot execution results flow back to Brain
3. All updates are validated before deployment
4. Rollback capability if new model fails
"""
import hashlib
import json
import logging
import os
import pickle
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple

logger = logging.getLogger("BRAIN_BOT_BRIDGE")


class DeploymentStage(Enum):
    """
    Stages in the deployment pipeline.
    Matches quant-platform exactly.
    """
    TRAINING = "training"           # Model training in Brain
    VALIDATION = "validation"       # Offline validation
    SHADOW = "shadow"               # Shadow mode (parallel, no trades)
    CANARY = "canary"               # Small % of traffic
    PRODUCTION = "production"       # Full production
    ROLLBACK = "rollback"           # Rolling back


class ModelHealth(Enum):
    """
    Health status of deployed model.
    Matches quant-platform exactly.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DeploymentRecord:
    """
    Record of a model deployment.
    Matches quant-platform exactly.
    """
    deployment_id: str
    model_id: str
    model_version: str
    stage: DeploymentStage
    deployed_at: datetime

    # Validation results
    offline_validation_score: float = 0.0
    shadow_validation_score: float = 0.0
    canary_validation_score: float = 0.0

    # Production metrics
    production_trades: int = 0
    production_pnl: float = 0.0
    production_win_rate: float = 0.0

    # Health
    health: ModelHealth = ModelHealth.UNKNOWN
    health_checks_passed: int = 0
    health_checks_failed: int = 0

    # Rollback info
    previous_deployment_id: Optional[str] = None
    rolled_back_at: Optional[datetime] = None
    rollback_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        d["health"] = self.health.value
        d["deployed_at"] = self.deployed_at.isoformat()
        if self.rolled_back_at:
            d["rolled_back_at"] = self.rolled_back_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeploymentRecord":
        data["stage"] = DeploymentStage(data["stage"])
        data["health"] = ModelHealth(data["health"])
        data["deployed_at"] = datetime.fromisoformat(data["deployed_at"])
        if data.get("rolled_back_at"):
            data["rolled_back_at"] = datetime.fromisoformat(data["rolled_back_at"])
        return cls(**data)


@dataclass
class ExecutionFeedback:
    """
    Feedback from Bot execution back to Brain.
    Matches quant-platform exactly.
    """
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

    # Features at time of trade (for replay)
    features: Dict[str, float] = field(default_factory=dict)

    # Market conditions
    regime: str = "unknown"
    volatility: float = 0.0
    spread: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class BrainToBotBridge:
    """
    Bridge between ML Brain (training) and Algo Bot (execution).

    Flow:
        ML Brain                     Bridge                      Algo Bot
        ========                     ======                      ========

        train() ──────────────────→ validate() ──────────────→ load_model()
                                        │
        retrain() ←────────────────── analyze() ←─────────────── feedback()

    Features:
    - Staged deployment (shadow -> canary -> production)
    - Health monitoring
    - Automatic rollback
    - Feedback loop for continuous learning
    """

    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or Path("models")
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Current deployment
        self.current_deployment: Optional[DeploymentRecord] = None
        self.previous_deployment: Optional[DeploymentRecord] = None

        # Deployment history
        self.deployment_history: List[DeploymentRecord] = []

        # Feedback buffer
        self.feedback_buffer: List[ExecutionFeedback] = []
        self.max_feedback_buffer: int = 1000

        # Health thresholds (match platform)
        self.health_thresholds = {
            "healthy": {
                "win_rate_min": 0.50,
                "sharpe_min": 1.0,
                "max_drawdown_max": 0.15,
                "consecutive_losses_max": 5,
                "latency_max_ms": 100,
            },
            "degraded": {
                "win_rate_min": 0.40,
                "sharpe_min": 0.5,
                "max_drawdown_max": 0.20,
            },
        }

        # Stage requirements
        self.stage_requirements = {
            DeploymentStage.VALIDATION: {"min_duration_hours": 24},
            DeploymentStage.SHADOW: {"min_duration_hours": 72},
            DeploymentStage.CANARY: {"min_duration_hours": 48},
        }

        # Callbacks
        self._on_deployment: List[Callable] = []
        self._on_rollback: List[Callable] = []

        # Load state
        self._load_state()

        logger.info("BrainToBotBridge initialized")

    def _load_state(self) -> None:
        """Load persisted state."""
        state_file = self.state_dir / "bridge_state.json"
        try:
            if state_file.exists():
                with open(state_file) as f:
                    data = json.load(f)

                if data.get("current_deployment"):
                    self.current_deployment = DeploymentRecord.from_dict(
                        data["current_deployment"]
                    )

                if data.get("previous_deployment"):
                    self.previous_deployment = DeploymentRecord.from_dict(
                        data["previous_deployment"]
                    )

                self.deployment_history = [
                    DeploymentRecord.from_dict(d)
                    for d in data.get("deployment_history", [])
                ]
        except Exception as e:
            logger.error(f"Error loading bridge state: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        state_file = self.state_dir / "bridge_state.json"
        try:
            data = {
                "current_deployment": (
                    self.current_deployment.to_dict()
                    if self.current_deployment else None
                ),
                "previous_deployment": (
                    self.previous_deployment.to_dict()
                    if self.previous_deployment else None
                ),
                "deployment_history": [
                    d.to_dict() for d in self.deployment_history[-50:]
                ],
                "updated": datetime.now().isoformat(),
            }
            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving bridge state: {e}")

    def register_on_deployment(self, callback: Callable) -> None:
        """Register callback for deployment events."""
        self._on_deployment.append(callback)

    def register_on_rollback(self, callback: Callable) -> None:
        """Register callback for rollback events."""
        self._on_rollback.append(callback)

    def start_deployment(
        self,
        model_id: str,
        model_version: str,
        validation_score: float,
    ) -> DeploymentRecord:
        """
        Start a new model deployment.

        Args:
            model_id: Unique model identifier
            model_version: Version string
            validation_score: Offline validation score

        Returns:
            New deployment record in VALIDATION stage
        """
        deployment_id = f"dep_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        record = DeploymentRecord(
            deployment_id=deployment_id,
            model_id=model_id,
            model_version=model_version,
            stage=DeploymentStage.VALIDATION,
            deployed_at=datetime.now(),
            offline_validation_score=validation_score,
            previous_deployment_id=(
                self.current_deployment.deployment_id
                if self.current_deployment else None
            ),
        )

        self.deployment_history.append(record)
        self._save_state()

        logger.info(
            f"Deployment started: {deployment_id} ({model_id} v{model_version})"
        )

        return record

    def promote_stage(self, deployment_id: str) -> Tuple[bool, str]:
        """
        Promote deployment to next stage.

        Stage progression: VALIDATION -> SHADOW -> CANARY -> PRODUCTION

        Args:
            deployment_id: Deployment to promote

        Returns:
            (success, message)
        """
        record = self._find_deployment(deployment_id)
        if not record:
            return False, f"Deployment not found: {deployment_id}"

        current_stage = record.stage
        next_stage = self._get_next_stage(current_stage)

        if next_stage is None:
            return False, f"Cannot promote from {current_stage.value}"

        # Check requirements
        if current_stage in self.stage_requirements:
            req = self.stage_requirements[current_stage]
            elapsed = datetime.now() - record.deployed_at
            min_hours = req.get("min_duration_hours", 0)
            if elapsed < timedelta(hours=min_hours):
                return False, f"Minimum {min_hours}h required in {current_stage.value}"

        # Promote
        record.stage = next_stage

        # If promoting to production, update current deployment
        if next_stage == DeploymentStage.PRODUCTION:
            self.previous_deployment = self.current_deployment
            self.current_deployment = record
            record.health = ModelHealth.UNKNOWN

            # Notify callbacks
            for callback in self._on_deployment:
                try:
                    callback(record)
                except Exception as e:
                    logger.error(f"Deployment callback error: {e}")

        self._save_state()
        logger.info(f"Deployment {deployment_id} promoted to {next_stage.value}")

        return True, f"Promoted to {next_stage.value}"

    def _get_next_stage(self, current: DeploymentStage) -> Optional[DeploymentStage]:
        """Get next stage in deployment pipeline."""
        progression = {
            DeploymentStage.TRAINING: DeploymentStage.VALIDATION,
            DeploymentStage.VALIDATION: DeploymentStage.SHADOW,
            DeploymentStage.SHADOW: DeploymentStage.CANARY,
            DeploymentStage.CANARY: DeploymentStage.PRODUCTION,
        }
        return progression.get(current)

    def _find_deployment(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Find deployment by ID."""
        for record in reversed(self.deployment_history):
            if record.deployment_id == deployment_id:
                return record
        return None

    def rollback(self, reason: str) -> Tuple[bool, str]:
        """
        Rollback to previous deployment.

        Args:
            reason: Why rollback is needed

        Returns:
            (success, message)
        """
        if not self.previous_deployment:
            return False, "No previous deployment to rollback to"

        if not self.current_deployment:
            return False, "No current deployment to rollback from"

        # Record rollback
        self.current_deployment.stage = DeploymentStage.ROLLBACK
        self.current_deployment.rolled_back_at = datetime.now()
        self.current_deployment.rollback_reason = reason

        # Restore previous
        old_current = self.current_deployment
        self.current_deployment = self.previous_deployment
        self.current_deployment.stage = DeploymentStage.PRODUCTION
        self.previous_deployment = None

        self._save_state()

        logger.warning(
            f"ROLLBACK: {old_current.deployment_id} -> {self.current_deployment.deployment_id} "
            f"Reason: {reason}"
        )

        # Notify callbacks
        for callback in self._on_rollback:
            try:
                callback(old_current, self.current_deployment, reason)
            except Exception as e:
                logger.error(f"Rollback callback error: {e}")

        return True, f"Rolled back to {self.current_deployment.deployment_id}"

    def receive_feedback(self, feedback: ExecutionFeedback) -> None:
        """
        Receive execution feedback from bot.

        Args:
            feedback: Execution feedback record
        """
        self.feedback_buffer.append(feedback)

        # Trim buffer if needed
        if len(self.feedback_buffer) > self.max_feedback_buffer:
            self.feedback_buffer = self.feedback_buffer[-self.max_feedback_buffer:]

        # Update deployment metrics if this is current model
        if (
            self.current_deployment
            and feedback.model_id == self.current_deployment.model_id
        ):
            self.current_deployment.production_trades += 1
            self.current_deployment.production_pnl += feedback.pnl

            # Update win rate
            wins = sum(1 for f in self.feedback_buffer if f.pnl > 0)
            total = len(self.feedback_buffer)
            if total > 0:
                self.current_deployment.production_win_rate = wins / total

    def check_health(self) -> ModelHealth:
        """
        Check health of current deployment.

        Returns:
            Current health status
        """
        if not self.current_deployment:
            return ModelHealth.UNKNOWN

        # Get recent feedback
        recent = [
            f for f in self.feedback_buffer[-100:]
            if f.model_id == self.current_deployment.model_id
        ]

        if len(recent) < 10:
            return ModelHealth.UNKNOWN

        # Calculate metrics
        wins = sum(1 for f in recent if f.pnl > 0)
        win_rate = wins / len(recent)

        total_pnl = sum(f.pnl for f in recent)
        avg_latency = sum(f.execution_latency_ms for f in recent) / len(recent)

        # Check consecutive losses
        consecutive_losses = 0
        for f in reversed(recent):
            if f.pnl < 0:
                consecutive_losses += 1
            else:
                break

        # Determine health
        healthy = self.health_thresholds["healthy"]
        degraded = self.health_thresholds["degraded"]

        if (
            win_rate >= healthy["win_rate_min"]
            and consecutive_losses <= healthy["consecutive_losses_max"]
            and avg_latency <= healthy["latency_max_ms"]
        ):
            health = ModelHealth.HEALTHY
            self.current_deployment.health_checks_passed += 1
        elif (
            win_rate >= degraded["win_rate_min"]
        ):
            health = ModelHealth.DEGRADED
            self.current_deployment.health_checks_passed += 1
        else:
            health = ModelHealth.UNHEALTHY
            self.current_deployment.health_checks_failed += 1

        self.current_deployment.health = health
        self._save_state()

        # Auto-rollback if unhealthy
        if health == ModelHealth.UNHEALTHY:
            if self.current_deployment.health_checks_failed >= 3:
                self.rollback(f"Auto-rollback: {health.value}")

        return health

    def get_status(self) -> Dict[str, Any]:
        """Get bridge status."""
        return {
            "current_deployment": (
                self.current_deployment.to_dict()
                if self.current_deployment else None
            ),
            "previous_deployment": (
                self.previous_deployment.to_dict()
                if self.previous_deployment else None
            ),
            "feedback_buffer_size": len(self.feedback_buffer),
            "deployment_history_count": len(self.deployment_history),
            "health_thresholds": self.health_thresholds,
        }


# Singleton instance
_brain_bot_bridge: Optional[BrainToBotBridge] = None


def get_brain_bot_bridge() -> BrainToBotBridge:
    """Get or create bridge singleton."""
    global _brain_bot_bridge
    if _brain_bot_bridge is None:
        _brain_bot_bridge = BrainToBotBridge()
    return _brain_bot_bridge
