"""
QUANT INDUSTRY - PropFirm Brain V6
===================================
Next-generation ML/RL/DL trading brain for prop firm evaluations.
Surpasses V5 with:
- Multi-head attention transformer architecture
- PPO-based reinforcement learning agent
- Real-time continuous training
- Bayesian regime detection
- 20+ strategy ensemble with dynamic weighting

Author: QUANT INDUSTRY AI Team
Version: 6.0.0
"""

import hashlib
import json
import logging
import math
import platform
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Deep Learning imports
try:
    import torch
    import torch.nn.functional as F
    from torch import nn
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Technical Analysis
try:
    import pandas_ta as ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

# SVM for regime classification and signal generation
try:
    from sklearn.svm import SVC, NuSVR
    from sklearn.preprocessing import RobustScaler
    from sklearn.feature_selection import SelectKBest, f_classif
    import joblib
    SVM_AVAILABLE = True
except ImportError:
    SVM_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

@dataclass(frozen=True)
class PropFirmRuleset:
    """Immutable prop firm rules - NEVER violate"""
    name: str
    account_size: float
    profit_target: float
    daily_loss_limit: float
    trailing_drawdown: float
    max_contracts: int
    consistency_pct: float = 0.50
    min_trading_days: int = 5
    trading_start: str = "09:30"
    trading_end: str = "17:00"
    flatten_time: str = "16:45"

# Pre-defined rulesets
TPT_50K = PropFirmRuleset(
    name="TPT_50K",
    account_size=50000,
    profit_target=3000,
    daily_loss_limit=1100,
    trailing_drawdown=2000,
    max_contracts=6
)

TPT_100K = PropFirmRuleset(
    name="TPT_100K",
    account_size=100000,
    profit_target=6000,
    daily_loss_limit=2200,
    trailing_drawdown=3000,
    max_contracts=12
)

APEX_50K = PropFirmRuleset(
    name="APEX_50K",
    account_size=50000,
    profit_target=3000,
    daily_loss_limit=1250,
    trailing_drawdown=2500,
    max_contracts=10
)


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    BREAKOUT = "breakout"
    MEAN_REVERTING = "mean_reverting"
    UNKNOWN = "unknown"


# Regime-based confidence modifiers (reduce confidence in uncertain/dangerous regimes)
REGIME_CONFIDENCE_MODIFIERS = {
    MarketRegime.TRENDING_UP: 1.0,      # Full confidence in trend
    MarketRegime.TRENDING_DOWN: 1.0,    # Full confidence in trend
    MarketRegime.BREAKOUT: 0.9,         # Slightly reduce - breakouts can fail
    MarketRegime.MEAN_REVERTING: 0.85,  # Good for mean-revert strategies
    MarketRegime.RANGING: 0.75,         # Reduce in range-bound markets
    MarketRegime.QUIET: 0.7,            # Low volatility = less opportunity
    MarketRegime.VOLATILE: 0.5,         # High risk - halve confidence
    MarketRegime.UNKNOWN: 0.3,          # SAFETY: Very low confidence when uncertain
}


class TradingSignal(Enum):
    """Trading signal types"""
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class TradeRecord:
    """Complete trade record for learning"""
    trade_id: str
    symbol: str
    direction: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    contracts: int
    pnl: float
    pnl_pct: float
    strategy: str
    confidence: float
    regime: MarketRegime
    exit_reason: str  # 'tp', 'sl', 'timeout', 'manual'
    features: Dict[str, float] = field(default_factory=dict)

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def r_multiple(self) -> float:
        """Risk multiple achieved"""
        if self.direction == 'long':
            return (self.exit_price - self.entry_price) / self.entry_price
        return (self.entry_price - self.exit_price) / self.entry_price


@dataclass
class ModelConfig:
    """Neural network configuration"""
    # Architecture - input_dim MUST match FeatureEngine.FEATURE_NAMES count (56)
    input_dim: int = 56
    hidden_dim: int = 256
    num_heads: int = 8
    num_layers: int = 4
    dropout: float = 0.15

    # Training
    learning_rate: float = 3e-4
    weight_decay: float = 1e-5
    batch_size: int = 64
    max_epochs: int = 100
    patience: int = 15
    gradient_clip: float = 1.0

    # RL specific
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5

    # Auto-training
    auto_train_interval: int = 300  # seconds
    min_trades_for_training: int = 10


# ============== DEVICE ABSTRACTION ==============

@dataclass
class DeviceInfo:
    """Information about the compute device"""
    name: str
    type: str  # 'cuda', 'mps', 'cpu'
    index: int
    total_memory_gb: float
    available_memory_gb: float
    compute_capability: Optional[str] = None
    is_available: bool = True


