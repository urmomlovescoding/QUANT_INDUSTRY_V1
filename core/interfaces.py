"""
QUANT_INDUSTRY_V1 Core Interfaces

Abstract base classes defining the contracts for all major subsystems.
Implementations must adhere to these interfaces for proper integration.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd

from .types import (
    Symbol, Timeframe, Signal, Direction, Regime,
    MarketData, FeatureVector, Prediction, ExecutionResult, RiskAssessment
)


class DataProvider(ABC):
    """
    Interface for market data providers.

    Implementations should handle:
    - Data fetching from various sources
    - Caching and rate limiting
    - Data validation and quality checks
    - Fallback mechanisms
    """

    @abstractmethod
    def fetch(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: Optional[datetime] = None
    ) -> MarketData:
        """
        Fetch market data for a symbol.

        Args:
            symbol: The trading symbol
            timeframe: Data timeframe (e.g., '1d', '1h')
            start: Start datetime
            end: End datetime (default: now)

        Returns:
            MarketData object with OHLCV data

        Raises:
            DataError: If data cannot be fetched
        """
        pass

    @abstractmethod
    def get_latest(self, symbol: Symbol, timeframe: Timeframe) -> MarketData:
        """
        Get the most recent data for a symbol.

        Args:
            symbol: The trading symbol
            timeframe: Data timeframe

        Returns:
            MarketData with latest bar
        """
        pass

    @abstractmethod
    def validate(self, data: MarketData) -> Tuple[bool, List[str]]:
        """
        Validate market data quality.

        Args:
            data: MarketData to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        pass

    @abstractmethod
    def get_data_freshness(self, symbol: Symbol, timeframe: Timeframe) -> float:
        """
        Get seconds since last data update.

        Args:
            symbol: The trading symbol
            timeframe: Data timeframe

        Returns:
            Seconds since last update
        """
        pass


class FeatureComputer(ABC):
    """
    Interface for feature computation engines.

    Implementations should handle:
    - Technical indicator calculation
    - Feature normalization/scaling
    - Feature validation
    - Reproducible feature hashing
    """

    @abstractmethod
    def compute(
        self,
        data: MarketData,
        feature_names: Optional[List[str]] = None
    ) -> FeatureVector:
        """
        Compute features from market data.

        Args:
            data: MarketData input
            feature_names: Optional list of specific features to compute

        Returns:
            FeatureVector with computed features
        """
        pass

    @abstractmethod
    def get_feature_names(self) -> List[str]:
        """Get list of all supported feature names."""
        pass

    @abstractmethod
    def get_feature_hash(self, features: FeatureVector) -> str:
        """
        Get reproducible hash of feature configuration.

        Args:
            features: Computed features

        Returns:
            16-character hex hash
        """
        pass


