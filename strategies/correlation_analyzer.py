"""
Correlation Analyzer - Rolling Correlation Analysis for Strategy Diversification

This module provides comprehensive correlation analysis tools for
strategy diversification and portfolio construction.

Key Features:
- Rolling correlation computation
- Correlation regime detection
- Correlation breakdown analysis
- Dynamic correlation forecasting
- Diversification scoring

Usage:
    from strategies.correlation_analyzer import CorrelationAnalyzer

    analyzer = CorrelationAnalyzer()
    correlations = analyzer.compute_rolling_correlations(returns_df)
    diversification_score = analyzer.get_diversification_score(correlations)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CorrelationConfig:
    """Configuration for correlation analysis."""
    short_window: int = 21
    medium_window: int = 63
    long_window: int = 252
    min_periods: int = 10
    correlation_threshold_high: float = 0.7
    correlation_threshold_low: float = 0.3
    regime_change_threshold: float = 0.2


@dataclass
class CorrelationMetrics:
    """Container for correlation analysis results."""
    timestamp: datetime
    correlation_matrix: pd.DataFrame
    avg_correlation: float
    max_correlation: float
    min_correlation: float
    diversification_ratio: float
    correlation_cluster_count: int
    regime: str  # 'high_correlation', 'low_correlation', 'normal'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'avg_correlation': self.avg_correlation,
            'max_correlation': self.max_correlation,
            'min_correlation': self.min_correlation,
            'diversification_ratio': self.diversification_ratio,
            'correlation_cluster_count': self.correlation_cluster_count,
            'regime': self.regime,
        }


class CorrelationAnalyzer:
    """
    Comprehensive correlation analyzer for strategy diversification.

    Provides rolling correlation analysis, regime detection, and
    diversification scoring for portfolio construction.

    Example:
        analyzer = CorrelationAnalyzer()

        # Compute rolling correlations
        rolling_corr = analyzer.compute_rolling_correlations(returns_df, window=63)

        # Detect correlation regimes
        regimes = analyzer.detect_correlation_regimes(rolling_corr)

        # Get diversification score
        score = analyzer.get_diversification_score(returns_df)
    """

    def __init__(self, config: Optional[CorrelationConfig] = None):
        self.config = config or CorrelationConfig()
        self._correlation_history: List[CorrelationMetrics] = []

    def compute_rolling_correlations(
        self,
        returns: pd.DataFrame,
        window: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Compute rolling correlations at multiple time horizons.

        Args:
            returns: DataFrame of returns (columns are assets/strategies)
            window: Optional custom window

        Returns:
            Dictionary with correlation DataFrames for each window
        """
        windows = {
            'short': window or self.config.short_window,
            'medium': self.config.medium_window,
            'long': self.config.long_window,
        }

        results = {}

        for name, w in windows.items():
            # Compute rolling correlation for each pair
            n_assets = len(returns.columns)
            rolling_corr = {}

            for i in range(n_assets):
                for j in range(i + 1, n_assets):
                    col_i = returns.columns[i]
                    col_j = returns.columns[j]
                    pair_name = f"{col_i}_{col_j}"

                    rolling_corr[pair_name] = returns[col_i].rolling(
                        window=w,
                        min_periods=self.config.min_periods
                    ).corr(returns[col_j])

            results[name] = pd.DataFrame(rolling_corr)

        return results

    def compute_correlation_matrix(
        self,
        returns: pd.DataFrame,
        window: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Compute correlation matrix for latest period.

        Args:
            returns: DataFrame of returns
            window: Lookback window

        Returns:
            Correlation matrix DataFrame
        """
        window = window or self.config.medium_window

        if len(returns) < window:
            return returns.corr()

        return returns.tail(window).corr()

    def detect_correlation_regimes(
        self,
        rolling_correlations: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Detect correlation regime changes.

        Args:
            rolling_correlations: DataFrame of rolling correlations

        Returns:
            DataFrame with regime labels and change points
        """
        avg_corr = rolling_correlations.mean(axis=1)

        # Classify regimes
        regimes = pd.Series(index=avg_corr.index, dtype=str)
        regimes[avg_corr >= self.config.correlation_threshold_high] = 'high_correlation'
        regimes[avg_corr <= self.config.correlation_threshold_low] = 'low_correlation'
        regimes[(avg_corr > self.config.correlation_threshold_low) &
                (avg_corr < self.config.correlation_threshold_high)] = 'normal'

        # Detect regime changes
        regime_changes = regimes != regimes.shift(1)

        # Detect correlation spikes
        corr_change = avg_corr.diff().abs()
        spikes = corr_change > self.config.regime_change_threshold

        return pd.DataFrame({
            'avg_correlation': avg_corr,
            'regime': regimes,
            'regime_change': regime_changes,
            'correlation_spike': spikes,
        })

    def compute_correlation_breakdown(
        self,
        returns: pd.DataFrame,
        crisis_threshold: float = -0.02,
    ) -> Dict[str, Any]:
        """
        Analyze how correlations change during market stress.

        Args:
            returns: DataFrame of returns
            crisis_threshold: Return threshold to identify stress periods

        Returns:
            Dictionary with normal and stress period correlations
        """
        # Identify stress periods (using portfolio/market proxy)
        market_return = returns.mean(axis=1)
        stress_mask = market_return < crisis_threshold
        normal_mask = ~stress_mask

        # Compute correlations for each regime
        if stress_mask.sum() >= self.config.min_periods:
            stress_corr = returns[stress_mask].corr()
        else:
            stress_corr = None

        if normal_mask.sum() >= self.config.min_periods:
            normal_corr = returns[normal_mask].corr()
        else:
            normal_corr = None

        # Compute correlation increase during stress
        if stress_corr is not None and normal_corr is not None:
            corr_increase = stress_corr - normal_corr
            avg_increase = corr_increase.values[np.triu_indices_from(corr_increase, k=1)].mean()
        else:
            corr_increase = None
            avg_increase = None

        return {
            'normal_correlation': normal_corr,
            'stress_correlation': stress_corr,
            'correlation_increase': corr_increase,
            'avg_correlation_increase': avg_increase,
            'stress_period_count': stress_mask.sum(),
            'normal_period_count': normal_mask.sum(),
        }

    def get_diversification_score(
        self,
        returns: pd.DataFrame,
        weights: Optional[np.ndarray] = None,
    ) -> float:
        """
        Compute diversification score (diversification ratio).

        Higher score means better diversification.

        Args:
            returns: DataFrame of returns
            weights: Portfolio weights (equal weight if None)

        Returns:
            Diversification ratio (>1 indicates diversification benefit)
        """
        if weights is None:
            weights = np.ones(len(returns.columns)) / len(returns.columns)

        weights = np.array(weights)

        # Compute covariance matrix
        cov_matrix = returns.cov()

        # Weighted average volatility
        vols = returns.std()
        weighted_avg_vol = np.dot(weights, vols)

        # Portfolio volatility
        portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
        portfolio_vol = np.sqrt(portfolio_var)

        # Diversification ratio
        if portfolio_vol > 0:
            div_ratio = weighted_avg_vol / portfolio_vol
        else:
            div_ratio = 1.0

        return float(div_ratio)

    def find_correlation_clusters(
        self,
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7,
    ) -> List[List[str]]:
        """
        Find clusters of highly correlated assets.

        Args:
            correlation_matrix: Correlation matrix
            threshold: Correlation threshold for clustering

        Returns:
            List of clusters (each cluster is a list of asset names)
        """
        assets = correlation_matrix.columns.tolist()
        n = len(assets)
        visited = [False] * n
        clusters = []

        def dfs(idx: int, cluster: List[int]) -> None:
            visited[idx] = True
            cluster.append(idx)

            for j in range(n):
                if not visited[j] and correlation_matrix.iloc[idx, j] >= threshold:
                    dfs(j, cluster)

        for i in range(n):
            if not visited[i]:
                cluster = []
                dfs(i, cluster)
                if len(cluster) > 1:
                    clusters.append([assets[idx] for idx in cluster])

        return clusters

    def compute_effective_correlation(
        self,
        returns: pd.DataFrame,
    ) -> float:
        """
        Compute effective correlation (average pairwise correlation).

        Args:
            returns: DataFrame of returns

        Returns:
            Effective correlation value
        """
        corr_matrix = returns.corr()
        n = len(corr_matrix)

        if n <= 1:
            return 0.0

        # Extract upper triangle (excluding diagonal)
        upper_triangle = corr_matrix.values[np.triu_indices(n, k=1)]

        return float(np.mean(upper_triangle))

    def forecast_correlation(
        self,
        rolling_correlations: pd.DataFrame,
        horizon: int = 5,
    ) -> pd.DataFrame:
        """
        Simple correlation forecast using exponential smoothing.

        Args:
            rolling_correlations: Historical rolling correlations
            horizon: Forecast horizon

        Returns:
            Forecasted correlations
        """
        # Use exponential smoothing
        alpha = 0.3
        smoothed = rolling_correlations.ewm(alpha=alpha).mean()

        # Extrapolate (simple approach - use last smoothed value)
        last_values = smoothed.iloc[-1]

        forecast_index = pd.date_range(
            start=rolling_correlations.index[-1],
            periods=horizon + 1,
            freq='D'
        )[1:]

        forecast = pd.DataFrame(
            {col: [last_values[col]] * horizon for col in rolling_correlations.columns},
            index=forecast_index
        )

        return forecast

    def analyze(
        self,
        returns: pd.DataFrame,
    ) -> CorrelationMetrics:
        """
        Perform comprehensive correlation analysis.

        Args:
            returns: DataFrame of returns

        Returns:
            CorrelationMetrics object with analysis results
        """
        # Compute correlation matrix
        corr_matrix = self.compute_correlation_matrix(returns)

        # Extract upper triangle values
        n = len(corr_matrix)
        upper_values = corr_matrix.values[np.triu_indices(n, k=1)]

        # Compute metrics
        avg_corr = float(np.mean(upper_values))
        max_corr = float(np.max(upper_values))
        min_corr = float(np.min(upper_values))

        # Diversification ratio
        div_ratio = self.get_diversification_score(returns)

        # Find clusters
        clusters = self.find_correlation_clusters(corr_matrix)

        # Determine regime
        if avg_corr >= self.config.correlation_threshold_high:
            regime = 'high_correlation'
        elif avg_corr <= self.config.correlation_threshold_low:
            regime = 'low_correlation'
        else:
            regime = 'normal'

        metrics = CorrelationMetrics(
            timestamp=datetime.now(timezone.utc),
            correlation_matrix=corr_matrix,
            avg_correlation=avg_corr,
            max_correlation=max_corr,
            min_correlation=min_corr,
            diversification_ratio=div_ratio,
            correlation_cluster_count=len(clusters),
            regime=regime,
        )

        self._correlation_history.append(metrics)

        return metrics

    def get_low_correlation_pairs(
        self,
        returns: pd.DataFrame,
        n_pairs: int = 5,
    ) -> List[Tuple[str, str, float]]:
        """
        Find pairs with lowest correlation for diversification.

        Args:
            returns: DataFrame of returns
            n_pairs: Number of pairs to return

        Returns:
            List of tuples (asset1, asset2, correlation)
        """
        corr_matrix = self.compute_correlation_matrix(returns)
        assets = corr_matrix.columns.tolist()
        n = len(assets)

        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append((
                    assets[i],
                    assets[j],
                    corr_matrix.iloc[i, j]
                ))

        # Sort by correlation (lowest first)
        pairs.sort(key=lambda x: x[2])

        return pairs[:n_pairs]

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        if not self._correlation_history:
            return {'history_length': 0}

        recent = self._correlation_history[-100:]

        return {
            'history_length': len(self._correlation_history),
            'avg_correlation_trend': np.mean([m.avg_correlation for m in recent]),
            'diversification_trend': np.mean([m.diversification_ratio for m in recent]),
            'current_regime': self._correlation_history[-1].regime if self._correlation_history else None,
        }