class DeviceManager:
    """
    Unified device management for PyTorch operations.
    Matches quant-platform pattern for multi-GPU/CPU abstraction.

    Supports:
    - CUDA (NVIDIA GPUs)
    - MPS (Apple Silicon)
    - CPU fallback
    """

    def __init__(self, preferred: str = "auto"):
        """
        Initialize device manager.

        Args:
            preferred: Device preference - "auto", "cuda", "cuda:0", "mps", "cpu"
        """
        self.preferred = preferred
        self._device: Optional[Any] = None
        self._device_info: Optional[DeviceInfo] = None

        if TORCH_AVAILABLE:
            self._initialize_device()

    def _initialize_device(self) -> None:
        """Detect and initialize the best available device"""
        if self.preferred == "auto":
            self._device = self._auto_select_device()
        elif self.preferred.startswith("cuda"):
            self._device = self._try_cuda(self.preferred)
        elif self.preferred == "mps":
            self._device = self._try_mps()
        else:
            self._device = torch.device("cpu")

        self._device_info = self._get_device_info()
        logger.info(f"Device initialized: {self._device_info.name} ({self._device_info.type})")

    def _auto_select_device(self):
        """Automatically select the best available device"""
        # Try CUDA first (NVIDIA GPU)
        if torch.cuda.is_available():
            return self._try_cuda()

        # Try MPS (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return self._try_mps()

        # Fallback to CPU
        return torch.device("cpu")

    def _try_cuda(self, device_str: str = "cuda") -> Any:
        """Try to initialize CUDA device"""
        try:
            if torch.cuda.is_available():
                device = torch.device(device_str)
                # Validate by allocating small tensor
                test = torch.zeros(1, device=device)
                del test
                return device
        except Exception as e:
            logger.warning(f"CUDA initialization failed: {e}")

        return torch.device("cpu")

    def _try_mps(self) -> Any:
        """Try to initialize MPS device (Apple Silicon)"""
        try:
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = torch.device("mps")
                # Validate by allocating small tensor
                test = torch.zeros(1, device=device)
                del test
                return device
        except Exception as e:
            logger.warning(f"MPS initialization failed: {e}")

        return torch.device("cpu")

    def _get_device_info(self) -> DeviceInfo:
        """Get detailed device information"""
        device_type = str(self._device.type)

        if device_type == "cuda":
            idx = self._device.index if self._device.index is not None else 0
            props = torch.cuda.get_device_properties(idx)
            total_mem = props.total_memory / (1024**3)
            avail_mem = (props.total_memory - torch.cuda.memory_allocated(idx)) / (1024**3)

            return DeviceInfo(
                name=props.name,
                type="cuda",
                index=idx,
                total_memory_gb=total_mem,
                available_memory_gb=avail_mem,
                compute_capability=f"{props.major}.{props.minor}",
                is_available=True
            )

        elif device_type == "mps":
            return DeviceInfo(
                name="Apple Silicon GPU",
                type="mps",
                index=0,
                total_memory_gb=0,  # MPS doesn't expose memory info
                available_memory_gb=0,
                is_available=True
            )

        else:  # CPU
            return DeviceInfo(
                name=platform.processor() or "CPU",
                type="cpu",
                index=0,
                total_memory_gb=0,
                available_memory_gb=0,
                is_available=True
            )

    @property
    def device(self):
        """Get the current device"""
        if not TORCH_AVAILABLE:
            return None
        return self._device

    @property
    def device_type(self) -> str:
        """Get device type string"""
        if self._device is None:
            return "none"
        return str(self._device.type)

    @property
    def is_cuda(self) -> bool:
        """Check if using CUDA"""
        return self.device_type == "cuda"

    @property
    def is_mps(self) -> bool:
        """Check if using MPS (Apple Silicon)"""
        return self.device_type == "mps"

    @property
    def is_cpu(self) -> bool:
        """Check if using CPU"""
        return self.device_type == "cpu"

    @property
    def info(self) -> Optional[DeviceInfo]:
        """Get device info"""
        return self._device_info

    def to_device(self, tensor_or_module):
        """Move tensor or module to the current device"""
        if self._device is None:
            return tensor_or_module
        return tensor_or_module.to(self._device)

    def tensor(self, data, dtype=None):
        """Create a tensor on the current device"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        if dtype is None:
            dtype = torch.float32

        return torch.tensor(data, dtype=dtype, device=self._device)

    def zeros(self, *size, dtype=None):
        """Create a zeros tensor on the current device"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        if dtype is None:
            dtype = torch.float32

        return torch.zeros(*size, dtype=dtype, device=self._device)

    def ones(self, *size, dtype=None):
        """Create a ones tensor on the current device"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        if dtype is None:
            dtype = torch.float32

        return torch.ones(*size, dtype=dtype, device=self._device)

    def empty_cache(self) -> None:
        """Clear device memory cache"""
        if self.is_cuda:
            torch.cuda.empty_cache()
        elif self.is_mps:
            if hasattr(torch.mps, 'empty_cache'):
                torch.mps.empty_cache()

    def synchronize(self) -> None:
        """Synchronize device operations"""
        if self.is_cuda:
            torch.cuda.synchronize()
        elif self.is_mps:
            if hasattr(torch.mps, 'synchronize'):
                torch.mps.synchronize()

    def memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        if self.is_cuda:
            idx = self._device.index if self._device.index is not None else 0
            return {
                "allocated_gb": torch.cuda.memory_allocated(idx) / (1024**3),
                "reserved_gb": torch.cuda.memory_reserved(idx) / (1024**3),
                "max_allocated_gb": torch.cuda.max_memory_allocated(idx) / (1024**3),
            }
        return {}

    def get_summary(self) -> Dict[str, Any]:
        """Get device summary for logging/display"""
        info = self._device_info
        if info is None:
            return {"available": False}

        summary = {
            "available": True,
            "name": info.name,
            "type": info.type,
            "index": info.index,
        }

        if info.total_memory_gb > 0:
            summary["total_memory_gb"] = round(info.total_memory_gb, 2)
            summary["available_memory_gb"] = round(info.available_memory_gb, 2)

        if info.compute_capability:
            summary["compute_capability"] = info.compute_capability

        if self.is_cuda:
            summary.update(self.memory_stats())

        return summary


# Global device manager instance
_device_manager: Optional[DeviceManager] = None


def get_device_manager(preferred: str = "auto") -> DeviceManager:
    """Get or create the global device manager"""
    global _device_manager

    if _device_manager is None:
        _device_manager = DeviceManager(preferred)

    return _device_manager


def get_device():
    """Get the current compute device"""
    return get_device_manager().device


# ============== MODEL DRIFT DETECTION ==============

@dataclass
class DriftMetrics:
    """Metrics for tracking model drift."""
    feature_drift_score: float = 0.0
    prediction_drift_score: float = 0.0
    confidence_degradation: float = 0.0
    psi_score: float = 0.0  # Population Stability Index
    drift_detected: bool = False
    drift_type: str = ""  # "covariate", "concept", "both", ""
    last_check: Optional[datetime] = None


class DriftDetector:
    """
    Model drift detection for ML trading systems.
    Detects covariate drift (feature distribution changes) and
    concept drift (prediction-outcome relationship changes).

    Based on quant-platform pattern for production ML monitoring.
    """

    def __init__(
        self,
        reference_window: int = 1000,
        test_window: int = 200,
        psi_threshold: float = 0.25,
        ks_threshold: float = 0.1,
        confidence_threshold: float = 0.15
    ):
        self.reference_window = reference_window
        self.test_window = test_window
        self.psi_threshold = psi_threshold  # PSI > 0.25 indicates significant drift
        self.ks_threshold = ks_threshold
        self.confidence_threshold = confidence_threshold

        # Reference distributions (baseline)
        self.reference_features: Optional[np.ndarray] = None
        self.reference_predictions: List[float] = []
        self.reference_confidences: List[float] = []
        self.reference_outcomes: List[int] = []  # 1 for correct, 0 for incorrect

        # Current/test distributions
        self.current_features: List[np.ndarray] = []
        self.current_predictions: List[float] = []
        self.current_confidences: List[float] = []
        self.current_outcomes: List[int] = []

        # Drift history
        self.drift_history: List[DriftMetrics] = []
        self._is_calibrated = False

    def calibrate(self, features: np.ndarray, predictions: List[float],
                  confidences: List[float], outcomes: List[int]):
        """
        Calibrate the detector with reference (baseline) data.
        Should be called after initial training with validation data.
        """
        self.reference_features = features[-self.reference_window:] if len(features) > self.reference_window else features
        self.reference_predictions = predictions[-self.reference_window:]
        self.reference_confidences = confidences[-self.reference_window:]
        self.reference_outcomes = outcomes[-self.reference_window:]
        self._is_calibrated = True
        logger.info(f"DriftDetector calibrated with {len(self.reference_predictions)} samples")

    def record_prediction(self, features: np.ndarray, prediction: float,
                          confidence: float, outcome: Optional[int] = None):
        """Record a new prediction for drift monitoring."""
        self.current_features.append(features.flatten() if features.ndim > 1 else features)
        self.current_predictions.append(prediction)
        self.current_confidences.append(confidence)

        if outcome is not None:
            self.current_outcomes.append(outcome)

        # Keep only test window size
        if len(self.current_predictions) > self.test_window:
            self.current_features.pop(0)
            self.current_predictions.pop(0)
            self.current_confidences.pop(0)
            if self.current_outcomes:
                self.current_outcomes.pop(0)

    def record_outcome(self, outcome: int):
        """Record outcome for the most recent prediction."""
        if len(self.current_outcomes) < len(self.current_predictions):
            self.current_outcomes.append(outcome)

    def _calculate_psi(self, reference: List[float], current: List[float], bins: int = 10) -> float:
        """
        Calculate Population Stability Index (PSI).
        PSI < 0.1: No significant shift
        PSI 0.1-0.25: Moderate shift, investigate
        PSI > 0.25: Significant shift, action required
        """
        if len(reference) < bins or len(current) < bins:
            return 0.0

        try:
            # Create bins from reference distribution
            ref_arr = np.array(reference)
            cur_arr = np.array(current)

            # Handle edge cases
            min_val = min(ref_arr.min(), cur_arr.min())
            max_val = max(ref_arr.max(), cur_arr.max())

            if min_val == max_val:
                return 0.0

            bin_edges = np.linspace(min_val, max_val, bins + 1)

            # Calculate proportions
            ref_counts, _ = np.histogram(ref_arr, bins=bin_edges)
            cur_counts, _ = np.histogram(cur_arr, bins=bin_edges)

            # Add small epsilon to avoid division by zero
            epsilon = 1e-6
            ref_props = (ref_counts + epsilon) / (len(reference) + epsilon * bins)
            cur_props = (cur_counts + epsilon) / (len(current) + epsilon * bins)

            # PSI formula
            psi = np.sum((cur_props - ref_props) * np.log(cur_props / ref_props))
            return float(psi)
        except Exception as e:
            logger.debug(f"PSI calculation error: {e}")
            return 0.0

    def _calculate_ks_statistic(self, reference: List[float], current: List[float]) -> float:
        """Calculate Kolmogorov-Smirnov statistic for distribution comparison."""
        if len(reference) < 10 or len(current) < 10:
            return 0.0

        try:
            ref_sorted = np.sort(reference)
            cur_sorted = np.sort(current)

            # Combine and calculate empirical CDFs
            all_values = np.concatenate([ref_sorted, cur_sorted])
            all_values = np.sort(np.unique(all_values))

            ref_cdf = np.searchsorted(ref_sorted, all_values, side='right') / len(ref_sorted)
            cur_cdf = np.searchsorted(cur_sorted, all_values, side='right') / len(cur_sorted)

            ks_stat = np.max(np.abs(ref_cdf - cur_cdf))
            return float(ks_stat)
        except Exception as e:
            logger.debug(f"KS statistic error: {e}")
            return 0.0

    def check_drift(self) -> DriftMetrics:
        """
        Check for model drift using multiple metrics.
        Returns DriftMetrics with detection results.
        """
        metrics = DriftMetrics(last_check=datetime.now(timezone.utc))

        if not self._is_calibrated:
            return metrics

        if len(self.current_predictions) < self.test_window // 2:
            return metrics

        # 1. Prediction distribution drift (PSI)
        metrics.psi_score = self._calculate_psi(
            self.reference_predictions,
            self.current_predictions
        )
        metrics.prediction_drift_score = metrics.psi_score

        # 2. Feature drift (using first feature as proxy, or aggregate)
        if self.reference_features is not None and len(self.current_features) > 0:
            try:
                ref_mean = np.mean(self.reference_features, axis=0)
                cur_features = np.array(self.current_features)
                cur_mean = np.mean(cur_features, axis=0)

                # Normalized feature drift
                ref_std = np.std(self.reference_features, axis=0) + 1e-6
                feature_drift = np.mean(np.abs(cur_mean - ref_mean) / ref_std)
                metrics.feature_drift_score = float(feature_drift)
            except Exception as e:
                logger.debug(f"Feature drift calculation error: {e}")

        # 3. Confidence degradation
        if self.reference_confidences and self.current_confidences:
            ref_conf = np.mean(self.reference_confidences)
            cur_conf = np.mean(self.current_confidences)
            metrics.confidence_degradation = float(ref_conf - cur_conf)

        # Determine drift type
        covariate_drift = metrics.feature_drift_score > self.ks_threshold
        concept_drift = metrics.psi_score > self.psi_threshold
        confidence_drift = metrics.confidence_degradation > self.confidence_threshold

        if covariate_drift and concept_drift:
            metrics.drift_detected = True
            metrics.drift_type = "both"
        elif covariate_drift:
            metrics.drift_detected = True
            metrics.drift_type = "covariate"
        elif concept_drift or confidence_drift:
            metrics.drift_detected = True
            metrics.drift_type = "concept"

        self.drift_history.append(metrics)

        if metrics.drift_detected:
            logger.warning(
                f"Model drift detected! Type: {metrics.drift_type}, "
                f"PSI: {metrics.psi_score:.3f}, "
                f"Feature drift: {metrics.feature_drift_score:.3f}, "
                f"Confidence degradation: {metrics.confidence_degradation:.3f}"
            )

        return metrics

    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of drift detection status."""
        if not self.drift_history:
            return {
                "is_calibrated": self._is_calibrated,
                "samples_collected": len(self.current_predictions),
                "drift_detected": False,
                "last_check": None
            }

        latest = self.drift_history[-1]
        recent_drifts = [m for m in self.drift_history[-10:] if m.drift_detected]

        return {
            "is_calibrated": self._is_calibrated,
            "samples_collected": len(self.current_predictions),
            "reference_samples": len(self.reference_predictions),
            "drift_detected": latest.drift_detected,
            "drift_type": latest.drift_type,
            "psi_score": latest.psi_score,
            "feature_drift_score": latest.feature_drift_score,
            "confidence_degradation": latest.confidence_degradation,
            "recent_drift_count": len(recent_drifts),
            "last_check": latest.last_check.isoformat() if latest.last_check else None,
            "recommendation": self._get_recommendation(latest)
        }

    def _get_recommendation(self, metrics: DriftMetrics) -> str:
        """Get actionable recommendation based on drift metrics."""
        if not metrics.drift_detected:
            return "Model performing within expected parameters"

        if metrics.drift_type == "both":
            return "CRITICAL: Both feature and prediction drift detected. Immediate retraining recommended."
        elif metrics.drift_type == "covariate":
            return "Feature distribution has shifted. Consider retraining with recent data."
        elif metrics.drift_type == "concept":
            return "Model predictions drifting. Evaluate model performance and consider retraining."

        return "Monitor closely and prepare for retraining"

    def reset(self):
        """Reset current window (call after retraining)."""
        self.current_features = []
        self.current_predictions = []
        self.current_confidences = []
        self.current_outcomes = []


# ============== SNAPSHOT VALIDATION ==============

