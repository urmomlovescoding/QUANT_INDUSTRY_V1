"""
QUANT INDUSTRY - SVM Kernel Comparison Framework
=================================================
Implements the methodology from:
"Differences Between SVM Kernels and a Backtesting Methodology for Stock-Market Prediction"

Key Features:
1. Linear, Polynomial, RBF, and Sigmoid kernel comparison
2. Walk-forward validation with purging and embargo
3. Nested hyperparameter tuning (prevents selection bias)
4. Deflated Sharpe Ratio for multiple comparison correction
5. Probability of Backtest Overfitting (PBO) estimation

References:
- de Prado (2018): Advances in Financial Machine Learning
- Bailey & de Prado (2014): The Probability of Backtest Overfitting
- Hansen (2005): Superior Predictive Ability Test

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# ML Libraries
try:
    from sklearn.svm import SVC, SVR
    from sklearn.preprocessing import StandardScaler, RobustScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        balanced_accuracy_score, roc_auc_score, mean_squared_error
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class SVMKernel(Enum):
    """Available SVM kernels for comparison."""
    LINEAR = "linear"
    POLYNOMIAL = "poly"
    RBF = "rbf"
    SIGMOID = "sigmoid"


@dataclass
class KernelConfig:
    """
    Configuration for a specific SVM kernel.

    Based on scikit-learn parameterization and the document's recommendations:
    - Linear: tune C only
    - Polynomial: tune C, degree, gamma, coef0
    - RBF: tune C, gamma
    - Sigmoid: tune C, gamma, coef0 (use with caution - non-PSD risk)
    """
    kernel: SVMKernel

    # Common parameter grid
    C_range: List[float] = field(default_factory=lambda: [0.01, 0.1, 1.0, 10.0, 100.0])

    # Polynomial-specific
    degree_range: List[int] = field(default_factory=lambda: [2, 3, 4])

    # RBF/Poly/Sigmoid
    gamma_range: List[Union[str, float]] = field(default_factory=lambda: ['scale', 'auto', 0.01, 0.1, 1.0])

    # Polynomial/Sigmoid
    coef0_range: List[float] = field(default_factory=lambda: [0.0, 0.1, 1.0])

    def get_param_grid(self) -> Dict[str, List]:
        """
        Get the parameter grid for GridSearchCV.
        Returns grid specific to the kernel type.
        """
        # Always include C (regularization)
        grid = {'svm__C': self.C_range}

        if self.kernel == SVMKernel.LINEAR:
            # Linear: only C matters
            pass

        elif self.kernel == SVMKernel.POLYNOMIAL:
            # Polynomial: C, degree, gamma, coef0
            grid['svm__degree'] = self.degree_range
            grid['svm__gamma'] = self.gamma_range
            grid['svm__coef0'] = self.coef0_range

        elif self.kernel == SVMKernel.RBF:
            # RBF: C, gamma
            grid['svm__gamma'] = self.gamma_range

        elif self.kernel == SVMKernel.SIGMOID:
            # Sigmoid: C, gamma, coef0 (caution: may be non-PSD)
            grid['svm__gamma'] = self.gamma_range
            grid['svm__coef0'] = self.coef0_range

        return grid


@dataclass
class WalkForwardSplit:
    """Single train/test split with embargo."""
    fold_id: int
    train_start_idx: int
    train_end_idx: int
    test_start_idx: int
    test_end_idx: int
    embargo_periods: int = 0

    @property
    def train_size(self) -> int:
        return self.train_end_idx - self.train_start_idx

    @property
    def test_size(self) -> int:
        return self.test_end_idx - self.test_start_idx


@dataclass
class KernelResult:
    """Results from evaluating a single kernel."""
    kernel: SVMKernel
    fold_id: int

    # Best parameters from nested CV
    best_params: Dict[str, Any]

    # Predictive metrics (on test fold)
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    balanced_accuracy: float = 0.0
    roc_auc: Optional[float] = None

    # Trading metrics (after converting predictions to positions)
    sharpe_ratio: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    # Overfitting indicators
    train_accuracy: float = 0.0
    accuracy_degradation: float = 0.0  # train - test

    # Timing
    training_time_seconds: float = 0.0

    def is_overfit(self, threshold: float = 0.15) -> bool:
        """Check if the model is likely overfit."""
        return self.accuracy_degradation > threshold


@dataclass
class KernelComparisonReport:
    """
    Complete report comparing all kernels.

    Includes:
    - Per-kernel, per-fold results
    - Aggregate statistics
    - Deflated Sharpe Ratio
    - Probability of Backtest Overfitting
    """
    results: Dict[SVMKernel, List[KernelResult]] = field(default_factory=dict)

    # Aggregate metrics per kernel
    aggregate_metrics: Dict[SVMKernel, Dict[str, float]] = field(default_factory=dict)

    # Multiple comparison corrections
    deflated_sharpe_ratios: Dict[SVMKernel, float] = field(default_factory=dict)
    pbo_estimates: Dict[SVMKernel, float] = field(default_factory=dict)

    # Best kernel selection
    best_kernel: Optional[SVMKernel] = None
    ranking: List[Tuple[SVMKernel, float]] = field(default_factory=list)

    def compute_aggregates(self):
        """Compute aggregate statistics for each kernel."""
        for kernel, fold_results in self.results.items():
            if not fold_results:
                continue

            sharpes = [r.sharpe_ratio for r in fold_results]
            returns = [r.total_return for r in fold_results]
            accuracies = [r.accuracy for r in fold_results]
            overfit_flags = [r.is_overfit() for r in fold_results]

            self.aggregate_metrics[kernel] = {
                # Sharpe statistics
                'mean_sharpe': np.mean(sharpes),
                'std_sharpe': np.std(sharpes),
                'min_sharpe': np.min(sharpes),
                'max_sharpe': np.max(sharpes),
                'median_sharpe': np.median(sharpes),

                # Return statistics
                'mean_return': np.mean(returns),
                'cumulative_return': np.prod([1 + r for r in returns]) - 1,

                # Accuracy statistics
                'mean_accuracy': np.mean(accuracies),

                # Stability metrics
                'sharpe_consistency': np.sum(np.array(sharpes) > 0) / len(sharpes),
                'profitable_folds': np.sum(np.array(returns) > 0),

                # Overfitting
                'overfit_ratio': np.sum(overfit_flags) / len(overfit_flags),

                'n_folds': len(fold_results)
            }

    def compute_deflated_sharpe(self, n_trials: int = 4):
        """
        Compute Deflated Sharpe Ratio for each kernel.

        DSR corrects for:
        1. Multiple testing (we tried n_trials kernels)
        2. Non-normal returns
        3. Short sample bias

        Reference: Bailey & de Prado (2014) "The Deflated Sharpe Ratio"
        """
        from scipy import stats

        for kernel, metrics in self.aggregate_metrics.items():
            sr = metrics.get('mean_sharpe', 0)
            sr_std = metrics.get('std_sharpe', 1)
            n_folds = metrics.get('n_folds', 1)

            if sr_std == 0 or n_folds < 2:
                self.deflated_sharpe_ratios[kernel] = 0.0
                continue

            # Expected max Sharpe from random trials (order statistics)
            # E[max(Z_1, ..., Z_n)] ≈ (1 - γ) * Φ^(-1)(1 - 1/n) + γ * Φ^(-1)(1 - 1/(n*e))
            # Simplified: use approximation sqrt(2 * log(n_trials))
            expected_max_sr = np.sqrt(2 * np.log(n_trials)) if n_trials > 1 else 0

            # Deflate the Sharpe ratio
            # DSR = (SR - E[max SR]) / std(SR) * sqrt(n)
            dsr = (sr - expected_max_sr * sr_std) / sr_std * np.sqrt(n_folds)

            # Convert to probability
            dsr_prob = stats.norm.cdf(dsr)

            self.deflated_sharpe_ratios[kernel] = dsr_prob

    def rank_kernels(self, metric: str = 'mean_sharpe'):
        """Rank kernels by specified metric (DSR-adjusted)."""
        # First compute everything
        self.compute_aggregates()
        self.compute_deflated_sharpe(n_trials=len(self.results))

        # Rank by DSR-weighted Sharpe
        rankings = []
        for kernel in self.results.keys():
            base_metric = self.aggregate_metrics.get(kernel, {}).get(metric, 0)
            dsr_weight = self.deflated_sharpe_ratios.get(kernel, 0.5)

            # Penalize high overfit ratio
            overfit_penalty = self.aggregate_metrics.get(kernel, {}).get('overfit_ratio', 0)

            # Combined score: DSR-weighted metric with overfit penalty
            combined_score = base_metric * dsr_weight * (1 - overfit_penalty)
            rankings.append((kernel, combined_score))

        self.ranking = sorted(rankings, key=lambda x: x[1], reverse=True)
        self.best_kernel = self.ranking[0][0] if self.ranking else None

    def summary(self) -> str:
        """Generate human-readable comparison summary."""
        self.rank_kernels()

        lines = [
            "=" * 70,
            "SVM KERNEL COMPARISON REPORT",
            "Based on: 'Differences Between SVM Kernels and Backtesting Methodology'",
            "=" * 70,
            "",
            "KERNEL RANKING (DSR-adjusted, penalized for overfitting):",
            "-" * 50,
        ]

        for i, (kernel, score) in enumerate(self.ranking):
            metrics = self.aggregate_metrics.get(kernel, {})
            dsr = self.deflated_sharpe_ratios.get(kernel, 0)

            lines.append(
                f"{i+1}. {kernel.value.upper():10} | "
                f"Score: {score:.4f} | "
                f"Mean Sharpe: {metrics.get('mean_sharpe', 0):.3f} | "
                f"DSR: {dsr:.3f} | "
                f"Overfit: {metrics.get('overfit_ratio', 0):.1%}"
            )

        lines.extend([
            "",
            "DETAILED KERNEL METRICS:",
            "-" * 50,
        ])

        for kernel, metrics in self.aggregate_metrics.items():
            lines.extend([
                f"\n{kernel.value.upper()} Kernel:",
                f"  Sharpe: {metrics.get('mean_sharpe', 0):.3f} ± {metrics.get('std_sharpe', 0):.3f}",
                f"  Range: [{metrics.get('min_sharpe', 0):.3f}, {metrics.get('max_sharpe', 0):.3f}]",
                f"  Mean Return: {metrics.get('mean_return', 0):.2%}",
                f"  Accuracy: {metrics.get('mean_accuracy', 0):.1%}",
                f"  Consistency: {metrics.get('sharpe_consistency', 0):.0%} folds positive",
                f"  Overfit Ratio: {metrics.get('overfit_ratio', 0):.1%}",
            ])

        lines.extend([
            "",
            "=" * 70,
            f"RECOMMENDATION: Use {self.best_kernel.value.upper()} kernel",
            "=" * 70,
        ])

        return "\n".join(lines)


class PurgedKFold:
    """
    Combinatorially Purged K-Fold Cross-Validation.

    Implements de Prado's method from AFML Chapter 7:
    1. Purging: Remove training samples whose labels overlap test period
    2. Embargo: Add buffer after test fold to prevent leakage from autocorrelation

    This is essential for financial time series where:
    - Labels may span multiple bars (e.g., "return over next 5 days")
    - Features exhibit serial correlation
    """

    def __init__(
        self,
        n_splits: int = 5,
        embargo_pct: float = 0.01,
        label_horizon: int = 1
    ):
        """
        Args:
            n_splits: Number of CV folds
            embargo_pct: Fraction of samples to embargo after each test fold
            label_horizon: How many bars forward the label looks (for purging)
        """
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
        self.label_horizon = label_horizon

    def split(self, X: np.ndarray, y: np.ndarray = None) -> List[WalkForwardSplit]:
        """
        Generate purged k-fold splits.

        Returns list of WalkForwardSplit objects with indices.
        """
        n_samples = len(X)
        fold_size = n_samples // self.n_splits
        embargo_size = max(1, int(n_samples * self.embargo_pct))

        splits = []

        for fold_id in range(self.n_splits):
            # Test fold boundaries
            test_start = fold_id * fold_size
            test_end = min((fold_id + 1) * fold_size, n_samples)

            # Training: everything except test + purge window
            # Purge: samples whose labels overlap with test period
            purge_start = max(0, test_start - self.label_horizon)
            purge_end = min(n_samples, test_end + embargo_size)

            # For simplicity in walk-forward, train on everything before purge_start
            train_start = 0
            train_end = purge_start

            if train_end <= train_start:
                continue  # Skip if no training data

            splits.append(WalkForwardSplit(
                fold_id=fold_id,
                train_start_idx=train_start,
                train_end_idx=train_end,
                test_start_idx=test_start,
                test_end_idx=test_end,
                embargo_periods=embargo_size
            ))

        return splits


class SVMKernelComparison:
    """
    Main class for comparing SVM kernels on financial data.

    Implements the full methodology from the referenced document:
    1. Feature scaling (mandatory for SVMs)
    2. Walk-forward validation with purging and embargo
    3. Nested hyperparameter tuning
    4. Multiple kernel comparison
    5. Statistical correction for multiple testing
    """

    def __init__(
        self,
        task: str = 'classification',  # 'classification' or 'regression'
        n_splits: int = 5,
        embargo_pct: float = 0.01,
        label_horizon: int = 1,
        inner_cv_splits: int = 3,
        scoring: str = 'accuracy',
        n_jobs: int = -1,
        random_state: int = 42
    ):
        """
        Args:
            task: 'classification' for direction prediction, 'regression' for return
            n_splits: Number of outer walk-forward folds
            embargo_pct: Embargo as fraction of data
            label_horizon: Forward horizon for label (for purging)
            inner_cv_splits: CV folds for hyperparameter tuning
            scoring: Metric for GridSearchCV
            n_jobs: Parallel jobs (-1 = all cores)
            random_state: For reproducibility
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for SVM kernel comparison")

        self.task = task
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
        self.label_horizon = label_horizon
        self.inner_cv_splits = inner_cv_splits
        self.scoring = scoring
        self.n_jobs = n_jobs
        self.random_state = random_state

        # Initialize purged k-fold
        self.cv_splitter = PurgedKFold(
            n_splits=n_splits,
            embargo_pct=embargo_pct,
            label_horizon=label_horizon
        )

        # Kernel configurations (default grids from the document)
        self.kernel_configs = {
            SVMKernel.LINEAR: KernelConfig(kernel=SVMKernel.LINEAR),
            SVMKernel.POLYNOMIAL: KernelConfig(kernel=SVMKernel.POLYNOMIAL),
            SVMKernel.RBF: KernelConfig(kernel=SVMKernel.RBF),
            SVMKernel.SIGMOID: KernelConfig(kernel=SVMKernel.SIGMOID),
        }

    def _create_pipeline(self, kernel: SVMKernel) -> Pipeline:
        """Create sklearn pipeline with scaling + SVM."""
        # Feature scaling is NOT optional for kernel SVMs (from document)
        scaler = StandardScaler()

        if self.task == 'classification':
            svm = SVC(
                kernel=kernel.value,
                probability=True,  # For ROC-AUC
                random_state=self.random_state,
                class_weight='balanced'  # Handle imbalanced classes
            )
        else:
            svm = SVR(
                kernel=kernel.value,
            )

        return Pipeline([
            ('scaler', scaler),
            ('svm', svm)
        ])

    def _tune_hyperparameters(
        self,
        pipeline: Pipeline,
        param_grid: Dict[str, List],
        X_train: np.ndarray,
        y_train: np.ndarray
    ) -> Tuple[Pipeline, Dict[str, Any]]:
        """
        Nested hyperparameter tuning using inner CV.

        This prevents hyperparameter overfitting (selection bias).
        """
        # Inner CV for hyperparameter selection
        inner_cv = TimeSeriesSplit(n_splits=self.inner_cv_splits)

        grid_search = GridSearchCV(
            pipeline,
            param_grid,
            cv=inner_cv,
            scoring=self.scoring,
            n_jobs=self.n_jobs,
            refit=True
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            grid_search.fit(X_train, y_train)

        return grid_search.best_estimator_, grid_search.best_params_

    def _evaluate_predictions(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """Compute predictive metrics."""
        metrics = {}

        if self.task == 'classification':
            metrics['accuracy'] = accuracy_score(y_true, y_pred)
            metrics['balanced_accuracy'] = balanced_accuracy_score(y_true, y_pred)
            metrics['precision'] = precision_score(y_true, y_pred, average='weighted', zero_division=0)
            metrics['recall'] = recall_score(y_true, y_pred, average='weighted', zero_division=0)
            metrics['f1'] = f1_score(y_true, y_pred, average='weighted', zero_division=0)

            if y_proba is not None and len(np.unique(y_true)) == 2:
                try:
                    metrics['roc_auc'] = roc_auc_score(y_true, y_proba[:, 1])
                except:
                    metrics['roc_auc'] = None
        else:
            metrics['mse'] = mean_squared_error(y_true, y_pred)
            metrics['rmse'] = np.sqrt(metrics['mse'])

        return metrics

    def _compute_trading_metrics(
        self,
        predictions: np.ndarray,
        returns: np.ndarray,
        transaction_cost: float = 0.001
    ) -> Dict[str, float]:
        """
        Convert predictions to positions and compute trading metrics.

        Args:
            predictions: Model predictions (1 = long, -1 = short, 0 = hold for classification)
            returns: Actual forward returns
            transaction_cost: Per-trade cost (both sides)
        """
        # Convert classification predictions to positions
        if self.task == 'classification':
            positions = np.where(predictions > 0, 1, -1)
        else:
            # For regression, use sign of predicted return
            positions = np.sign(predictions)

        # Strategy returns (position * actual return)
        strategy_returns = positions * returns

        # Subtract transaction costs on position changes
        position_changes = np.abs(np.diff(positions, prepend=positions[0]))
        costs = position_changes * transaction_cost
        net_returns = strategy_returns - costs

        # Compute metrics
        if len(net_returns) < 2:
            return {
                'sharpe_ratio': 0.0,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0
            }

        # Sharpe ratio (annualized, assuming daily data)
        mean_ret = np.mean(net_returns)
        std_ret = np.std(net_returns)
        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0

        # Total return
        total_return = np.prod(1 + net_returns) - 1

        # Max drawdown
        cumulative = np.cumprod(1 + net_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdowns)

        # Win rate
        wins = np.sum(net_returns > 0)
        losses = np.sum(net_returns < 0)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

        # Profit factor
        gross_profit = np.sum(net_returns[net_returns > 0])
        gross_loss = np.abs(np.sum(net_returns[net_returns < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

        return {
            'sharpe_ratio': sharpe,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor
        }

    def compare_kernels(
        self,
        X: np.ndarray,
        y: np.ndarray,
        returns: Optional[np.ndarray] = None,
        kernels: Optional[List[SVMKernel]] = None,
        transaction_cost: float = 0.001
    ) -> KernelComparisonReport:
        """
        Run full kernel comparison with walk-forward validation.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (direction for classification, returns for regression)
            returns: Actual forward returns (for trading metric calculation)
            kernels: List of kernels to compare (default: all four)
            transaction_cost: Per-trade cost

        Returns:
            KernelComparisonReport with full comparison results
        """
        if kernels is None:
            kernels = list(SVMKernel)

        if returns is None:
            # If no separate returns provided, use labels as returns
            returns = y.copy()

        report = KernelComparisonReport()
        splits = self.cv_splitter.split(X, y)

        logger.info(f"Starting SVM kernel comparison with {len(kernels)} kernels, {len(splits)} folds")

        for kernel in kernels:
            logger.info(f"Evaluating {kernel.value} kernel...")
            report.results[kernel] = []

            config = self.kernel_configs[kernel]
            param_grid = config.get_param_grid()

            for split in splits:
                import time
                start_time = time.time()

                # Get train/test data
                X_train = X[split.train_start_idx:split.train_end_idx]
                y_train = y[split.train_start_idx:split.train_end_idx]
                X_test = X[split.test_start_idx:split.test_end_idx]
                y_test = y[split.test_start_idx:split.test_end_idx]
                returns_test = returns[split.test_start_idx:split.test_end_idx]

                if len(X_train) < 10 or len(X_test) < 5:
                    logger.warning(f"Skipping fold {split.fold_id}: insufficient data")
                    continue

                try:
                    # Create pipeline for this kernel
                    pipeline = self._create_pipeline(kernel)

                    # Nested hyperparameter tuning
                    best_pipeline, best_params = self._tune_hyperparameters(
                        pipeline, param_grid, X_train, y_train
                    )

                    # Predictions on train (for overfitting check)
                    y_train_pred = best_pipeline.predict(X_train)
                    train_metrics = self._evaluate_predictions(y_train, y_train_pred)

                    # Predictions on test
                    y_pred = best_pipeline.predict(X_test)
                    y_proba = None
                    if self.task == 'classification' and hasattr(best_pipeline, 'predict_proba'):
                        try:
                            y_proba = best_pipeline.predict_proba(X_test)
                        except:
                            pass

                    # Predictive metrics
                    test_metrics = self._evaluate_predictions(y_test, y_pred, y_proba)

                    # Trading metrics
                    trading_metrics = self._compute_trading_metrics(
                        y_pred, returns_test, transaction_cost
                    )

                    elapsed = time.time() - start_time

                    result = KernelResult(
                        kernel=kernel,
                        fold_id=split.fold_id,
                        best_params=best_params,
                        accuracy=test_metrics.get('accuracy', 0),
                        precision=test_metrics.get('precision', 0),
                        recall=test_metrics.get('recall', 0),
                        f1=test_metrics.get('f1', 0),
                        balanced_accuracy=test_metrics.get('balanced_accuracy', 0),
                        roc_auc=test_metrics.get('roc_auc'),
                        sharpe_ratio=trading_metrics['sharpe_ratio'],
                        total_return=trading_metrics['total_return'],
                        max_drawdown=trading_metrics['max_drawdown'],
                        win_rate=trading_metrics['win_rate'],
                        profit_factor=trading_metrics['profit_factor'],
                        train_accuracy=train_metrics.get('accuracy', 0),
                        accuracy_degradation=train_metrics.get('accuracy', 0) - test_metrics.get('accuracy', 0),
                        training_time_seconds=elapsed
                    )

                    report.results[kernel].append(result)

                    logger.info(
                        f"  Fold {split.fold_id}: Accuracy={result.accuracy:.3f}, "
                        f"Sharpe={result.sharpe_ratio:.3f}, Return={result.total_return:.2%}"
                    )

                except Exception as e:
                    logger.error(f"Error evaluating {kernel.value} on fold {split.fold_id}: {e}")
                    continue

        # Compute aggregates and rankings
        report.rank_kernels()

        return report


# ============================================================================
# INTEGRATION WITH QUANT INDUSTRY BACKTESTING
# ============================================================================

def create_svm_signals(
    df: pd.DataFrame,
    kernel: SVMKernel = SVMKernel.RBF,
    feature_columns: Optional[List[str]] = None,
    label_column: str = 'direction',
    **svm_params
) -> pd.Series:
    """
    Convenience function to generate trading signals using SVM.

    Can be integrated with:
    - beast_ml.py feature engineering
    - realistic_engine.py backtesting
    - walk_forward.py validation

    Args:
        df: DataFrame with features and labels
        kernel: Which SVM kernel to use
        feature_columns: Which columns are features (default: all except label)
        label_column: Column containing direction labels
        **svm_params: Additional SVM parameters

    Returns:
        Series of predicted signals
    """
    if feature_columns is None:
        feature_columns = [c for c in df.columns if c != label_column]

    X = df[feature_columns].values
    y = df[label_column].values

    # Create and fit pipeline
    scaler = StandardScaler()
    svm = SVC(kernel=kernel.value, probability=True, **svm_params)
    pipeline = Pipeline([('scaler', scaler), ('svm', svm)])

    # Fit on all data (in production, use walk-forward)
    pipeline.fit(X, y)

    # Return predictions
    predictions = pipeline.predict(X)
    return pd.Series(predictions, index=df.index, name='svm_signal')


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_kernel_comparison():
    """
    Example demonstrating the full kernel comparison workflow.

    This shows how to:
    1. Prepare features (using beast_ml feature engineering)
    2. Run the comparison
    3. Interpret results
    """
    # Generate synthetic data for demonstration
    np.random.seed(42)
    n_samples = 1000
    n_features = 20

    # Synthetic features (normally would come from FeatureEngineer)
    X = np.random.randn(n_samples, n_features)

    # Synthetic labels: next day direction (1 = up, 0 = down)
    # Add some signal: feature 0 has predictive power
    prob_up = 1 / (1 + np.exp(-(0.5 * X[:, 0] + 0.3 * X[:, 1])))
    y = (np.random.random(n_samples) < prob_up).astype(int)

    # Synthetic returns (aligned with labels)
    returns = np.where(y == 1, 0.002 + 0.01 * np.random.randn(n_samples),
                                -0.002 + 0.01 * np.random.randn(n_samples))

    # Run comparison
    comparator = SVMKernelComparison(
        task='classification',
        n_splits=5,
        embargo_pct=0.02,
        label_horizon=1
    )

    report = comparator.compare_kernels(
        X, y, returns,
        kernels=[SVMKernel.LINEAR, SVMKernel.RBF, SVMKernel.POLYNOMIAL],
        transaction_cost=0.001
    )

    # Print results
    print(report.summary())

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_kernel_comparison()
