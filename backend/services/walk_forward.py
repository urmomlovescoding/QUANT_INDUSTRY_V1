"""
QUANT INDUSTRY - Walk-Forward Validation Framework
===================================================
Institutional-grade time-series cross-validation for trading models.

This module implements:
1. Walk-Forward Optimization (WFO)
2. Combinatorially Purged Cross-Validation (CPCV) - de Prado method
3. Embargo periods to prevent look-ahead bias
4. Rolling and expanding window validation

The key insight: Financial time series are non-stationary. Traditional CV
leaks future information into the past. Walk-forward respects temporal order.

References:
- de Prado (2018): "Advances in Financial Machine Learning" - Chapter 7
- Bailey et al. (2014): "The Probability of Backtest Overfitting"

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)


class ValidationMethod(Enum):
    """Walk-forward validation methods."""
    ROLLING = "rolling"           # Fixed window, rolls forward
    EXPANDING = "expanding"       # Growing training window
    ANCHORED = "anchored"         # Fixed start, expanding end
    PURGED_KFOLD = "purged_kfold" # de Prado's CPCV


@dataclass
class WalkForwardSplit:
    """A single train/validation/test split."""
    split_id: int
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None
    embargo_periods: int = 0  # Gaps between train and val/test
    
    @property
    def train_size(self) -> timedelta:
        return self.train_end - self.train_start
    
    @property 
    def validation_size(self) -> timedelta:
        return self.validation_end - self.validation_start
    
    def __repr__(self) -> str:
        return (
            f"Split {self.split_id}: "
            f"Train[{self.train_start.date()} - {self.train_end.date()}] "
            f"Val[{self.validation_start.date()} - {self.validation_end.date()}]"
        )


@dataclass
class WalkForwardResult:
    """Results from walk-forward validation."""
    split_id: int
    train_metrics: Dict[str, float]
    validation_metrics: Dict[str, float]
    test_metrics: Optional[Dict[str, float]] = None
    model_params: Optional[Dict[str, Any]] = None
    training_time_seconds: float = 0.0
    
    @property
    def is_overfit(self) -> bool:
        """Check if model shows signs of overfitting."""
        train_sharpe = self.train_metrics.get('sharpe_ratio', 0)
        val_sharpe = self.validation_metrics.get('sharpe_ratio', 0)
        
        # If validation Sharpe is < 50% of training, likely overfit
        if train_sharpe > 0:
            return val_sharpe / train_sharpe < 0.5
        return False


@dataclass
class WalkForwardReport:
    """Complete walk-forward validation report."""
    method: ValidationMethod
    n_splits: int
    results: List[WalkForwardResult]
    aggregate_metrics: Dict[str, float] = field(default_factory=dict)
    
    def compute_aggregates(self):
        """Compute aggregate statistics across all splits."""
        if not self.results:
            return
        
        # Collect metrics across splits
        val_sharpes = [r.validation_metrics.get('sharpe_ratio', 0) for r in self.results]
        val_returns = [r.validation_metrics.get('total_return', 0) for r in self.results]
        val_win_rates = [r.validation_metrics.get('win_rate', 0) for r in self.results]
        
        self.aggregate_metrics = {
            'mean_sharpe': np.mean(val_sharpes),
            'std_sharpe': np.std(val_sharpes),
            'min_sharpe': np.min(val_sharpes),
            'max_sharpe': np.max(val_sharpes),
            'sharpe_consistency': np.sum(np.array(val_sharpes) > 0) / len(val_sharpes),
            'mean_return': np.mean(val_returns),
            'mean_win_rate': np.mean(val_win_rates),
            'overfit_ratio': np.sum([r.is_overfit for r in self.results]) / len(self.results),
            'n_profitable_splits': np.sum(np.array(val_returns) > 0),
        }
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        self.compute_aggregates()
        
        return f"""
Walk-Forward Validation Report
==============================
Method: {self.method.value}
Splits: {self.n_splits}