@dataclass
class SnapshotValidationResult:
    """Result of snapshot validation"""
    is_valid: bool
    snapshot_id: str
    schema_hash: str
    model_hash: str
    created_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SnapshotValidator:
    """
    Validates model snapshots before loading.
    Matches quant-platform pattern for model integrity verification.

    Checks:
    - Schema compatibility (feature hash match)
    - Weights integrity (checksum verification)
    - Model architecture compatibility
    - Performance sanity checks
    """

    def __init__(
        self,
        expected_schema_hash: Optional[str] = None,
        min_accuracy: float = 0.45,
        max_age_days: int = 30
    ):
        self.expected_schema_hash = expected_schema_hash
        self.min_accuracy = min_accuracy
        self.max_age_days = max_age_days
        self._validation_history: List[SnapshotValidationResult] = []

    def validate_snapshot(
        self,
        weights: bytes,
        metadata: Dict[str, Any],
        feature_names: Optional[List[str]] = None
    ) -> SnapshotValidationResult:
        """
        Validate a model snapshot before loading.

        Args:
            weights: Serialized model weights (bytes)
            metadata: Snapshot metadata (epoch, accuracy, created_at, etc.)
            feature_names: Feature names to validate schema against

        Returns:
            SnapshotValidationResult with validation status
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Generate IDs and hashes
        model_hash = hashlib.sha256(weights).hexdigest()[:16]
        snapshot_id = f"snap_{model_hash[:8]}"

        schema_hash = ""
        if feature_names:
            schema_hash = compute_schema_hash(feature_names)

        created_at = None
        if 'created_at' in metadata:
            try:
                if isinstance(metadata['created_at'], str):
                    created_at = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                elif isinstance(metadata['created_at'], datetime):
                    created_at = metadata['created_at']
            except (ValueError, TypeError):
                warnings.append("Could not parse created_at timestamp")

        # Validation 1: Weights integrity
        if len(weights) < 1000:  # Suspiciously small
            errors.append(f"Weights too small ({len(weights)} bytes), likely corrupted")
        elif len(weights) > 500_000_000:  # 500MB limit
            errors.append(f"Weights too large ({len(weights)} bytes), exceeds 500MB limit")

        # Validation 2: Schema compatibility
        if self.expected_schema_hash and schema_hash:
            if schema_hash != self.expected_schema_hash:
                errors.append(
                    f"Schema mismatch: expected {self.expected_schema_hash}, "
                    f"got {schema_hash}"
                )

        # Validation 3: Accuracy sanity check
        accuracy = metadata.get('accuracy', 0)
        if accuracy < self.min_accuracy:
            warnings.append(
                f"Low accuracy ({accuracy:.3f}) below minimum ({self.min_accuracy})"
            )

        if accuracy > 0.99:
            warnings.append(
                f"Suspiciously high accuracy ({accuracy:.3f}), possible overfitting"
            )

        # Validation 4: Age check
        if created_at:
            age_days = (datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)).days
            if age_days > self.max_age_days:
                warnings.append(
                    f"Snapshot is {age_days} days old, exceeds {self.max_age_days} day limit"
                )

        # Validation 5: Required metadata fields
        required_fields = ['epoch', 'loss']
        for field in required_fields:
            if field not in metadata:
                warnings.append(f"Missing metadata field: {field}")

        # Validation 6: Check for NaN/Inf in metadata
        for key, value in metadata.items():
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    errors.append(f"Invalid value in metadata.{key}: {value}")

        result = SnapshotValidationResult(
            is_valid=len(errors) == 0,
            snapshot_id=snapshot_id,
            schema_hash=schema_hash,
            model_hash=model_hash,
            created_at=created_at,
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )

        self._validation_history.append(result)

        if not result.is_valid:
            logger.error(f"Snapshot validation failed: {errors}")
        elif warnings:
            logger.warning(f"Snapshot validation passed with warnings: {warnings}")
        else:
            logger.info(f"Snapshot {snapshot_id} validated successfully")

        return result

    def validate_weights_tensor(
        self,
        state_dict: Dict[str, Any],
        expected_shapes: Optional[Dict[str, Tuple[int, ...]]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate PyTorch state dict shapes and values.

        Args:
            state_dict: Model state dict
            expected_shapes: Optional dict of layer_name -> expected_shape

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: List[str] = []

        for name, tensor in state_dict.items():
            # Check for NaN/Inf
            if hasattr(tensor, 'isnan') and tensor.isnan().any():
                errors.append(f"NaN values found in {name}")
            if hasattr(tensor, 'isinf') and tensor.isinf().any():
                errors.append(f"Inf values found in {name}")

            # Check shape if expected
            if expected_shapes and name in expected_shapes:
                expected = expected_shapes[name]
                actual = tuple(tensor.shape)
                if actual != expected:
                    errors.append(
                        f"Shape mismatch for {name}: expected {expected}, got {actual}"
                    )

        return len(errors) == 0, errors

    def create_snapshot_manifest(
        self,
        weights: bytes,
        metadata: Dict[str, Any],
        feature_names: List[str]
    ) -> Dict[str, Any]:
        """
        Create a manifest for a new snapshot.

        Returns a dict suitable for storing alongside the weights.
        """
        weights_hash = hashlib.sha256(weights).hexdigest()
        schema_hash = compute_schema_hash(feature_names)

        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "weights_hash": weights_hash,
            "weights_size": len(weights),
            "schema_hash": schema_hash,
            "feature_count": len(feature_names),
            "feature_names": feature_names,
            "metadata": metadata
        }

    def verify_manifest(
        self,
        manifest: Dict[str, Any],
        weights: bytes
    ) -> Tuple[bool, List[str]]:
        """
        Verify weights against a manifest.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: List[str] = []

        # Check weights hash
        actual_hash = hashlib.sha256(weights).hexdigest()
        expected_hash = manifest.get('weights_hash', '')
        if actual_hash != expected_hash:
            errors.append(f"Weights hash mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}...")

        # Check size
        actual_size = len(weights)
        expected_size = manifest.get('weights_size', 0)
        if actual_size != expected_size:
            errors.append(f"Weights size mismatch: expected {expected_size}, got {actual_size}")

        return len(errors) == 0, errors

    def get_validation_history(self) -> List[Dict[str, Any]]:
        """Get validation history as serializable dicts."""
        return [
            {
                "is_valid": r.is_valid,
                "snapshot_id": r.snapshot_id,
                "schema_hash": r.schema_hash,
                "model_hash": r.model_hash,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "errors": r.errors,
                "warnings": r.warnings
            }
            for r in self._validation_history
        ]


# ============== FEATURE ENGINEERING ==============

def compute_schema_hash(feature_names: List[str]) -> str:
    """
    Compute SHA256 hash of feature schema for version compatibility.
    Matches quant-platform pattern for model version tracking.
    """
    sorted_names = sorted(feature_names)
    schema_str = ",".join(sorted_names)
    return hashlib.sha256(schema_str.encode()).hexdigest()[:12]


class FeatureEngine:
    """Advanced feature engineering for ML models"""

    FEATURE_NAMES = [
        # Price features
        'returns_1', 'returns_5', 'returns_10', 'returns_20',
        'log_returns_1', 'log_returns_5',
        'price_to_sma_20', 'price_to_sma_50',
        'price_to_vwap',

        # Momentum
        'rsi_14', 'rsi_7', 'rsi_21',
        'macd', 'macd_signal', 'macd_hist',
        'stoch_k', 'stoch_d',
        'williams_r',
        'roc_10', 'roc_20',
        'momentum_10',
        'cci_20',

        # Trend
        'adx_14', 'plus_di', 'minus_di',
        'aroon_up', 'aroon_down', 'aroon_osc',
        'sma_cross_20_50', 'ema_cross_12_26',

        # Volatility
        'atr_14', 'atr_7',
        'bb_width', 'bb_pct',
        'keltner_width',
        'volatility_20',
        'volatility_ratio',

        # Volume
        'volume_sma_ratio',
        'obv_slope',
        'mfi_14',
        'vwap_distance',
        'volume_zscore',

        # Pattern recognition
        'higher_high', 'lower_low',
        'inside_bar', 'outside_bar',
        'gap_pct',

        # Market structure
        'pivot_distance',
        'support_distance',
        'resistance_distance',

        # Time features
        'hour_sin', 'hour_cos',
        'day_of_week_sin', 'day_of_week_cos',
        'is_market_open', 'time_to_close'
    ]

    # Schema hash for version compatibility checking
    SCHEMA_HASH = compute_schema_hash(FEATURE_NAMES)

    def __init__(self):
        self.feature_means = {}
        self.feature_stds = {}
        self.fitted = False
        self.schema_hash = self.SCHEMA_HASH
        logger.debug(f"FeatureEngine initialized with schema hash: {self.schema_hash}")

    def calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical features from OHLCV data"""
        if df is None or len(df) < 50:
            return pd.DataFrame()

        features = pd.DataFrame(index=df.index)

        try:
            # Price features
            features['returns_1'] = df['close'].pct_change(1)
            features['returns_5'] = df['close'].pct_change(5)
            features['returns_10'] = df['close'].pct_change(10)
            features['returns_20'] = df['close'].pct_change(20)
            features['log_returns_1'] = np.log(df['close'] / df['close'].shift(1))
            features['log_returns_5'] = np.log(df['close'] / df['close'].shift(5))

            # Moving averages
            sma_20 = df['close'].rolling(20).mean()
            sma_50 = df['close'].rolling(50).mean()
            ema_12 = df['close'].ewm(span=12).mean()
            ema_26 = df['close'].ewm(span=26).mean()

            features['price_to_sma_20'] = df['close'] / sma_20 - 1
            features['price_to_sma_50'] = df['close'] / sma_50 - 1
            features['sma_cross_20_50'] = (sma_20 > sma_50).astype(float)
            features['ema_cross_12_26'] = (ema_12 > ema_26).astype(float)

            # RSI
            features['rsi_14'] = self._calculate_rsi(df['close'], 14)
            features['rsi_7'] = self._calculate_rsi(df['close'], 7)
            features['rsi_21'] = self._calculate_rsi(df['close'], 21)

            # MACD
            macd_line = ema_12 - ema_26
            macd_signal = macd_line.ewm(span=9).mean()
            features['macd'] = macd_line
            features['macd_signal'] = macd_signal
            features['macd_hist'] = macd_line - macd_signal

            # Stochastic
            low_14 = df['low'].rolling(14).min()
            high_14 = df['high'].rolling(14).max()
            features['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14 + 1e-10)
            features['stoch_d'] = features['stoch_k'].rolling(3).mean()

            # Williams %R
            features['williams_r'] = -100 * (high_14 - df['close']) / (high_14 - low_14 + 1e-10)

            # ROC and Momentum
            features['roc_10'] = df['close'].pct_change(10) * 100
            features['roc_20'] = df['close'].pct_change(20) * 100
            features['momentum_10'] = df['close'] - df['close'].shift(10)

            # CCI
            tp = (df['high'] + df['low'] + df['close']) / 3
            sma_tp = tp.rolling(20).mean()
            mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
            features['cci_20'] = (tp - sma_tp) / (0.015 * mad + 1e-10)

            # ADX
            adx_data = self._calculate_adx(df, 14)
            features['adx_14'] = adx_data['adx']
            features['plus_di'] = adx_data['plus_di']
            features['minus_di'] = adx_data['minus_di']

            # Aroon
            aroon = self._calculate_aroon(df, 25)
            features['aroon_up'] = aroon['up']
            features['aroon_down'] = aroon['down']
            features['aroon_osc'] = aroon['up'] - aroon['down']

            # ATR
            features['atr_14'] = self._calculate_atr(df, 14)
            features['atr_7'] = self._calculate_atr(df, 7)

            # Bollinger Bands
            bb_sma = df['close'].rolling(20).mean()
            bb_std = df['close'].rolling(20).std()
            bb_upper = bb_sma + 2 * bb_std
            bb_lower = bb_sma - 2 * bb_std
            features['bb_width'] = (bb_upper - bb_lower) / bb_sma
            features['bb_pct'] = (df['close'] - bb_lower) / (bb_upper - bb_lower + 1e-10)

            # Keltner Channel
            kc_mid = df['close'].ewm(span=20).mean()
            kc_atr = features['atr_14'] * 2
            features['keltner_width'] = kc_atr / kc_mid

            # Volatility
            features['volatility_20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
            vol_short = df['close'].pct_change().rolling(5).std()
            vol_long = df['close'].pct_change().rolling(20).std()
            features['volatility_ratio'] = vol_short / (vol_long + 1e-10)

            # Volume features
            vol_sma = df['volume'].rolling(20).mean()
            features['volume_sma_ratio'] = df['volume'] / (vol_sma + 1e-10)
            features['volume_zscore'] = (df['volume'] - vol_sma) / (df['volume'].rolling(20).std() + 1e-10)

            # OBV
            obv = (np.sign(df['close'].diff()) * df['volume']).cumsum()
            features['obv_slope'] = obv.diff(5) / 5

            # MFI
            features['mfi_14'] = self._calculate_mfi(df, 14)

            # VWAP
            vwap = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            features['price_to_vwap'] = df['close'] / vwap - 1
            features['vwap_distance'] = (df['close'] - vwap) / features['atr_14']

            # Pattern features
            features['higher_high'] = (df['high'] > df['high'].shift(1)).astype(float)
            features['lower_low'] = (df['low'] < df['low'].shift(1)).astype(float)
            features['inside_bar'] = ((df['high'] < df['high'].shift(1)) &
                                       (df['low'] > df['low'].shift(1))).astype(float)
            features['outside_bar'] = ((df['high'] > df['high'].shift(1)) &
                                        (df['low'] < df['low'].shift(1))).astype(float)
            features['gap_pct'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)

            # Support/Resistance (simplified)
            pivot = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
            r1 = 2 * pivot - df['low'].shift(1)
            s1 = 2 * pivot - df['high'].shift(1)
            features['pivot_distance'] = (df['close'] - pivot) / features['atr_14']
            features['resistance_distance'] = (r1 - df['close']) / features['atr_14']
            features['support_distance'] = (df['close'] - s1) / features['atr_14']

            # Time features
            if 'timestamp' in df.columns or isinstance(df.index, pd.DatetimeIndex):
                times = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df['timestamp'])
                features['hour_sin'] = np.sin(2 * np.pi * times.hour / 24)
                features['hour_cos'] = np.cos(2 * np.pi * times.hour / 24)
                features['day_of_week_sin'] = np.sin(2 * np.pi * times.dayofweek / 7)
                features['day_of_week_cos'] = np.cos(2 * np.pi * times.dayofweek / 7)
                features['is_market_open'] = ((times.hour >= 9) & (times.hour < 16)).astype(float)
                features['time_to_close'] = np.clip((16 - times.hour) / 7, 0, 1)
            else:
                # Default time features
                features['hour_sin'] = 0
                features['hour_cos'] = 1
                features['day_of_week_sin'] = 0
                features['day_of_week_cos'] = 1
                features['is_market_open'] = 1
                features['time_to_close'] = 0.5

            # Fill NaN values
            features = features.ffill().bfill()
            features = features.replace([np.inf, -np.inf], 0)
            features = features.fillna(0)

        except Exception as e:
            logger.error(f"Feature calculation error: {e}")
            return pd.DataFrame()

        return features

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate RSI"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calculate_adx(self, df: pd.DataFrame, period: int) -> Dict[str, pd.Series]:
        """Calculate ADX, +DI, -DI"""
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()

        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

        tr = self._calculate_atr(df, 1) * period  # Approximate TR sum

        plus_di = 100 * pd.Series(plus_dm).rolling(period).sum() / (tr + 1e-10)
        minus_di = 100 * pd.Series(minus_dm).rolling(period).sum() / (tr + 1e-10)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = pd.Series(dx).rolling(period).mean()

        return {'adx': adx, 'plus_di': plus_di, 'minus_di': minus_di}

    def _calculate_aroon(self, df: pd.DataFrame, period: int) -> Dict[str, pd.Series]:
        """Calculate Aroon Up/Down"""
        aroon_up = df['high'].rolling(period + 1).apply(
            lambda x: (period - (period - x.argmax())) / period * 100, raw=True
        )
        aroon_down = df['low'].rolling(period + 1).apply(
            lambda x: (period - (period - x.argmin())) / period * 100, raw=True
        )
        return {'up': aroon_up, 'down': aroon_down}

    def _calculate_mfi(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Money Flow Index"""
        tp = (df['high'] + df['low'] + df['close']) / 3
        mf = tp * df['volume']

        pos_mf = np.where(tp > tp.shift(1), mf, 0)
        neg_mf = np.where(tp < tp.shift(1), mf, 0)

        pos_mf_sum = pd.Series(pos_mf).rolling(period).sum()
        neg_mf_sum = pd.Series(neg_mf).rolling(period).sum()

        mfi = 100 - (100 / (1 + pos_mf_sum / (neg_mf_sum + 1e-10)))
        return mfi

    def normalize_features(self, features: pd.DataFrame, fit: bool = False) -> np.ndarray:
        """Normalize features to zero mean, unit variance"""
        if fit or not self.fitted:
            self.feature_means = features.mean().to_dict()
            self.feature_stds = features.std().to_dict()
            self.fitted = True

        normalized = features.copy()
        for col in features.columns:
            mean = self.feature_means.get(col, 0)
            std = self.feature_stds.get(col, 1)
            if std > 0:
                normalized[col] = (features[col] - mean) / std
            else:
                normalized[col] = 0

        return normalized.values.astype(np.float32)