class ModelTrainer(ABC):
    """
    Interface for model training.

    Implementations should handle:
    - Training data preparation
    - Model fitting
    - Hyperparameter optimization
    - Model persistence
    """

    @abstractmethod
    def train(
        self,
        features: List[FeatureVector],
        labels: List[Any],
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Train a model.

        Args:
            features: List of feature vectors
            labels: Corresponding labels
            config: Training configuration

        Returns:
            Model ID of trained model
        """
        pass

    @abstractmethod
    def evaluate(
        self,
        model_id: str,
        features: List[FeatureVector],
        labels: List[Any]
    ) -> Dict[str, float]:
        """
        Evaluate a trained model.

        Args:
            model_id: ID of model to evaluate
            features: Test features
            labels: Test labels

        Returns:
            Dictionary of metric names to values
        """
        pass

    @abstractmethod
    def save(self, model_id: str, path: str) -> None:
        """Save model to disk."""
        pass

    @abstractmethod
    def load(self, path: str) -> str:
        """Load model from disk. Returns model ID."""
        pass


class ModelPredictor(ABC):
    """
    Interface for model prediction/inference.

    Implementations should handle:
    - Efficient inference
    - Batch prediction
    - Confidence estimation
    - Prediction caching
    """

    @abstractmethod
    def predict(
        self,
        model_id: str,
        features: FeatureVector
    ) -> Prediction:
        """
        Generate prediction from features.

        Args:
            model_id: ID of model to use
            features: Input features

        Returns:
            Prediction with direction, strength, and confidence
        """
        pass

    @abstractmethod
    def predict_batch(
        self,
        model_id: str,
        features_list: List[FeatureVector]
    ) -> List[Prediction]:
        """
        Batch prediction for efficiency.

        Args:
            model_id: ID of model to use
            features_list: List of feature vectors

        Returns:
            List of predictions
        """
        pass

    @abstractmethod
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get metadata about a model."""
        pass


class SignalGenerator(ABC):
    """
    Interface for trading signal generation.

    Implementations should handle:
    - Multi-model ensemble
    - Regime-aware signal generation
    - Confidence calibration
    - Signal explanation
    """

    @abstractmethod
    def generate(
        self,
        symbol: Symbol,
        features: FeatureVector,
        regime: Optional[Regime] = None
    ) -> Signal:
        """
        Generate trading signal for a symbol.

        Args:
            symbol: Trading symbol
            features: Computed features
            regime: Current market regime (optional)

        Returns:
            Signal with direction, strength, confidence, and explanation
        """
        pass

    @abstractmethod
    def generate_batch(
        self,
        symbols: List[Symbol],
        features_list: List[FeatureVector],
        regime: Optional[Regime] = None
    ) -> List[Signal]:
        """
        Generate signals for multiple symbols.

        Args:
            symbols: List of symbols
            features_list: List of feature vectors (one per symbol)
            regime: Current market regime

        Returns:
            List of signals
        """
        pass

    @abstractmethod
    def get_active_models(self) -> List[str]:
        """Get list of active model IDs used for generation."""
        pass


class Executor(ABC):
    """
    Interface for order execution.

    Implementations should handle:
    - Order placement
    - Order management (cancel, replace)
    - Fill tracking
    - Slippage estimation
    """

    @abstractmethod
    def execute(self, signal: Signal, position_size: float) -> ExecutionResult:
        """
        Execute a trading signal.

        Args:
            signal: Trading signal
            position_size: Size to trade (shares or dollars)

        Returns:
            ExecutionResult with fill details
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: ID of order to cancel

        Returns:
            True if cancelled, False otherwise
        """
        pass

    @abstractmethod
    def get_positions(self) -> Dict[Symbol, float]:
        """
        Get current positions.

        Returns:
            Dictionary of symbol -> quantity
        """
        pass

    @abstractmethod
    def get_account(self) -> Dict[str, float]:
        """
        Get account information.

        Returns:
            Dictionary with cash, equity, buying_power, etc.
        """
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        pass


class RiskManager(ABC):
    """
    Interface for risk management.

    Implementations should handle:
    - Pre-trade risk checks
    - Position sizing
    - Exposure limits
    - Drawdown monitoring
    - Kill switch
    """

    @abstractmethod
    def check_pre_trade(
        self,
        signal: Signal,
        proposed_size: float
    ) -> RiskAssessment:
        """
        Perform pre-trade risk check.

        Args:
            signal: Proposed trading signal
            proposed_size: Proposed position size

        Returns:
            RiskAssessment with approval status and any adjustments
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        signal: Signal,
        account_equity: float
    ) -> float:
        """
        Calculate appropriate position size.

        Args:
            signal: Trading signal
            account_equity: Current account equity

        Returns:
            Recommended position size (shares or dollars)
        """
        pass

    @abstractmethod
    def get_current_exposure(self) -> Dict[str, float]:
        """
        Get current risk exposure metrics.

        Returns:
            Dictionary with gross_exposure, net_exposure, var, etc.
        """
        pass

    @abstractmethod
    def check_kill_switch(self) -> Tuple[bool, Optional[str]]:
        """
        Check if kill switch should be triggered.

        Returns:
            Tuple of (should_kill, reason)
        """
        pass

    @abstractmethod
    def update_metrics(self) -> None:
        """Update risk metrics based on current positions and market data."""
        pass


class RegimeDetector(ABC):
    """
    Interface for market regime detection.

    Implementations should handle:
    - Regime classification
    - Regime transition detection
    - Regime stability assessment
    """

    @abstractmethod
    def detect(self, features: FeatureVector) -> Regime:
        """
        Detect current market regime.

        Args:
            features: Market features

        Returns:
            Detected regime
        """
        pass

    @abstractmethod
    def get_regime_probabilities(self, features: FeatureVector) -> Dict[Regime, float]:
        """
        Get probability distribution over regimes.

        Args:
            features: Market features

        Returns:
            Dictionary of regime -> probability
        """
        pass

    @abstractmethod
    def get_regime_history(self, n: int = 10) -> List[Regime]:
        """Get recent regime history."""
        pass


class HealthChecker(ABC):
    """
    Interface for system health monitoring.

    Implementations should handle:
    - Component health checks
    - Performance monitoring
    - Alert generation
    """

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Dictionary with component health statuses
        """
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, float]:
        """
        Get current performance metrics.

        Returns:
            Dictionary of metric name -> value
        """
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Quick check if system is healthy."""
        pass
