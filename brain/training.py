"""
QUANT_INDUSTRY_V1 Model Training Pipeline

Handles model training, validation, and selection:
- Walk-forward validation
- Time-series cross-validation
- Hyperparameter tuning
- Model selection
- Performance tracking

Rollback Plan: Delete this file
Tests Required: Cross-validation, model persistence
Failure Modes: Fall back to default models
"""

import numpy as np
import logging
import json
import pickle
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import sqlite3

logger = logging.getLogger(__name__)


# =============================================================================
# TRAINING TYPES
# =============================================================================

class ValidationMethod(Enum):
    """Validation method for time series."""
    HOLDOUT = "holdout"
    WALK_FORWARD = "walk_forward"
    TIME_SERIES_CV = "time_series_cv"
    EXPANDING_WINDOW = "expanding_window"


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    validation_method: ValidationMethod = ValidationMethod.WALK_FORWARD
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15
    n_folds: int = 5
    min_train_samples: int = 252  # ~1 year of daily data
    walk_forward_step: int = 21  # ~1 month
    purge_window: int = 5  # Days to purge between train/test
    embargo_window: int = 5  # Days to embargo after test
    early_stopping_rounds: int = 50
    random_state: int = 42


@dataclass
class TrainingMetrics:
    """Metrics from a training run."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    information_ratio: float = 0.0
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, float]:
        result = {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'information_ratio': self.information_ratio,
        }
        result.update(self.custom_metrics)
        return result


@dataclass
class TrainingResult:
    """Result from model training."""
    model_id: str
    model_type: str
    trained_at: datetime
    config: Dict[str, Any]
    train_metrics: TrainingMetrics
    validation_metrics: TrainingMetrics
    test_metrics: Optional[TrainingMetrics] = None
    feature_importance: Dict[str, float] = field(default_factory=dict)
    training_duration_seconds: float = 0.0
    samples_used: int = 0
    model_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_id': self.model_id,
            'model_type': self.model_type,
            'trained_at': self.trained_at.isoformat(),
            'config': self.config,
            'train_metrics': self.train_metrics.to_dict(),
            'validation_metrics': self.validation_metrics.to_dict(),
            'test_metrics': self.test_metrics.to_dict() if self.test_metrics else None,
            'feature_importance': self.feature_importance,
            'training_duration_seconds': self.training_duration_seconds,
            'samples_used': self.samples_used,
            'model_path': self.model_path,
        }


# =============================================================================
# TIME SERIES SPLIT
# =============================================================================

class TimeSeriesSplitter:
    """
    Time series cross-validation splitter.

    Ensures temporal ordering and prevents data leakage.
    """

    def __init__(self, config: TrainingConfig):
        self.config = config

    def split_holdout(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]]:
        """
        Simple holdout split maintaining temporal order.

        Returns:
            Tuple of (train, validation, test) each as (X, y) tuple
        """
        n = len(X)

        train_end = int(n * self.config.train_ratio)
        val_end = train_end + int(n * self.config.validation_ratio)

        # Apply purge and embargo
        train_end -= self.config.purge_window
        val_start = train_end + self.config.purge_window
        val_end_adj = val_end - self.config.embargo_window
        test_start = val_end + self.config.embargo_window

        train = (X[:train_end], y[:train_end])
        val = (X[val_start:val_end_adj], y[val_start:val_end_adj])
        test = (X[test_start:], y[test_start:])

        return train, val, test

    def walk_forward_splits(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> List[Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]]]:
        """
        Generate walk-forward validation splits.

        Returns:
            List of (train, test) tuples
        """
        n = len(X)
        min_train = self.config.min_train_samples
        step = self.config.walk_forward_step

        splits = []
        train_end = min_train

        while train_end + step <= n:
            # Apply purge
            actual_train_end = train_end - self.config.purge_window
            test_start = train_end + self.config.purge_window
            test_end = min(train_end + step, n)

            if actual_train_end > 0 and test_start < n:
                train = (X[:actual_train_end], y[:actual_train_end])
                test = (X[test_start:test_end], y[test_start:test_end])
                splits.append((train, test))

            train_end += step

        return splits

    def time_series_cv_splits(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> List[Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]]]:
        """
        Generate time series cross-validation splits.

        Each fold uses all prior data for training.
        """
        n = len(X)
        n_folds = self.config.n_folds
        fold_size = (n - self.config.min_train_samples) // n_folds

        splits = []

        for i in range(n_folds):
            train_end = self.config.min_train_samples + i * fold_size
            test_start = train_end + self.config.purge_window
            test_end = train_end + fold_size

            if test_start < n and test_end <= n:
                train = (X[:train_end - self.config.purge_window], y[:train_end - self.config.purge_window])
                test = (X[test_start:test_end], y[test_start:test_end])
                splits.append((train, test))

        return splits


# =============================================================================
# METRICS CALCULATOR
# =============================================================================

class MetricsCalculator:
    """Calculate training and trading metrics."""

    @staticmethod
    def calculate_classification_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: Optional[np.ndarray] = None
    ) -> TrainingMetrics:
        """Calculate classification metrics."""
        metrics = TrainingMetrics()

        # Accuracy
        metrics.accuracy = float(np.mean(y_true == y_pred))

        # Per-class metrics (simplified for binary/ternary)
        unique_classes = np.unique(y_true)

        if len(unique_classes) == 2:
            # Binary classification
            tp = np.sum((y_true == 1) & (y_pred == 1))
            fp = np.sum((y_true == 0) & (y_pred == 1))
            fn = np.sum((y_true == 1) & (y_pred == 0))

            metrics.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            metrics.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

            if metrics.precision + metrics.recall > 0:
                metrics.f1_score = 2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall)

        else:
            # Multi-class: macro average
            precisions, recalls, f1s = [], [], []

            for cls in unique_classes:
                tp = np.sum((y_true == cls) & (y_pred == cls))
                fp = np.sum((y_true != cls) & (y_pred == cls))
                fn = np.sum((y_true == cls) & (y_pred != cls))

                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

                precisions.append(prec)
                recalls.append(rec)
                f1s.append(f1)

            metrics.precision = float(np.mean(precisions))
            metrics.recall = float(np.mean(recalls))
            metrics.f1_score = float(np.mean(f1s))

        return metrics

    @staticmethod
    def calculate_trading_metrics(
        predictions: np.ndarray,
        returns: np.ndarray,
        risk_free_rate: float = 0.0
    ) -> TrainingMetrics:
        """Calculate trading-specific metrics."""
        metrics = TrainingMetrics()

        # Strategy returns: prediction * actual return
        # Assume predictions are -1 (short), 0 (neutral), 1 (long)
        strategy_returns = predictions * returns

        # Win rate
        winning_trades = strategy_returns > 0
        metrics.win_rate = float(np.mean(winning_trades)) if len(winning_trades) > 0 else 0.0

        # Sharpe ratio (annualized for daily data)
        if len(strategy_returns) > 0 and np.std(strategy_returns) > 0:
            metrics.sharpe_ratio = float(
                np.sqrt(252) * (np.mean(strategy_returns) - risk_free_rate / 252) / np.std(strategy_returns)
            )

        # Max drawdown
        cumulative = np.cumprod(1 + strategy_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / running_max
        metrics.max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Profit factor
        gains = strategy_returns[strategy_returns > 0].sum() if any(strategy_returns > 0) else 0
        losses = abs(strategy_returns[strategy_returns < 0].sum()) if any(strategy_returns < 0) else 0
        metrics.profit_factor = float(gains / losses) if losses > 0 else float('inf') if gains > 0 else 0.0

        # Information ratio (vs benchmark = buy and hold)
        benchmark_returns = returns
        active_returns = strategy_returns - benchmark_returns

        if len(active_returns) > 0 and np.std(active_returns) > 0:
            metrics.information_ratio = float(
                np.sqrt(252) * np.mean(active_returns) / np.std(active_returns)
            )

        return metrics


# =============================================================================
# MODEL TRAINER
# =============================================================================

class ModelTrainer:
    """
    Main model training orchestrator.

    Handles training, validation, and model selection.
    """

    def __init__(
        self,
        config: TrainingConfig = None,
        model_dir: str = None,
        db_path: str = None
    ):
        self.config = config or TrainingConfig()
        self.model_dir = Path(model_dir) if model_dir else Path.home() / "QUANT_INDUSTRY_V1" / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

        self.splitter = TimeSeriesSplitter(self.config)
        self.metrics_calculator = MetricsCalculator()

        self.training_history: List[TrainingResult] = []

    def train_model(
        self,
        model: Any,  # BaseModel from models.py
        X: np.ndarray,
        y: np.ndarray,
        returns: np.ndarray = None,
        symbol: str = "UNKNOWN",
        save_model: bool = True
    ) -> TrainingResult:
        """
        Train a single model with validation.

        Args:
            model: Model instance to train
            X: Feature matrix
            y: Target labels
            returns: Actual returns for trading metrics
            symbol: Symbol being trained for
            save_model: Whether to save the trained model

        Returns:
            TrainingResult with metrics
        """
        import time
        start_time = time.time()

        # Generate model ID
        model_id = self._generate_model_id(model, symbol)

        logger.info(f"Training model {model_id} with {len(X)} samples")

        # Split data
        (X_train, y_train), (X_val, y_val), (X_test, y_test) = self.splitter.split_holdout(X, y)

        # Train
        model.train(X_train, y_train)

        # Evaluate on train set
        y_train_pred = model.predict(X_train)
        y_train_prob = model.predict_proba(X_train) if hasattr(model, 'predict_proba') else None
        train_metrics = self.metrics_calculator.calculate_classification_metrics(
            y_train, y_train_pred, y_train_prob
        )

        # Evaluate on validation set
        y_val_pred = model.predict(X_val)
        y_val_prob = model.predict_proba(X_val) if hasattr(model, 'predict_proba') else None
        val_metrics = self.metrics_calculator.calculate_classification_metrics(
            y_val, y_val_pred, y_val_prob
        )

        # Evaluate on test set
        y_test_pred = model.predict(X_test)
        y_test_prob = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
        test_metrics = self.metrics_calculator.calculate_classification_metrics(
            y_test, y_test_pred, y_test_prob
        )

        # Add trading metrics if returns provided
        if returns is not None:
            n = len(X)
            train_end = int(n * self.config.train_ratio)
            val_end = train_end + int(n * self.config.validation_ratio)

            if len(returns) >= val_end:
                train_returns = returns[:train_end]
                val_returns = returns[train_end:val_end]
                test_returns = returns[val_end:]

                # Adjust for purge/embargo
                if len(train_returns) >= len(y_train_pred):
                    train_trading = self.metrics_calculator.calculate_trading_metrics(
                        y_train_pred, train_returns[:len(y_train_pred)]
                    )
                    train_metrics.sharpe_ratio = train_trading.sharpe_ratio
                    train_metrics.max_drawdown = train_trading.max_drawdown
                    train_metrics.win_rate = train_trading.win_rate
                    train_metrics.profit_factor = train_trading.profit_factor

                if len(val_returns) >= len(y_val_pred):
                    val_trading = self.metrics_calculator.calculate_trading_metrics(
                        y_val_pred, val_returns[:len(y_val_pred)]
                    )
                    val_metrics.sharpe_ratio = val_trading.sharpe_ratio
                    val_metrics.max_drawdown = val_trading.max_drawdown
                    val_metrics.win_rate = val_trading.win_rate
                    val_metrics.profit_factor = val_trading.profit_factor

        # Get feature importance
        feature_importance = {}
        if hasattr(model, 'feature_importance') and model.feature_importance is not None:
            feature_importance = dict(model.feature_importance)

        # Calculate duration
        duration = time.time() - start_time

        # Save model
        model_path = None
        if save_model:
            model_path = str(self.model_dir / f"{model_id}.pkl")
            self._save_model(model, model_path)

        result = TrainingResult(
            model_id=model_id,
            model_type=type(model).__name__,
            trained_at=datetime.now(timezone.utc),
            config={
                'symbol': symbol,
                'validation_method': self.config.validation_method.value,
                'train_ratio': self.config.train_ratio,
            },
            train_metrics=train_metrics,
            validation_metrics=val_metrics,
            test_metrics=test_metrics,
            feature_importance=feature_importance,
            training_duration_seconds=duration,
            samples_used=len(X),
            model_path=model_path,
        )

        self.training_history.append(result)

        # Save to database if available
        if self.db_path:
            self._save_to_database(result)

        logger.info(
            f"Model {model_id} trained: "
            f"val_accuracy={val_metrics.accuracy:.3f}, "
            f"val_sharpe={val_metrics.sharpe_ratio:.3f}"
        )

        return result

    def walk_forward_train(
        self,
        model_factory: Callable[[], Any],  # Function that creates a new model
        X: np.ndarray,
        y: np.ndarray,
        returns: np.ndarray = None,
        symbol: str = "UNKNOWN"
    ) -> List[TrainingResult]:
        """
        Perform walk-forward training and validation.

        Args:
            model_factory: Function that creates a new model instance
            X: Feature matrix
            y: Target labels
            returns: Actual returns
            symbol: Symbol being trained for

        Returns:
            List of TrainingResult for each fold
        """
        splits = self.splitter.walk_forward_splits(X, y)
        results = []

        logger.info(f"Walk-forward training with {len(splits)} folds")

        for i, ((X_train, y_train), (X_test, y_test)) in enumerate(splits):
            model = model_factory()
            model_id = self._generate_model_id(model, symbol, fold=i)

            logger.info(f"Training fold {i+1}/{len(splits)}")

            # Train
            model.train(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            metrics = self.metrics_calculator.calculate_classification_metrics(
                y_test, y_pred
            )

            # Trading metrics if available
            if returns is not None:
                # Need to align returns with test set
                pass  # Would need to track indices properly

            result = TrainingResult(
                model_id=model_id,
                model_type=type(model).__name__,
                trained_at=datetime.now(timezone.utc),
                config={
                    'symbol': symbol,
                    'fold': i,
                    'validation_method': 'walk_forward',
                },
                train_metrics=metrics,  # Using same for simplicity
                validation_metrics=metrics,
                samples_used=len(X_train),
            )

            results.append(result)

        return results

    def cross_validate(
        self,
        model_factory: Callable[[], Any],
        X: np.ndarray,
        y: np.ndarray,
        symbol: str = "UNKNOWN"
    ) -> Tuple[TrainingMetrics, List[TrainingMetrics]]:
        """
        Perform time series cross-validation.

        Returns:
            Tuple of (average_metrics, per_fold_metrics)
        """
        splits = self.splitter.time_series_cv_splits(X, y)

        all_metrics = []

        for i, ((X_train, y_train), (X_test, y_test)) in enumerate(splits):
            model = model_factory()

            model.train(X_train, y_train)
            y_pred = model.predict(X_test)

            metrics = self.metrics_calculator.calculate_classification_metrics(
                y_test, y_pred
            )
            all_metrics.append(metrics)

        # Average metrics
        avg_metrics = TrainingMetrics(
            accuracy=float(np.mean([m.accuracy for m in all_metrics])),
            precision=float(np.mean([m.precision for m in all_metrics])),
            recall=float(np.mean([m.recall for m in all_metrics])),
            f1_score=float(np.mean([m.f1_score for m in all_metrics])),
            sharpe_ratio=float(np.mean([m.sharpe_ratio for m in all_metrics])),
            max_drawdown=float(np.mean([m.max_drawdown for m in all_metrics])),
            win_rate=float(np.mean([m.win_rate for m in all_metrics])),
            profit_factor=float(np.mean([m.profit_factor for m in all_metrics])),
        )

        return avg_metrics, all_metrics

    def _generate_model_id(self, model: Any, symbol: str, fold: int = None) -> str:
        """Generate unique model ID."""
        components = [
            type(model).__name__,
            symbol,
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        ]
        if fold is not None:
            components.append(f"fold{fold}")

        id_string = "_".join(components)
        hash_suffix = hashlib.md5(id_string.encode()).hexdigest()[:8]

        return f"{type(model).__name__}_{symbol}_{hash_suffix}"

    def _save_model(self, model: Any, path: str) -> None:
        """Save model to disk."""
        try:
            with open(path, 'wb') as f:
                pickle.dump(model, f)
            logger.info(f"Model saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def load_model(self, path: str) -> Any:
        """Load model from disk."""
        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None

    def _save_to_database(self, result: TrainingResult) -> None:
        """Save training result to database."""
        if not self.db_path:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO models (
                    model_id, model_type, symbol, trained_at, config,
                    accuracy, precision_score, recall, f1,
                    sharpe_ratio, max_drawdown, win_rate, profit_factor,
                    feature_importance, model_path, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.model_id,
                result.model_type,
                result.config.get('symbol', 'UNKNOWN'),
                result.trained_at.isoformat(),
                json.dumps(result.config),
                result.validation_metrics.accuracy,
                result.validation_metrics.precision,
                result.validation_metrics.recall,
                result.validation_metrics.f1_score,
                result.validation_metrics.sharpe_ratio,
                result.validation_metrics.max_drawdown,
                result.validation_metrics.win_rate,
                result.validation_metrics.profit_factor,
                json.dumps(result.feature_importance),
                result.model_path,
                'active'
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to save to database: {e}")


# =============================================================================
# MODEL SELECTOR
# =============================================================================

class ModelSelector:
    """
    Select best model based on validation metrics.

    Supports multiple selection criteria.
    """

    def __init__(
        self,
        primary_metric: str = 'sharpe_ratio',
        secondary_metric: str = 'accuracy',
        min_accuracy: float = 0.5,
        min_sharpe: float = 0.0
    ):
        self.primary_metric = primary_metric
        self.secondary_metric = secondary_metric
        self.min_accuracy = min_accuracy
        self.min_sharpe = min_sharpe

    def select_best(
        self,
        results: List[TrainingResult]
    ) -> Optional[TrainingResult]:
        """
        Select best model from training results.

        Args:
            results: List of training results

        Returns:
            Best TrainingResult or None
        """
        if not results:
            return None

        # Filter by minimum criteria
        valid_results = [
            r for r in results
            if r.validation_metrics.accuracy >= self.min_accuracy
            and r.validation_metrics.sharpe_ratio >= self.min_sharpe
        ]

        if not valid_results:
            logger.warning("No models meet minimum criteria, using best available")
            valid_results = results

        # Sort by primary metric (descending)
        sorted_results = sorted(
            valid_results,
            key=lambda r: (
                getattr(r.validation_metrics, self.primary_metric, 0),
                getattr(r.validation_metrics, self.secondary_metric, 0)
            ),
            reverse=True
        )

        best = sorted_results[0]
        logger.info(
            f"Selected model {best.model_id} with "
            f"{self.primary_metric}={getattr(best.validation_metrics, self.primary_metric):.3f}"
        )

        return best

    def rank_models(
        self,
        results: List[TrainingResult],
        top_n: int = 5
    ) -> List[TrainingResult]:
        """
        Rank models by performance.

        Returns:
            Top N models sorted by primary metric
        """
        sorted_results = sorted(
            results,
            key=lambda r: getattr(r.validation_metrics, self.primary_metric, 0),
            reverse=True
        )

        return sorted_results[:top_n]


# =============================================================================
# HYPERPARAMETER TUNER
# =============================================================================

class HyperparameterTuner:
    """
    Simple hyperparameter tuning via grid search.

    For production, consider optuna or hyperopt.
    """

    def __init__(self, trainer: ModelTrainer):
        self.trainer = trainer
        self.best_params: Dict[str, Any] = {}
        self.results_history: List[Dict[str, Any]] = []

    def grid_search(
        self,
        model_factory: Callable[[Dict], Any],
        param_grid: Dict[str, List[Any]],
        X: np.ndarray,
        y: np.ndarray,
        returns: np.ndarray = None,
        symbol: str = "UNKNOWN",
        metric: str = 'sharpe_ratio'
    ) -> Tuple[Dict[str, Any], TrainingResult]:
        """
        Perform grid search over hyperparameters.

        Args:
            model_factory: Function that takes params dict and returns model
            param_grid: Dict of param_name -> list of values
            X: Features
            y: Labels
            returns: Returns for trading metrics
            symbol: Symbol
            metric: Metric to optimize

        Returns:
            Tuple of (best_params, best_result)
        """
        # Generate all combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        combinations = self._generate_combinations(param_names, param_values)
        logger.info(f"Grid search with {len(combinations)} combinations")

        best_result = None
        best_params = None
        best_metric_value = float('-inf')

        for i, params in enumerate(combinations):
            logger.info(f"Trying combination {i+1}/{len(combinations)}: {params}")

            try:
                model = model_factory(params)
                result = self.trainer.train_model(
                    model, X, y, returns, symbol, save_model=False
                )

                metric_value = getattr(result.validation_metrics, metric, 0)

                self.results_history.append({
                    'params': params,
                    'metric_value': metric_value,
                    'result': result.to_dict()
                })

                if metric_value > best_metric_value:
                    best_metric_value = metric_value
                    best_params = params
                    best_result = result

            except Exception as e:
                logger.error(f"Error with params {params}: {e}")

        self.best_params = best_params or {}

        logger.info(f"Best params: {best_params} with {metric}={best_metric_value:.3f}")

        return best_params, best_result

    def _generate_combinations(
        self,
        names: List[str],
        values: List[List[Any]]
    ) -> List[Dict[str, Any]]:
        """Generate all parameter combinations."""
        if not names:
            return [{}]

        combinations = []

        def recurse(idx: int, current: Dict[str, Any]):
            if idx == len(names):
                combinations.append(current.copy())
                return

            for val in values[idx]:
                current[names[idx]] = val
                recurse(idx + 1, current)

        recurse(0, {})
        return combinations