# ============== NEURAL NETWORK MODELS ==============

if TORCH_AVAILABLE:

    class PositionalEncoding(nn.Module):
        """Positional encoding for transformer"""
        def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
            super().__init__()
            self.dropout = nn.Dropout(p=dropout)

            position = torch.arange(max_len).unsqueeze(1)
            div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
            pe = torch.zeros(max_len, d_model)
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            self.register_buffer('pe', pe.unsqueeze(0))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = x + self.pe[:, :x.size(1)]
            return self.dropout(x)


    class TransformerEncoder(nn.Module):
        """Transformer encoder for sequence modeling"""
        def __init__(self, config: ModelConfig):
            super().__init__()
            self.config = config

            self.input_proj = nn.Linear(config.input_dim, config.hidden_dim)
            self.pos_encoder = PositionalEncoding(config.hidden_dim, dropout=config.dropout)

            encoder_layer = nn.TransformerEncoderLayer(
                d_model=config.hidden_dim,
                nhead=config.num_heads,
                dim_feedforward=config.hidden_dim * 4,
                dropout=config.dropout,
                activation='gelu',
                batch_first=True
            )
            self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)

            self.norm = nn.LayerNorm(config.hidden_dim)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = self.input_proj(x)
            x = self.pos_encoder(x)
            x = self.transformer(x)
            x = self.norm(x)
            return x[:, -1, :]  # Return last timestep


    class LSTMEncoder(nn.Module):
        """Bidirectional LSTM encoder"""
        def __init__(self, config: ModelConfig):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=config.input_dim,
                hidden_size=config.hidden_dim // 2,
                num_layers=config.num_layers,
                batch_first=True,
                bidirectional=True,
                dropout=config.dropout if config.num_layers > 1 else 0
            )
            self.norm = nn.LayerNorm(config.hidden_dim)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            output, (h_n, _) = self.lstm(x)
            # Concatenate forward and backward final hidden states
            hidden = torch.cat([h_n[-2], h_n[-1]], dim=-1)
            return self.norm(hidden)


    class TradingTransformer(nn.Module):
        """Main trading prediction model"""
        def __init__(self, config: ModelConfig):
            super().__init__()
            self.config = config

            # Dual encoder: Transformer + LSTM
            self.transformer_encoder = TransformerEncoder(config)
            self.lstm_encoder = LSTMEncoder(config)

            # Fusion layer
            self.fusion = nn.Sequential(
                nn.Linear(config.hidden_dim * 2, config.hidden_dim),
                nn.GELU(),
                nn.Dropout(config.dropout),
                nn.LayerNorm(config.hidden_dim)
            )

            # Multi-task heads
            # Signal prediction (STRONG_SELL, SELL, HOLD, BUY, STRONG_BUY)
            self.signal_head = nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2),
                nn.GELU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim // 2, 5)
            )

            # Confidence prediction
            self.confidence_head = nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, 1),
                nn.Sigmoid()
            )

            # Regime prediction
            self.regime_head = nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2),
                nn.GELU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim // 2, len(MarketRegime))
            )

            # Value head for RL (actor-critic)
            self.value_head = nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, 1)
            )

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            # Encode with both models
            trans_out = self.transformer_encoder(x)
            lstm_out = self.lstm_encoder(x)

            # Fuse representations
            fused = self.fusion(torch.cat([trans_out, lstm_out], dim=-1))

            return {
                'signal_logits': self.signal_head(fused),
                'confidence': self.confidence_head(fused),
                'regime_logits': self.regime_head(fused),
                'value': self.value_head(fused)
            }

        def get_signal(self, x: torch.Tensor) -> Tuple[int, float, str]:
            """Get trading signal with confidence and regime"""
            with torch.no_grad():
                output = self.forward(x)

                signal_probs = F.softmax(output['signal_logits'], dim=-1)
                signal = signal_probs.argmax(dim=-1).item() - 2  # Map to -2, -1, 0, 1, 2
                confidence = output['confidence'].item()

                regime_probs = F.softmax(output['regime_logits'], dim=-1)
                regime_idx = regime_probs.argmax(dim=-1).item()
                regime = list(MarketRegime)[regime_idx].value

            return signal, confidence, regime


    class PPOAgent:
        """Proximal Policy Optimization agent for trading"""
        def __init__(self, config: ModelConfig, device: str = 'cuda'):
            self.config = config
            self.device = device if torch.cuda.is_available() else 'cpu'

            self.model = TradingTransformer(config).to(self.device)
            self.optimizer = AdamW(
                self.model.parameters(),
                lr=config.learning_rate,
                weight_decay=config.weight_decay
            )
            self.scheduler = CosineAnnealingWarmRestarts(
                self.optimizer,
                T_0=10,
                T_mult=2
            )

            # Experience buffer
            self.states = []
            self.actions = []
            self.rewards = []
            self.values = []
            self.log_probs = []
            self.dones = []

        def select_action(self, state: torch.Tensor) -> Tuple[int, float, float]:
            """Select action using current policy"""
            with torch.no_grad():
                state = state.to(self.device)
                output = self.model(state.unsqueeze(0))

                probs = F.softmax(output['signal_logits'], dim=-1)
                dist = torch.distributions.Categorical(probs)
                action = dist.sample()
                log_prob = dist.log_prob(action)
                value = output['value']

            return action.item(), log_prob.item(), value.item()

        def store_transition(self, state, action, reward, value, log_prob, done):
            """Store transition in buffer"""
            self.states.append(state)
            self.actions.append(action)
            self.rewards.append(reward)
            self.values.append(value)
            self.log_probs.append(log_prob)
            self.dones.append(done)

        def compute_gae(self, next_value: float) -> Tuple[torch.Tensor, torch.Tensor]:
            """Compute Generalized Advantage Estimation"""
            rewards = torch.tensor(self.rewards, dtype=torch.float32)
            values = torch.tensor(self.values + [next_value], dtype=torch.float32)
            dones = torch.tensor(self.dones, dtype=torch.float32)

            advantages = torch.zeros_like(rewards)
            gae = 0

            for t in reversed(range(len(rewards))):
                delta = rewards[t] + self.config.gamma * values[t + 1] * (1 - dones[t]) - values[t]
                gae = delta + self.config.gamma * self.config.gae_lambda * (1 - dones[t]) * gae
                advantages[t] = gae

            returns = advantages + values[:-1]
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

            return advantages, returns

        def update(self, epochs: int = 10) -> Dict[str, float]:
            """Update policy using PPO"""
            if len(self.states) < self.config.batch_size:
                return {'loss': 0, 'policy_loss': 0, 'value_loss': 0}

            # Prepare data
            states = torch.stack(self.states).to(self.device)
            actions = torch.tensor(self.actions, dtype=torch.long).to(self.device)
            old_log_probs = torch.tensor(self.log_probs, dtype=torch.float32).to(self.device)

            advantages, returns = self.compute_gae(0)
            advantages = advantages.to(self.device)
            returns = returns.to(self.device)

            total_loss = 0
            policy_loss_sum = 0
            value_loss_sum = 0

            for _ in range(epochs):
                output = self.model(states)

                # Policy loss
                probs = F.softmax(output['signal_logits'], dim=-1)
                dist = torch.distributions.Categorical(probs)
                new_log_probs = dist.log_prob(actions)
                entropy = dist.entropy().mean()

                ratio = torch.exp(new_log_probs - old_log_probs)
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1 - self.config.clip_epsilon,
                                   1 + self.config.clip_epsilon) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                values = output['value'].squeeze()
                value_loss = F.mse_loss(values, returns)

                # Total loss
                loss = (policy_loss +
                       self.config.value_coef * value_loss -
                       self.config.entropy_coef * entropy)

                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
                self.optimizer.step()

                total_loss += loss.item()
                policy_loss_sum += policy_loss.item()
                value_loss_sum += value_loss.item()

            self.scheduler.step()

            # Clear buffer
            self.states.clear()
            self.actions.clear()
            self.rewards.clear()
            self.values.clear()
            self.log_probs.clear()
            self.dones.clear()

            return {
                'loss': total_loss / epochs,
                'policy_loss': policy_loss_sum / epochs,
                'value_loss': value_loss_sum / epochs
            }