Aggregate Performance:
- Mean Sharpe: {self.aggregate_metrics.get('mean_sharpe', 0):.3f} ± {self.aggregate_metrics.get('std_sharpe', 0):.3f}
- Sharpe Range: [{self.aggregate_metrics.get('min_sharpe', 0):.3f}, {self.aggregate_metrics.get('max_sharpe', 0):.3f}]
- Consistency (% positive): {self.aggregate_metrics.get('sharpe_consistency', 0):.1%}
- Mean Return: {self.aggregate_metrics.get('mean_return', 0):.2%}
- Mean Win Rate: {self.aggregate_metrics.get('mean_win_rate', 0):.1%}
- Overfit Ratio: {self.aggregate_metrics.get('overfit_ratio', 0):.1%}
- Profitable Splits: {self.aggregate_metrics.get('n_profitable_splits', 0)}/{self.n_splits}

{'⚠️ WARNING: High overfit ratio detected!' if self.aggregate_metrics.get('overfit_ratio', 0) > 0.3 else ''}
{'⚠️ WARNING: Inconsistent Sharpe across periods!' if self.aggregate_metrics.get('sharpe_consistency', 0) < 0.6 else ''}
"""


class WalkForwardValidator:
    """
    Walk-Forward Validation Engine
    
    Implements proper time-series cross-validation that:
    1. Respects temporal ordering (no look-ahead bias)
    2. Uses embargo periods to prevent information leakage
    3. Supports multiple validation schemes
    4. Tracks overfit signals
    
    Usage:
    ------
    >>> validator = WalkForwardValidator(
    ...     method=ValidationMethod.ROLLING,
    ...     n_splits=12,
    ...     train_period_months=6,
    ...     test_period_months=1,
    ...     embargo_days=5
    ... )
    >>> 
    >>> for split, train_df, val_df in validator.generate_splits(data):
    ...     model.fit(train_df)
    ...     metrics = model.evaluate(val_df)
    ...     validator.record_result(split.split_id, train_metrics, val_metrics)
    >>>
    >>> report = validator.get_report()
    >>> print(report.summary())
    """
    
    def __init__(
        self,
        method: ValidationMethod = ValidationMethod.ROLLING,
        n_splits: int = 12,
        train_period_months: int = 6,
        validation_period_months: int = 1,
        test_period_months: int = 0,
        embargo_days: int = 5,
        min_train_samples: int = 1000,
        purge_overlap_days: int = 0
    ):
        """
        Initialize walk-forward validator.
        
        Args:
            method: Validation method to use
            n_splits: Number of train/validation splits
            train_period_months: Length of training window
            validation_period_months: Length of validation window  
            test_period_months: Length of test window (0 = no test set)
            embargo_days: Gap between train and validation to prevent leakage
            min_train_samples: Minimum samples required in training set
            purge_overlap_days: For CPCV, days to purge around test periods
        """
        self.method = method
        self.n_splits = n_splits
        self.train_period_months = train_period_months
        self.validation_period_months = validation_period_months
        self.test_period_months = test_period_months
        self.embargo_days = embargo_days
        self.min_train_samples = min_train_samples
        self.purge_overlap_days = purge_overlap_days
        
        self.splits: List[WalkForwardSplit] = []
        self.results: List[WalkForwardResult] = []
        
        logger.info(
            f"Initialized WalkForwardValidator: method={method.value}, "
            f"n_splits={n_splits}, embargo={embargo_days}d"
        )
    
    def generate_splits(
        self,
        data: 'pd.DataFrame',
        date_col: str = 'timestamp'
    ) -> Generator[Tuple[WalkForwardSplit, 'pd.DataFrame', 'pd.DataFrame'], None, None]:
        """
        Generate train/validation splits from data.
        
        Args:
            data: DataFrame with time-series data
            date_col: Name of datetime column
            
        Yields:
            Tuple of (split_info, train_df, validation_df)
        """
        if not HAS_PANDAS:
            raise ImportError("Pandas required for walk-forward validation")
        
        # Ensure datetime index
        if date_col in data.columns:
            data = data.set_index(date_col)
        
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        
        data = data.sort_index()
        
        start_date = data.index.min()
        end_date = data.index.max()
        
        logger.info(f"Data range: {start_date.date()} to {end_date.date()}")
        
        # Generate splits based on method
        if self.method == ValidationMethod.ROLLING:
            yield from self._rolling_splits(data, start_date, end_date)
        elif self.method == ValidationMethod.EXPANDING:
            yield from self._expanding_splits(data, start_date, end_date)
        elif self.method == ValidationMethod.ANCHORED:
            yield from self._anchored_splits(data, start_date, end_date)
        elif self.method == ValidationMethod.PURGED_KFOLD:
            yield from self._purged_kfold_splits(data)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def _rolling_splits(
        self,
        data: 'pd.DataFrame',
        start_date: datetime,
        end_date: datetime
    ) -> Generator[Tuple[WalkForwardSplit, 'pd.DataFrame', 'pd.DataFrame'], None, None]:
        """Generate rolling window splits."""
        train_delta = pd.DateOffset(months=self.train_period_months)
        val_delta = pd.DateOffset(months=self.validation_period_months)
        embargo_delta = timedelta(days=self.embargo_days)
        step_delta = val_delta  # Step by validation period
        
        # Calculate first valid start (need enough data for train + val)
        total_needed = train_delta + embargo_delta + val_delta
        first_val_start = start_date + train_delta + embargo_delta
        
        current_train_start = start_date
        split_id = 0
        
        while split_id < self.n_splits:
            train_end = current_train_start + train_delta
            val_start = train_end + embargo_delta
            val_end = val_start + val_delta
            
            # Check if we have enough data
            if val_end > end_date:
                logger.warning(f"Insufficient data for split {split_id + 1}, stopping")
                break
            
            # Extract data
            train_df = data.loc[current_train_start:train_end].copy()
            val_df = data.loc[val_start:val_end].copy()
            
            # Check minimum samples
            if len(train_df) < self.min_train_samples:
                logger.warning(
                    f"Split {split_id}: Train set too small ({len(train_df)} < {self.min_train_samples})"
                )
                current_train_start += step_delta
                continue
            
            split = WalkForwardSplit(
                split_id=split_id,
                train_start=current_train_start,
                train_end=train_end,
                validation_start=val_start,
                validation_end=val_end,
                embargo_periods=self.embargo_days
            )
            
            self.splits.append(split)
            
            logger.info(f"Generated {split}")
            
            yield split, train_df, val_df
            
            # Roll forward
            current_train_start += step_delta
            split_id += 1
    
    def _expanding_splits(
        self,
        data: 'pd.DataFrame',
        start_date: datetime,
        end_date: datetime
    ) -> Generator[Tuple[WalkForwardSplit, 'pd.DataFrame', 'pd.DataFrame'], None, None]:
        """Generate expanding window splits (training window grows)."""
        val_delta = pd.DateOffset(months=self.validation_period_months)
        embargo_delta = timedelta(days=self.embargo_days)
        
        # Fixed start, expanding training window
        train_start = start_date
        
        # Calculate step size
        total_val_periods = (end_date - start_date).days / 30 / self.validation_period_months
        step_months = max(1, int(total_val_periods / self.n_splits))
        step_delta = pd.DateOffset(months=step_months)
        
        current_train_end = train_start + pd.DateOffset(months=self.train_period_months)
        split_id = 0
        
        while split_id < self.n_splits:
            val_start = current_train_end + embargo_delta
            val_end = val_start + val_delta
            
            if val_end > end_date:
                break
            
            train_df = data.loc[train_start:current_train_end].copy()
            val_df = data.loc[val_start:val_end].copy()
            
            if len(train_df) < self.min_train_samples:
                current_train_end += step_delta
                continue
            
            split = WalkForwardSplit(
                split_id=split_id,
                train_start=train_start,
                train_end=current_train_end,
                validation_start=val_start,
                validation_end=val_end,
                embargo_periods=self.embargo_days
            )
            
            self.splits.append(split)
            
            logger.info(f"Generated {split} (train size: {len(train_df)})")
            
            yield split, train_df, val_df
            
            # Expand training window
            current_train_end += step_delta
            split_id += 1
    
    def _anchored_splits(
        self,
        data: 'pd.DataFrame',
        start_date: datetime,
        end_date: datetime
    ) -> Generator[Tuple[WalkForwardSplit, 'pd.DataFrame', 'pd.DataFrame'], None, None]:
        """Generate anchored splits (same as expanding but with different semantics)."""
        yield from self._expanding_splits(data, start_date, end_date)
    
    def _purged_kfold_splits(
        self,
        data: 'pd.DataFrame'
    ) -> Generator[Tuple[WalkForwardSplit, 'pd.DataFrame', 'pd.DataFrame'], None, None]:
        """
        Generate combinatorially purged k-fold splits.
        
        This is de Prado's CPCV method that:
        1. Splits data into k groups
        2. Uses k-1 groups for training, 1 for validation
        3. Purges overlapping observations around validation set
        4. Adds embargo after validation period
        """
        n = len(data)
        indices = np.arange(n)
        
        # Split into k groups
        k = self.n_splits
        fold_size = n // k
        
        purge_samples = int(self.purge_overlap_days * 390)  # Assuming minute bars
        embargo_samples = int(self.embargo_days * 390)
        
        for split_id in range(k):
            # Validation fold
            val_start_idx = split_id * fold_size
            val_end_idx = (split_id + 1) * fold_size if split_id < k - 1 else n
            
            # Purge: remove samples that overlap with validation
            purge_start = max(0, val_start_idx - purge_samples)
            purge_end = min(n, val_end_idx + embargo_samples)
            
            # Training indices: everything except validation + purge zone
            train_mask = np.ones(n, dtype=bool)
            train_mask[purge_start:purge_end] = False
            
            train_indices = indices[train_mask]
            val_indices = indices[val_start_idx:val_end_idx]
            
            train_df = data.iloc[train_indices].copy()
            val_df = data.iloc[val_indices].copy()
            
            split = WalkForwardSplit(
                split_id=split_id,
                train_start=train_df.index.min(),
                train_end=train_df.index.max(),
                validation_start=val_df.index.min(),
                validation_end=val_df.index.max(),
                embargo_periods=embargo_samples
            )
            
            self.splits.append(split)
            
            logger.info(
                f"CPCV Split {split_id}: Train={len(train_df)}, "
                f"Val={len(val_df)}, Purged={purge_end - purge_start - (val_end_idx - val_start_idx)}"
            )
            
            yield split, train_df, val_df
    
    def record_result(
        self,
        split_id: int,
        train_metrics: Dict[str, float],
        validation_metrics: Dict[str, float],
        test_metrics: Optional[Dict[str, float]] = None,
        model_params: Optional[Dict[str, Any]] = None,
        training_time: float = 0.0
    ):
        """Record validation results for a split."""
        result = WalkForwardResult(
            split_id=split_id,
            train_metrics=train_metrics,
            validation_metrics=validation_metrics,
            test_metrics=test_metrics,
            model_params=model_params,
            training_time_seconds=training_time
        )
        
        self.results.append(result)
        
        # Log overfit warning
        if result.is_overfit:
            logger.warning(
                f"Split {split_id}: Possible overfit detected - "
                f"Train Sharpe: {train_metrics.get('sharpe_ratio', 'N/A')}, "
                f"Val Sharpe: {validation_metrics.get('sharpe_ratio', 'N/A')}"
            )
    
    def get_report(self) -> WalkForwardReport:
        """Generate validation report."""
        report = WalkForwardReport(
            method=self.method,
            n_splits=len(self.results),
            results=self.results
        )
        report.compute_aggregates()
        return report
    
    def is_strategy_robust(self, min_sharpe: float = 0.5, min_consistency: float = 0.6) -> bool:
        """
        Check if strategy passes robustness criteria.
        
        Args:
            min_sharpe: Minimum average Sharpe ratio
            min_consistency: Minimum fraction of positive Sharpe periods
            
        Returns:
            True if strategy appears robust
        """
        report = self.get_report()
        agg = report.aggregate_metrics
        
        passes_sharpe = agg.get('mean_sharpe', 0) >= min_sharpe
        passes_consistency = agg.get('sharpe_consistency', 0) >= min_consistency
        not_overfit = agg.get('overfit_ratio', 1) < 0.3
        
        is_robust = passes_sharpe and passes_consistency and not_overfit
        
        if not is_robust:
            reasons = []
            if not passes_sharpe:
                reasons.append(f"Sharpe {agg.get('mean_sharpe', 0):.2f} < {min_sharpe}")
            if not passes_consistency:
                reasons.append(f"Consistency {agg.get('sharpe_consistency', 0):.1%} < {min_consistency:.1%}")
            if not not_overfit:
                reasons.append(f"Overfit ratio {agg.get('overfit_ratio', 0):.1%} >= 30%")
            
            logger.warning(f"Strategy failed robustness check: {'; '.join(reasons)}")
        
        return is_robust


# ============== CONVENIENCE FUNCTIONS ==============

def walk_forward_validate(
    data: 'pd.DataFrame',
    train_func: Callable,
    evaluate_func: Callable,
    n_splits: int = 12,
    train_months: int = 6,
    val_months: int = 1,
    embargo_days: int = 5,
    method: str = 'rolling'
) -> WalkForwardReport:
    """
    Run walk-forward validation with provided train/evaluate functions.
    
    Args:
        data: DataFrame with time-series data
        train_func: Function that takes train_df and returns a model
        evaluate_func: Function that takes (model, df) and returns metrics dict
        n_splits: Number of validation splits
        train_months: Training window in months
        val_months: Validation window in months
        embargo_days: Gap between train and validation
        method: Validation method ('rolling', 'expanding', 'purged_kfold')
        
    Returns:
        WalkForwardReport with results
        
    Example:
    -------
    >>> def train(df):
    ...     model = MyModel()
    ...     model.fit(df['features'], df['target'])
    ...     return model
    >>>
    >>> def evaluate(model, df):
    ...     preds = model.predict(df['features'])
    ...     return {
    ...         'sharpe_ratio': calculate_sharpe(preds, df['returns']),
    ...         'win_rate': calculate_win_rate(preds, df['target'])
    ...     }
    >>>
    >>> report = walk_forward_validate(data, train, evaluate)
    >>> print(report.summary())
    """
    import time
    
    method_enum = ValidationMethod(method)
    
    validator = WalkForwardValidator(
        method=method_enum,
        n_splits=n_splits,
        train_period_months=train_months,
        validation_period_months=val_months,
        embargo_days=embargo_days
    )
    
    for split, train_df, val_df in validator.generate_splits(data):
        # Train
        start_time = time.time()
        model = train_func(train_df)
        training_time = time.time() - start_time
        
        # Evaluate on both sets
        train_metrics = evaluate_func(model, train_df)
        val_metrics = evaluate_func(model, val_df)
        
        # Record
        validator.record_result(
            split_id=split.split_id,
            train_metrics=train_metrics,
            validation_metrics=val_metrics,
            training_time=training_time
        )
    
    return validator.get_report()


def generate_walk_forward_splits(
    data: 'pd.DataFrame',
    n_splits: int = 12,
    train_months: int = 6,
    val_months: int = 1,
    embargo_days: int = 5
) -> List[Tuple['pd.DataFrame', 'pd.DataFrame']]:
    """
    Simple function to generate walk-forward splits.
    
    Returns:
        List of (train_df, validation_df) tuples
    """
    validator = WalkForwardValidator(
        method=ValidationMethod.ROLLING,
        n_splits=n_splits,
        train_period_months=train_months,
        validation_period_months=val_months,
        embargo_days=embargo_days
    )
    
    splits = []
    for split, train_df, val_df in validator.generate_splits(data):
        splits.append((train_df, val_df))
    
    return splits