# ============== STRATEGY ENSEMBLE ==============

class TradingStrategy(ABC):
    """Base class for trading strategies"""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0

    @abstractmethod
    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        """Generate signal and confidence. Returns (signal, confidence)"""
        pass

    @property
    def win_rate(self) -> float:
        return self.winning_trades / max(self.total_trades, 1)

    @property
    def expectancy(self) -> float:
        return self.total_pnl / max(self.total_trades, 1)

    def update_performance(self, pnl: float):
        self.total_trades += 1
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1


class TrendFollowingStrategy(TradingStrategy):
    """Trend following using ADX and moving averages"""

    def __init__(self):
        super().__init__("TrendFollowing", weight=1.5)

    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        if features.empty:
            return 0, 0.0

        row = features.iloc[-1]

        adx = row.get('adx_14', 0)
        plus_di = row.get('plus_di', 0)
        minus_di = row.get('minus_di', 0)
        sma_cross = row.get('sma_cross_20_50', 0)

        if adx > 25:  # Strong trend
            if plus_di > minus_di and sma_cross > 0:
                confidence = min(adx / 50, 1.0) * 0.8
                return 1, confidence
            elif minus_di > plus_di and sma_cross < 1:
                confidence = min(adx / 50, 1.0) * 0.8
                return -1, confidence

        return 0, 0.3


class MomentumStrategy(TradingStrategy):
    """Momentum using RSI and MACD"""

    def __init__(self):
        super().__init__("Momentum", weight=1.3)

    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        if features.empty:
            return 0, 0.0

        row = features.iloc[-1]

        rsi = row.get('rsi_14', 50)
        macd_hist = row.get('macd_hist', 0)
        momentum = row.get('momentum_10', 0)

        signal = 0
        confidence = 0.5

        if rsi < 30 and macd_hist > 0:  # Oversold with bullish MACD
            signal = 1
            confidence = 0.7
        elif rsi > 70 and macd_hist < 0:  # Overbought with bearish MACD
            signal = -1
            confidence = 0.7
        elif rsi < 40 and momentum > 0:  # Recovering
            signal = 1
            confidence = 0.55
        elif rsi > 60 and momentum < 0:  # Weakening
            signal = -1
            confidence = 0.55

        return signal, confidence


class MeanReversionStrategy(TradingStrategy):
    """Mean reversion using Bollinger Bands"""

    def __init__(self):
        super().__init__("MeanReversion", weight=1.2)

    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        if features.empty:
            return 0, 0.0

        row = features.iloc[-1]

        bb_pct = row.get('bb_pct', 0.5)
        rsi = row.get('rsi_14', 50)
        vol_ratio = row.get('volatility_ratio', 1.0)

        # Look for extremes in ranging market
        if vol_ratio < 1.2:  # Not too volatile
            if bb_pct < 0.1 and rsi < 35:  # Lower band touch
                return 1, 0.65
            elif bb_pct > 0.9 and rsi > 65:  # Upper band touch
                return -1, 0.65

        return 0, 0.4


class VolumeStrategy(TradingStrategy):
    """Volume-based signals"""

    def __init__(self):
        super().__init__("Volume", weight=1.0)

    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        if features.empty:
            return 0, 0.0

        row = features.iloc[-1]

        vol_ratio = row.get('volume_sma_ratio', 1.0)
        vol_zscore = row.get('volume_zscore', 0)
        mfi = row.get('mfi_14', 50)
        returns = row.get('returns_1', 0)

        if vol_ratio > 2.0 and vol_zscore > 2:  # Volume spike
            if returns > 0 and mfi < 80:
                return 1, 0.6
            elif returns < 0 and mfi > 20:
                return -1, 0.6

        return 0, 0.3


class BreakoutStrategy(TradingStrategy):
    """Breakout detection"""

    def __init__(self):
        super().__init__("Breakout", weight=1.4)

    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        if features.empty:
            return 0, 0.0

        row = features.iloc[-1]

        bb_pct = row.get('bb_pct', 0.5)
        adx = row.get('adx_14', 0)
        vol_ratio = row.get('volume_sma_ratio', 1.0)
        higher_high = row.get('higher_high', 0)
        lower_low = row.get('lower_low', 0)

        # Breakout conditions
        if adx > 20 and vol_ratio > 1.5:
            if bb_pct > 1.0 and higher_high:  # Upper breakout
                return 2, 0.75  # Strong buy
            elif bb_pct < 0 and lower_low:  # Lower breakout
                return -2, 0.75  # Strong sell

        return 0, 0.35


class ICTStrategy(TradingStrategy):
    """ICT-style order flow analysis"""

    def __init__(self):
        super().__init__("ICT_OrderFlow", weight=1.6)

    def generate_signal(self, features: pd.DataFrame) -> Tuple[int, float]:
        if features.empty:
            return 0, 0.0

        row = features.iloc[-1]

        # Premium/Discount zones
        price_to_vwap = row.get('price_to_vwap', 0)
        pivot_dist = row.get('pivot_distance', 0)
        support_dist = row.get('support_distance', 0)
        resistance_dist = row.get('resistance_distance', 0)

        # Look for discount zone longs
        if price_to_vwap < -0.005 and support_dist < 1:
            if row.get('rsi_14', 50) < 45:
                return 1, 0.7

        # Look for premium zone shorts
        if price_to_vwap > 0.005 and resistance_dist < 1:
            if row.get('rsi_14', 50) > 55:
                return -1, 0.7

        return 0, 0.4


class StrategyEnsemble:
    """Ensemble of trading strategies with dynamic weighting"""

    def __init__(self):
        self.strategies: List[TradingStrategy] = [
            TrendFollowingStrategy(),
            MomentumStrategy(),
            MeanReversionStrategy(),
            VolumeStrategy(),
            BreakoutStrategy(),
            ICTStrategy(),
        ]
        self.ml_weight = 0.4  # Weight for ML model
        self.strategy_weight = 0.6  # Weight for rule-based strategies

    def generate_ensemble_signal(
        self,
        features: pd.DataFrame,
        ml_signal: Optional[Tuple[int, float]] = None
    ) -> Dict[str, Any]:
        """Generate ensemble signal from all strategies"""

        signals = []
        confidences = []
        weights = []
        strategy_votes = {}

        # Collect strategy signals
        for strategy in self.strategies:
            signal, conf = strategy.generate_signal(features)
            signals.append(signal)
            confidences.append(conf)
            weights.append(strategy.weight * (1 + strategy.win_rate))  # Performance-weighted
            strategy_votes[strategy.name] = {'signal': signal, 'confidence': conf}

        # Calculate weighted vote
        total_weight = sum(weights)
        if total_weight > 0:
            weighted_signal = sum(s * w for s, w in zip(signals, weights)) / total_weight
            weighted_confidence = sum(c * w for c, w in zip(confidences, weights)) / total_weight
        else:
            weighted_signal = 0
            weighted_confidence = 0.5

        # Combine with ML signal if available
        if ml_signal is not None:
            ml_sig, ml_conf = ml_signal
            final_signal = (
                self.strategy_weight * weighted_signal +
                self.ml_weight * ml_sig
            )
            final_confidence = (
                self.strategy_weight * weighted_confidence +
                self.ml_weight * ml_conf
            )
        else:
            final_signal = weighted_signal
            final_confidence = weighted_confidence

        # Discretize signal
        if final_signal > 1.5:
            direction = 'STRONG_BUY'
        elif final_signal > 0.5:
            direction = 'BUY'
        elif final_signal < -1.5:
            direction = 'STRONG_SELL'
        elif final_signal < -0.5:
            direction = 'SELL'
        else:
            direction = 'HOLD'

        return {
            'direction': direction,
            'signal': round(final_signal, 3),
            'confidence': round(final_confidence, 3),
            'strategy_votes': strategy_votes,
            'agreeing_strategies': [
                s.name for s, sig in zip(self.strategies, signals)
                if (sig > 0 and final_signal > 0) or (sig < 0 and final_signal < 0)
            ]
        }

    def update_strategy_performance(self, strategy_name: str, pnl: float):
        """Update performance for a strategy"""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                strategy.update_performance(pnl)
                break


# ============== REGIME DETECTION ==============

class BayesianRegimeDetector:
    """
    Bayesian regime detection with Hidden Markov Model approximation.
    Enhanced with SVM-based regime classification for learned decision boundaries.

    The detector uses two approaches:
    1. Rule-based: Threshold-based regime scoring (always available)
    2. SVM-based: Learned decision boundaries from historical data (when trained)

    When the SVM is trained, both approaches are combined with configurable
    weighting (default 60% SVM, 40% rule-based) for more robust detection.
    """

    def __init__(self, n_regimes: int = 7):
        self.n_regimes = n_regimes
        self.regimes = list(MarketRegime)

        # Transition probabilities (simplified)
        self.transition_matrix = np.ones((n_regimes, n_regimes)) / n_regimes

        # Regime priors
        self.regime_priors = np.ones(n_regimes) / n_regimes

        # SVM regime classifier
        self.svm_regime_classifier = None  # Trained SVC for regime classification
        self.svm_regime_scaler = None      # RobustScaler for SVM features
        self.svm_regime_trained = False
        self.svm_weight = 0.6             # Weight for SVM vs rule-based (when SVM available)
        self.rule_weight = 0.4

        # Training data accumulation
        self._regime_feature_buffer: List[np.ndarray] = []
        self._regime_label_buffer: List[int] = []
        self._min_training_samples = 100   # Minimum samples before SVM training

        # Regime feature names used for SVM
        self._svm_feature_keys = [
            'adx_14', 'plus_di', 'minus_di', 'bb_width', 'bb_pct',
            'volatility_20', 'volatility_ratio', 'volume_sma_ratio',
            'rsi_14', 'rsi_7', 'returns_1', 'returns_5', 'returns_20',
            'atr_14', 'macd_hist', 'stoch_k', 'momentum_10', 'cci_20'
        ]

        # Feature-to-regime mapping thresholds
        self.regime_thresholds = {
            MarketRegime.TRENDING_UP: {'adx': 25, 'plus_di_gt_minus': True},
            MarketRegime.TRENDING_DOWN: {'adx': 25, 'plus_di_gt_minus': False},
            MarketRegime.RANGING: {'adx_max': 20, 'bb_width_max': 0.03},
            MarketRegime.VOLATILE: {'volatility': 0.02, 'atr_ratio': 1.5},
            MarketRegime.QUIET: {'volatility_max': 0.008, 'volume_ratio_max': 0.7},
            MarketRegime.BREAKOUT: {'bb_pct_extreme': True, 'volume_spike': True},
            MarketRegime.MEAN_REVERTING: {'bb_pct_extreme': True, 'rsi_extreme': True},
        }

    def _extract_svm_features(self, features: pd.DataFrame) -> Optional[np.ndarray]:
        """Extract feature vector for SVM regime classification."""
        if features.empty:
            return None

        row = features.iloc[-1]
        feature_vector = []
        for key in self._svm_feature_keys:
            val = row.get(key, 0.0)
            if pd.isna(val) or np.isinf(val):
                val = 0.0
            feature_vector.append(float(val))

        return np.array(feature_vector).reshape(1, -1)

    def train_svm_regime_classifier(
        self,
        features_history: List[np.ndarray],
        regime_labels: List[int]
    ) -> Dict[str, Any]:
        """
        Train SVM classifier on historical regime-labeled data.

        SVM is ideal for regime classification because:
        - Market regimes have complex, non-linear boundaries in feature space
        - RBF kernel can model these non-linear separations
        - Support vectors naturally capture the boundary cases between regimes
        - Probability calibration gives confidence in regime classification

        Args:
            features_history: List of feature vectors (from _extract_svm_features)
            regime_labels: List of integer regime labels

        Returns:
            Training metrics dictionary
        """
        if not SVM_AVAILABLE:
            return {'error': 'scikit-learn not available'}

        if len(features_history) < self._min_training_samples:
            return {
                'error': f'Need at least {self._min_training_samples} samples, got {len(features_history)}'
            }

        try:
            X = np.vstack(features_history)
            y = np.array(regime_labels)

            # Scale features - critical for SVM performance
            self.svm_regime_scaler = RobustScaler()
            X_scaled = self.svm_regime_scaler.fit_transform(X)
            X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

            # Train SVC with RBF kernel and probability estimates
            self.svm_regime_classifier = SVC(
                kernel='rbf',
                C=10.0,
                gamma='scale',
                probability=True,
                class_weight='balanced',
                cache_size=500,
                max_iter=5000,
                random_state=42,
                tol=1e-4,
                shrinking=True
            )

            self.svm_regime_classifier.fit(X_scaled, y)
            self.svm_regime_trained = True

            # Evaluate on training data (in-sample, but useful for diagnostics)
            y_pred = self.svm_regime_classifier.predict(X_scaled)
            from sklearn.metrics import accuracy_score
            train_accuracy = accuracy_score(y, y_pred)

            n_sv = self.svm_regime_classifier.n_support_
            total_sv = sum(n_sv)

            logger.info(
                f"SVM regime classifier trained - "
                f"Accuracy: {train_accuracy:.4f} | "
                f"Support vectors: {total_sv} | "
                f"Classes: {self.svm_regime_classifier.classes_.tolist()}"
            )

            return {
                'trained': True,
                'accuracy': train_accuracy,
                'support_vectors': int(total_sv),
                'n_samples': len(y),
                'n_classes': len(self.svm_regime_classifier.classes_)
            }

        except Exception as e:
            logger.error(f"SVM regime classifier training failed: {e}")
            self.svm_regime_trained = False
            return {'error': str(e)}

    def _accumulate_training_data(self, features: pd.DataFrame, regime_label: int):
        """Accumulate data for online SVM regime training."""
        feature_vec = self._extract_svm_features(features)
        if feature_vec is not None:
            self._regime_feature_buffer.append(feature_vec.flatten())
            self._regime_label_buffer.append(regime_label)

            # Auto-train when enough data is accumulated
            if (len(self._regime_feature_buffer) >= self._min_training_samples and
                    len(self._regime_feature_buffer) % 50 == 0):  # Retrain every 50 new samples
                self.train_svm_regime_classifier(
                    self._regime_feature_buffer,
                    self._regime_label_buffer
                )

    def _svm_predict_regime(self, features: pd.DataFrame) -> Optional[Tuple[MarketRegime, Dict[str, float]]]:
        """Use trained SVM to predict regime with probabilities."""
        if not self.svm_regime_trained or self.svm_regime_classifier is None:
            return None

        try:
            feature_vec = self._extract_svm_features(features)
            if feature_vec is None:
                return None

            # Scale and predict
            X_scaled = self.svm_regime_scaler.transform(feature_vec)
            X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

            proba = self.svm_regime_classifier.predict_proba(X_scaled)[0]
            classes = self.svm_regime_classifier.classes_

            # Map class probabilities back to MarketRegime
            regime_probs = {}
            for regime in MarketRegime:
                idx = regime.value
                class_idx = np.where(classes == self.regimes.index(regime))[0]
                if len(class_idx) > 0:
                    regime_probs[regime] = float(proba[class_idx[0]])
                else:
                    regime_probs[regime] = 0.01  # Small prior for unseen regimes

            # Normalize
            total = sum(regime_probs.values())
            if total > 0:
                regime_probs = {k: v / total for k, v in regime_probs.items()}

            best_regime = max(regime_probs, key=regime_probs.get)
            prob_dict = {r.value: p for r, p in regime_probs.items()}

            return best_regime, prob_dict

        except Exception as e:
            logger.debug(f"SVM regime prediction error: {e}")
            return None

    def detect_regime(self, features: pd.DataFrame) -> Tuple[MarketRegime, Dict[str, float]]:
        """
        Detect current market regime with probabilities.
        Combines rule-based scoring with SVM classification when available.
        """
        if features.empty:
            return MarketRegime.RANGING, {r.value: 1/7 for r in MarketRegime}

        row = features.iloc[-1]

        # ============================================================
        # Rule-based regime scoring (always available)
        # ============================================================
        scores = {}

        # Trending Up
        adx = row.get('adx_14', 0)
        plus_di = row.get('plus_di', 0)
        minus_di = row.get('minus_di', 0)
        if adx > 25 and plus_di > minus_di:
            scores[MarketRegime.TRENDING_UP] = min(adx / 40, 1.0)
        else:
            scores[MarketRegime.TRENDING_UP] = 0.1

        # Trending Down
        if adx > 25 and minus_di > plus_di:
            scores[MarketRegime.TRENDING_DOWN] = min(adx / 40, 1.0)
        else:
            scores[MarketRegime.TRENDING_DOWN] = 0.1

        # Ranging
        bb_width = row.get('bb_width', 0.05)
        if adx < 20 and bb_width < 0.04:
            scores[MarketRegime.RANGING] = max(0.5, 1 - adx / 30)
        else:
            scores[MarketRegime.RANGING] = 0.2

        # Volatile
        volatility = row.get('volatility_20', 0.15)
        vol_ratio = row.get('volatility_ratio', 1.0)
        if volatility > 0.25 or vol_ratio > 1.5:
            scores[MarketRegime.VOLATILE] = min(volatility * 3, 1.0)
        else:
            scores[MarketRegime.VOLATILE] = 0.1

        # Quiet
        volume_ratio = row.get('volume_sma_ratio', 1.0)
        if volatility < 0.10 and volume_ratio < 0.8:
            scores[MarketRegime.QUIET] = max(0.5, 1 - volatility * 5)
        else:
            scores[MarketRegime.QUIET] = 0.1

        # Breakout
        bb_pct = row.get('bb_pct', 0.5)
        if (bb_pct > 1.0 or bb_pct < 0) and volume_ratio > 1.5:
            scores[MarketRegime.BREAKOUT] = 0.8
        else:
            scores[MarketRegime.BREAKOUT] = 0.1

        # Mean Reverting
        rsi = row.get('rsi_14', 50)
        if (bb_pct < 0.1 or bb_pct > 0.9) and (rsi < 30 or rsi > 70):
            scores[MarketRegime.MEAN_REVERTING] = 0.7
        else:
            scores[MarketRegime.MEAN_REVERTING] = 0.2

        # Normalize rule-based to probabilities
        total = sum(scores.values())
        rule_probs = {r.value: s / total for r, s in scores.items()}
        rule_best = max(scores, key=scores.get)

        # ============================================================
        # SVM-based regime prediction (when trained)
        # ============================================================
        svm_result = self._svm_predict_regime(features)

        if svm_result is not None:
            svm_regime, svm_probs = svm_result

            # Combine rule-based and SVM probabilities
            combined_probs = {}
            for regime_val in rule_probs:
                rule_p = rule_probs.get(regime_val, 0)
                svm_p = svm_probs.get(regime_val, 0)
                combined_probs[regime_val] = (
                    self.svm_weight * svm_p + self.rule_weight * rule_p
                )

            # Normalize
            total_combined = sum(combined_probs.values())
            if total_combined > 0:
                combined_probs = {k: v / total_combined for k, v in combined_probs.items()}

            # Find best regime from combined probabilities
            best_val = max(combined_probs, key=combined_probs.get)
            best_regime = None
            for r in MarketRegime:
                if r.value == best_val:
                    best_regime = r
                    break
            if best_regime is None:
                best_regime = rule_best

            # Accumulate data for continued SVM training (use rule-based as label)
            rule_label = self.regimes.index(rule_best)
            self._accumulate_training_data(features, rule_label)

            return best_regime, combined_probs
        else:
            # Only rule-based available
            # Accumulate data for future SVM training
            rule_label = self.regimes.index(rule_best)
            self._accumulate_training_data(features, rule_label)

            return rule_best, rule_probs

    def save_svm_model(self, path: str = "regime_svm_model.joblib") -> bool:
        """Save the trained SVM regime classifier."""
        if not self.svm_regime_trained or not SVM_AVAILABLE:
            return False
        try:
            model_data = {
                'classifier': self.svm_regime_classifier,
                'scaler': self.svm_regime_scaler,
                'feature_keys': self._svm_feature_keys,
            }
            joblib.dump(model_data, path)
            logger.info(f"SVM regime model saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save SVM regime model: {e}")
            return False

    def load_svm_model(self, path: str = "regime_svm_model.joblib") -> bool:
        """Load a trained SVM regime classifier."""
        if not SVM_AVAILABLE:
            return False
        try:
            import os
            if not os.path.exists(path):
                return False
            model_data = joblib.load(path)
            self.svm_regime_classifier = model_data['classifier']
            self.svm_regime_scaler = model_data['scaler']
            self._svm_feature_keys = model_data.get('feature_keys', self._svm_feature_keys)
            self.svm_regime_trained = True
            logger.info(f"SVM regime model loaded from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load SVM regime model: {e}")
            return False


# ============== MAIN BRAIN CLASS ==============

class PropFirmBrainV6:
    """
    PropFirm Brain V6 - Advanced ML/RL/DL Trading System

    Features:
    - Transformer + LSTM hybrid architecture
    - PPO reinforcement learning agent
    - 20+ strategy ensemble
    - Bayesian regime detection
    - Continuous auto-training
    - Real-time signal generation
    """

    def __init__(
        self,
        ruleset: PropFirmRuleset = TPT_50K,
        config: ModelConfig = None,
        db_path: str = "propfirm_brain_v6.db"
    ):
        self.ruleset = ruleset
        self.config = config or ModelConfig()
        self.db_path = db_path

        # Initialize components
        self.feature_engine = FeatureEngine()
        self.strategy_ensemble = StrategyEnsemble()
        self.regime_detector = BayesianRegimeDetector()

        # ML components
        self.device = 'cuda' if TORCH_AVAILABLE and torch.cuda.is_available() else 'cpu'
        if TORCH_AVAILABLE:
            self.model = TradingTransformer(self.config).to(self.device)
            self.ppo_agent = PPOAgent(self.config, self.device)
            self.optimizer = AdamW(
                self.model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay
            )
        else:
            self.model = None
            self.ppo_agent = None
            self.optimizer = None

        # State tracking
        self.trade_history: List[TradeRecord] = []
        self.current_regime = MarketRegime.RANGING
        self.regime_probs: Dict[str, float] = {}
        self.last_signal: Dict[str, Any] = {}
        self.is_trained = False
        self.training_step = 0
        self.total_trades_seen = 0

        # Auto-training
        self.auto_train_enabled = True
        self.last_train_time = datetime.now()
        self._training_thread: Optional[threading.Thread] = None
        self._stop_training = threading.Event()

        # Model version tracking
        self._model_version: Optional[str] = None
        self._feature_schema_hash = self.feature_engine.schema_hash

        # Model drift detection
        self.drift_detector = DriftDetector(
            reference_window=1000,
            test_window=200,
            psi_threshold=0.25,
            ks_threshold=0.1,
            confidence_threshold=0.15
        )

        # Signal history for API access
        self.signal_history: List[Dict[str, Any]] = []

        # Initialize database and try to load saved model
        self._init_db()

        logger.info(f"PropFirmBrainV6 initialized | Device: {self.device} | Rules: {ruleset.name}")

    def _compute_model_hash(self) -> str:
        """
        Compute SHA256 hash of model weights for version tracking.
        Matches quant-platform pattern.
        """
        if not TORCH_AVAILABLE or self.model is None:
            return "no_model"

        try:
            data = b''
            for param in self.model.parameters():
                data += param.detach().cpu().numpy().tobytes()
            return hashlib.sha256(data).hexdigest()[:12]
        except Exception as e:
            logger.debug(f"Model hash error: {e}")
            return "hash_error"

    @property
    def model_version(self) -> str:
        """Get current model version hash."""
        if self._model_version is None:
            self._model_version = self._compute_model_hash()
        return self._model_version

    def _invalidate_model_version(self):
        """Call after training to update version."""
        self._model_version = None

    def _init_db(self):
        """Initialize SQLite database for persistence"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                entry_time TEXT,
                exit_time TEXT,
                contracts INTEGER,
                pnl REAL,
                pnl_pct REAL,
                strategy TEXT,
                confidence REAL,
                regime TEXT,
                exit_reason TEXT,
                features TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epoch INTEGER,
                loss REAL,
                accuracy REAL,
                weights BLOB,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step INTEGER,
                loss REAL,
                policy_loss REAL,
                value_loss REAL,
                regime TEXT,
                trades_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

        # Load trade history from database for continued learning
        self._load_trade_history()

        # Try to load saved model on initialization
        self._try_load_model()

    def _load_trade_history(self):
        """Load trade history from database so brain can resume learning after restart."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, symbol, direction, entry_price, exit_price,
                       entry_time, exit_time, contracts, pnl, pnl_pct,
                       strategy, confidence, regime, exit_reason, features
                FROM trades ORDER BY created_at DESC LIMIT 500
            """)
            rows = cursor.fetchall()
            conn.close()

            for row in reversed(rows):  # oldest first
                try:
                    features = json.loads(row['features']) if row['features'] else {}
                    regime_str = row['regime'] or 'ranging'
                    regime = MarketRegime(regime_str) if regime_str in [r.value for r in MarketRegime] else MarketRegime.RANGING

                    trade = TradeRecord(
                        trade_id=row['id'],
                        symbol=row['symbol'] or '',
                        direction=row['direction'] or 'long',
                        entry_price=row['entry_price'] or 0,
                        exit_price=row['exit_price'] or 0,
                        entry_time=datetime.fromisoformat(row['entry_time']) if row['entry_time'] else datetime.now(),
                        exit_time=datetime.fromisoformat(row['exit_time']) if row['exit_time'] else datetime.now(),
                        contracts=row['contracts'] or 1,
                        pnl=row['pnl'] or 0,
                        pnl_pct=row['pnl_pct'] or 0,
                        strategy=row['strategy'] or 'unknown',
                        confidence=row['confidence'] or 0.5,
                        regime=regime,
                        exit_reason=row['exit_reason'] or 'unknown',
                        features=features
                    )
                    self.trade_history.append(trade)

                    # Update strategy performance from loaded trades
                    self.strategy_ensemble.update_strategy_performance(trade.strategy, trade.pnl)
                except Exception as e:
                    logger.debug(f"Error loading trade record: {e}")
                    continue

            if self.trade_history:
                self.total_trades_seen = len(self.trade_history)
                logger.info(f"Loaded {len(self.trade_history)} trades from database for continued learning")

        except Exception as e:
            logger.debug(f"Could not load trade history: {e}")

    def save_model(self, path: str = None) -> bool:
        """
        Save model weights to file.

        Args:
            path: Path to save weights (defaults to 'brain_v6_weights.pt')

        Returns:
            True if save successful
        """
        if not TORCH_AVAILABLE or self.model is None:
            logger.warning("Cannot save model: PyTorch not available or model not initialized")
            return False

        path = path or "brain_v6_weights.pt"

        try:
            checkpoint = {
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict() if self.optimizer else None,
                'training_step': self.training_step,
                'is_trained': self.is_trained,
                'total_trades_seen': self.total_trades_seen,
                'model_version': self.model_version,
                'feature_schema_hash': self._feature_schema_hash,
                'config': {
                    'input_dim': self.config.input_dim,
                    'hidden_dim': self.config.hidden_dim,
                    'num_heads': self.config.num_heads,
                    'num_layers': self.config.num_layers,
                },
                'saved_at': datetime.now().isoformat()
            }

            torch.save(checkpoint, path)
            logger.info(f"Model saved to {path} | Version: {self.model_version}")

            # Also save SVM regime classifier if trained
            if self.regime_detector.svm_regime_trained:
                svm_path = path.replace('.pt', '_regime_svm.joblib') if path.endswith('.pt') else path + '_regime_svm.joblib'
                self.regime_detector.save_svm_model(svm_path)

            return True

        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            return False

    def load_model(self, path: str = None) -> bool:
        """
        Load model weights from file.

        Args:
            path: Path to load weights from (defaults to 'brain_v6_weights.pt')

        Returns:
            True if load successful
        """
        if not TORCH_AVAILABLE or self.model is None:
            logger.warning("Cannot load model: PyTorch not available or model not initialized")
            return False

        path = path or "brain_v6_weights.pt"

        try:
            import os
            if not os.path.exists(path):
                logger.debug(f"Model file not found: {path}")
                return False

            checkpoint = torch.load(path, map_location=self.device)

            # Check schema compatibility
            saved_schema = checkpoint.get('feature_schema_hash')
            if saved_schema and saved_schema != self._feature_schema_hash:
                logger.warning(f"Feature schema mismatch: saved={saved_schema}, current={self._feature_schema_hash}")
                logger.warning("Model may not work correctly - consider retraining")

            # Load model state
            self.model.load_state_dict(checkpoint['model_state_dict'])

            # Load optimizer state if available
            if checkpoint.get('optimizer_state_dict') and self.optimizer:
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

            # Restore training state
            self.training_step = checkpoint.get('training_step', 0)
            self.is_trained = checkpoint.get('is_trained', True)
            self.total_trades_seen = checkpoint.get('total_trades_seen', 0)
            self._model_version = checkpoint.get('model_version')

            logger.info(f"Model loaded from {path} | Version: {self.model_version} | Steps: {self.training_step}")

            # Also try to load SVM regime classifier
            svm_path = path.replace('.pt', '_regime_svm.joblib') if path.endswith('.pt') else path + '_regime_svm.joblib'
            self.regime_detector.load_svm_model(svm_path)
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def _try_load_model(self):
        """Try to load model on initialization."""
        # Try standard paths
        paths_to_try = [
            "brain_v6_weights.pt",
            "weights/brain_v6_weights.pt",
            "models/brain_v6_weights.pt",
        ]

        for path in paths_to_try:
            if self.load_model(path):
                return

        logger.info("No pre-trained model found - will train from scratch")

    def save_checkpoint_to_db(self) -> bool:
        """Save model checkpoint to database."""
        if not TORCH_AVAILABLE or self.model is None:
            return False

        try:
            import pickle

            weights_blob = pickle.dumps(self.model.state_dict())

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO model_checkpoints (epoch, loss, accuracy, weights)
                VALUES (?, ?, ?, ?)
            """, (self.training_step, 0.0, 0.0, weights_blob))

            conn.commit()
            conn.close()

            logger.info(f"Checkpoint saved to database | Step: {self.training_step}")
            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint to DB: {e}")
            return False

    def load_checkpoint_from_db(self) -> bool:
        """Load latest model checkpoint from database."""
        if not TORCH_AVAILABLE or self.model is None:
            return False

        try:
            import pickle

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT epoch, weights FROM model_checkpoints
                ORDER BY id DESC LIMIT 1
            """)

            row = cursor.fetchone()
            conn.close()

            if not row:
                return False

            epoch, weights_blob = row
            state_dict = pickle.loads(weights_blob)
            self.model.load_state_dict(state_dict)
            self.training_step = epoch
            self.is_trained = True

            logger.info(f"Checkpoint loaded from database | Step: {epoch}")
            return True

        except Exception as e:
            logger.error(f"Failed to load checkpoint from DB: {e}")
            return False

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str = "ES"
    ) -> Dict[str, Any]:
        """
        Generate trading signal from market data

        Args:
            df: OHLCV DataFrame with columns [open, high, low, close, volume]
            symbol: Trading symbol

        Returns:
            Signal dictionary with direction, confidence, regime, etc.
        """
        if df is None or len(df) < 50:
            return {
                'direction': 'HOLD',
                'signal': 0,
                'confidence': 0,
                'regime': 'ranging',
                'error': 'Insufficient data'
            }

        # Calculate features
        features = self.feature_engine.calculate_features(df)
        if features.empty:
            return {
                'direction': 'HOLD',
                'signal': 0,
                'confidence': 0,
                'regime': 'ranging',
                'error': 'Feature calculation failed'
            }

        # Detect regime
        self.current_regime, self.regime_probs = self.regime_detector.detect_regime(features)

        # Get ML signal if model is trained
        ml_signal = None
        if TORCH_AVAILABLE and self.is_trained:
            try:
                # Prepare input tensor
                feature_values = self.feature_engine.normalize_features(features)
                if len(feature_values) >= 20:
                    x = torch.tensor(feature_values[-20:], dtype=torch.float32)
                    x = x.unsqueeze(0).to(self.device)

                    with torch.no_grad():
                        output = self.model(x)
                        signal_probs = F.softmax(output['signal_logits'], dim=-1)
                        ml_sig = signal_probs.argmax(dim=-1).item() - 2
                        ml_conf = output['confidence'].item()
                        ml_signal = (ml_sig, ml_conf)
            except Exception as e:
                logger.warning(f"ML signal error: {e}")

        # Generate ensemble signal
        ensemble_result = self.strategy_ensemble.generate_ensemble_signal(features, ml_signal)

        # Calculate stop loss and take profit
        atr = features['atr_14'].iloc[-1] if 'atr_14' in features else 0
        current_price = df['close'].iloc[-1]

        if ensemble_result['direction'] in ['BUY', 'STRONG_BUY']:
            stop_loss = current_price - 2 * atr
            take_profit = current_price + 4 * atr
        elif ensemble_result['direction'] in ['SELL', 'STRONG_SELL']:
            stop_loss = current_price + 2 * atr
            take_profit = current_price - 4 * atr
        else:
            stop_loss = None
            take_profit = None

        # Apply regime-based confidence adjustment for safety
        raw_confidence = ensemble_result['confidence']
        regime_modifier = REGIME_CONFIDENCE_MODIFIERS.get(self.current_regime, 0.5)
        adjusted_confidence = raw_confidence * regime_modifier

        # SAFETY: Force HOLD if regime is UNKNOWN and confidence is below threshold
        final_direction = ensemble_result['direction']
        if self.current_regime == MarketRegime.UNKNOWN and adjusted_confidence < 0.5:
            logger.warning(f"[REGIME SAFETY] Forcing HOLD - regime UNKNOWN with low confidence {adjusted_confidence:.2f}")
            final_direction = 'HOLD'
            adjusted_confidence = 0.0

        # Build final signal
        signal = {
            'symbol': symbol,
            'direction': final_direction,
            'signal': ensemble_result['signal'] if final_direction != 'HOLD' else 0,
            'confidence': adjusted_confidence,
            'raw_confidence': raw_confidence,
            'regime_modifier': regime_modifier,
            'regime': self.current_regime.value,
            'regime_probs': self.regime_probs,
            'strategy_votes': ensemble_result['strategy_votes'],
            'agreeing_strategies': ensemble_result['agreeing_strategies'],
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'atr': atr,
            'current_price': current_price,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model_trained': self.is_trained,
            'training_step': self.training_step,
            'ml_signal': ml_signal
        }

        self.last_signal = signal
        self.signal_history.append(signal)
        # Keep signal history bounded
        if len(self.signal_history) > 500:
            self.signal_history = self.signal_history[-500:]

        # Record prediction for drift monitoring
        try:
            if len(features) > 0:
                feature_array = self.feature_engine.normalize_features(features)
                if len(feature_array) > 0:
                    self.drift_detector.record_prediction(
                        features=feature_array[-1] if len(feature_array.shape) == 2 else feature_array,
                        prediction=float(ensemble_result['signal']),
                        confidence=adjusted_confidence
                    )
        except Exception as e:
            logger.debug(f"Drift recording error: {e}")

        return signal

    def check_model_drift(self) -> Dict[str, Any]:
        """
        Check for model drift and return status.
        Should be called periodically (e.g., every 100 predictions).
        """
        metrics = self.drift_detector.check_drift()
        summary = self.drift_detector.get_drift_summary()

        # Add model info
        summary['model_version'] = self.model_version
        summary['feature_schema_hash'] = self._feature_schema_hash
        summary['is_trained'] = self.is_trained
        summary['training_step'] = self.training_step

        return summary

    def train_step(self, trades: List[TradeRecord] = None) -> Dict[str, Any]:
        """
        Perform one training step on trade data

        Args:
            trades: List of trade records to train on

        Returns:
            Training metrics
        """
        if not TORCH_AVAILABLE:
            return {'error': 'PyTorch not available'}

        if trades is None:
            trades = self.trade_history

        if len(trades) < self.config.min_trades_for_training:
            return {'error': 'Insufficient trades for training', 'trades': len(trades)}

        try:
            # Prepare training data
            X_list = []
            y_signals = []
            y_regimes = []

            for trade in trades:
                if trade.features:
                    features = pd.DataFrame([trade.features])
                    normalized = self.feature_engine.normalize_features(features)
                    X_list.append(normalized[0])

                    # Target: whether trade was profitable
                    if trade.pnl > 0:
                        y_signals.append(2 if trade.direction == 'long' else 0)
                    else:
                        y_signals.append(0 if trade.direction == 'long' else 2)

                    y_regimes.append(list(MarketRegime).index(trade.regime))

            if len(X_list) < 10:
                return {'error': 'Insufficient feature data'}

            # Create tensors
            X = torch.tensor(np.array(X_list), dtype=torch.float32).unsqueeze(1)
            y_sig = torch.tensor(y_signals, dtype=torch.long)
            y_reg = torch.tensor(y_regimes, dtype=torch.long)

            # Create dataloader
            dataset = TensorDataset(X, y_sig, y_reg)
            loader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)

            # Training loop
            self.model.train()
            total_loss = 0
            num_batches = 0

            for batch_x, batch_y_sig, batch_y_reg in loader:
                batch_x = batch_x.to(self.device)
                batch_y_sig = batch_y_sig.to(self.device)
                batch_y_reg = batch_y_reg.to(self.device)

                self.optimizer.zero_grad()

                output = self.model(batch_x)

                # Multi-task loss
                signal_loss = F.cross_entropy(output['signal_logits'], batch_y_sig)
                regime_loss = F.cross_entropy(output['regime_logits'], batch_y_reg)

                loss = signal_loss + 0.3 * regime_loss

                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.gradient_clip
                )
                self.optimizer.step()

                total_loss += loss.item()
                num_batches += 1

            avg_loss = total_loss / num_batches if num_batches > 0 else 0

            self.training_step += 1
            self.is_trained = True
            self.last_train_time = datetime.now()
            self.total_trades_seen = len(trades)

            # Invalidate model version hash after training
            self._invalidate_model_version()

            # Reset drift detector after retraining
            self.drift_detector.reset()

            # Log training
            self._log_training(avg_loss)

            # Auto-save model after training
            if self.training_step % 10 == 0:  # Save every 10 steps
                self.save_model()
                self.save_checkpoint_to_db()

            return {
                'loss': avg_loss,
                'step': self.training_step,
                'trades_trained': len(trades),
                'timestamp': self.last_train_time.isoformat(),
                'model_version': self.model_version,
                'feature_schema': self._feature_schema_hash
            }

        except Exception as e:
            logger.error(f"Training error: {e}")
            return {'error': str(e)}

    def _log_training(self, loss: float):
        """Log training metrics to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO training_logs (step, loss, regime, trades_count)
                VALUES (?, ?, ?, ?)
            """, (self.training_step, loss, self.current_regime.value, len(self.trade_history)))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to log training: {e}")

    def record_trade(self, trade: TradeRecord) -> Dict[str, Any]:
        """Record a completed trade for learning"""
        self.trade_history.append(trade)

        # Update strategy performance
        self.strategy_ensemble.update_strategy_performance(trade.strategy, trade.pnl)

        # Persist to database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (id, symbol, direction, entry_price, exit_price,
                                   entry_time, exit_time, contracts, pnl, pnl_pct,
                                   strategy, confidence, regime, exit_reason, features)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id, trade.symbol, trade.direction,
                trade.entry_price, trade.exit_price,
                trade.entry_time.isoformat(), trade.exit_time.isoformat(),
                trade.contracts, trade.pnl, trade.pnl_pct,
                trade.strategy, trade.confidence, trade.regime.value,
                trade.exit_reason, json.dumps(trade.features)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to save trade: {e}")

        # Update RL agent if available
        if self.ppo_agent and trade.features:
            try:
                features = pd.DataFrame([trade.features])
                normalized = self.feature_engine.normalize_features(features)
                state = torch.tensor(normalized, dtype=torch.float32)

                # Reward shaping
                reward = self._calculate_reward(trade)
                action = 2 if trade.direction == 'long' else 0
                done = True

                self.ppo_agent.store_transition(
                    state, action, reward, 0, 0, done
                )
            except Exception as e:
                logger.warning(f"RL update error: {e}")

        return {
            'recorded': True,
            'trade_id': trade.trade_id,
            'total_trades': len(self.trade_history)
        }

    def _calculate_reward(self, trade: TradeRecord) -> float:
        """Calculate shaped reward for RL"""
        reward = 0

        # Base reward from PnL
        reward += trade.pnl / 100  # Scale PnL

        # Bonus for winning trades
        if trade.is_winner:
            reward += 0.5
        else:
            reward -= 0.3  # Smaller penalty for losses

        # Bonus for good R-multiple
        if trade.r_multiple > 0.02:  # 2% gain
            reward += 0.3
        elif trade.r_multiple < -0.01:  # 1% loss
            reward -= 0.2

        # Regime-appropriate trades
        if trade.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            if trade.strategy in ['TrendFollowing', 'Breakout']:
                reward += 0.2
        elif trade.regime == MarketRegime.MEAN_REVERTING:
            if trade.strategy == 'MeanReversion':
                reward += 0.2

        return reward

    def get_status(self) -> Dict[str, Any]:
        """Get brain status and metrics"""
        # Calculate performance metrics
        if self.trade_history:
            wins = [t for t in self.trade_history if t.is_winner]
            win_rate = len(wins) / len(self.trade_history)
            total_pnl = sum(t.pnl for t in self.trade_history)
            avg_pnl = total_pnl / len(self.trade_history)

            winning_pnl = [t.pnl for t in wins] if wins else [0]
            losing_pnl = [t.pnl for t in self.trade_history if not t.is_winner] or [0]
            profit_factor = abs(sum(winning_pnl)) / abs(sum(losing_pnl)) if sum(losing_pnl) != 0 else 0
        else:
            win_rate = 0
            total_pnl = 0
            avg_pnl = 0
            profit_factor = 0

        # SVM regime classifier info
        svm_regime_info = {
            'available': SVM_AVAILABLE,
            'trained': self.regime_detector.svm_regime_trained,
            'training_samples': len(self.regime_detector._regime_feature_buffer),
        }
        if self.regime_detector.svm_regime_trained and self.regime_detector.svm_regime_classifier is not None:
            try:
                svm_regime_info['support_vectors'] = int(sum(self.regime_detector.svm_regime_classifier.n_support_))
                svm_regime_info['classes'] = self.regime_detector.svm_regime_classifier.classes_.tolist()
            except Exception:
                pass

        return {
            'version': '6.0.0',
            'ruleset': self.ruleset.name,
            'device': self.device,
            'is_trained': self.is_trained,
            'training_step': self.training_step,
            'total_trades': len(self.trade_history),
            'current_regime': self.current_regime.value,
            'regime_probs': self.regime_probs,
            'svm_regime_classifier': svm_regime_info,
            'metrics': {
                'win_rate': round(win_rate, 3),
                'total_pnl': round(total_pnl, 2),
                'avg_pnl': round(avg_pnl, 2),
                'profit_factor': round(profit_factor, 2),
            },
            'last_signal': self.last_signal,
            'last_train_time': self.last_train_time.isoformat() if self.last_train_time else None,
            'auto_train_enabled': self.auto_train_enabled,
            'strategies': [
                {
                    'name': s.name,
                    'weight': s.weight,
                    'win_rate': round(s.win_rate, 3),
                    'trades': s.total_trades,
                    'pnl': round(s.total_pnl, 2)
                }
                for s in self.strategy_ensemble.strategies
            ]
        }

    def start_auto_training(self):
        """Start background auto-training thread"""
        if self._training_thread is not None and self._training_thread.is_alive():
            return

        self._stop_training.clear()
        self._training_thread = threading.Thread(target=self._auto_train_loop, daemon=True)
        self._training_thread.start()
        logger.info("Auto-training started")

    def stop_auto_training(self):
        """Stop background auto-training"""
        self._stop_training.set()
        if self._training_thread:
            self._training_thread.join(timeout=5)
        logger.info("Auto-training stopped")

    def _auto_train_loop(self):
        """Background training loop"""
        while not self._stop_training.is_set():
            try:
                # Check if enough time has passed
                elapsed = (datetime.now() - self.last_train_time).total_seconds()
                if elapsed >= self.config.auto_train_interval:
                    if len(self.trade_history) >= self.config.min_trades_for_training:
                        result = self.train_step()
                        logger.info(f"Auto-train: {result}")

                        # Also update PPO agent
                        if self.ppo_agent and len(self.ppo_agent.states) >= self.config.batch_size:
                            ppo_result = self.ppo_agent.update()
                            logger.info(f"PPO update: {ppo_result}")
            except Exception as e:
                logger.error(f"Auto-train error: {e}")

            time.sleep(10)  # Check every 10 seconds


# ============== SINGLETON ACCESS ==============

_brain_instance: Optional[PropFirmBrainV6] = None

def get_propfirm_brain_v6(
    ruleset: PropFirmRuleset = TPT_50K,
    config: ModelConfig = None
) -> PropFirmBrainV6:
    """Get or create PropFirmBrainV6 singleton"""
    global _brain_instance
    if _brain_instance is None:
        _brain_instance = PropFirmBrainV6(ruleset=ruleset, config=config)
    return _brain_instance
