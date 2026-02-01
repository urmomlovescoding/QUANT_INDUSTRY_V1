"""
Diversification Optimizer - HRP-Style Portfolio Diversification

This module provides Hierarchical Risk Parity (HRP) and related
optimization methods for portfolio diversification.

Key Features:
- Hierarchical Risk Parity (HRP) allocation
- Hierarchical clustering of assets
- Risk-based diversification
- Correlation-aware rebalancing
- Cluster-based position limits

Reference:
    López de Prado, M. (2016). Building Diversified Portfolios that
    Outperform Out of Sample. The Journal of Portfolio Management.

Usage:
    from strategies.diversification_optimizer import DiversificationOptimizer

    optimizer = DiversificationOptimizer()
    weights = optimizer.hrp_optimize(returns_df)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


@dataclass
class DiversificationConfig:
    """Configuration for diversification optimizer."""
    linkage_method: str = 'ward'
    risk_metric: str = 'variance'  # 'variance', 'mad', 'cvar'
    min_weight: float = 0.01
    max_weight: float = 0.30
    cluster_weight_limit: float = 0.50
    rebalance_threshold: float = 0.05


@dataclass
class HRPResult:
    """Results from HRP optimization."""
    weights: Dict[str, float]
    clustering: np.ndarray
    linkage_matrix: np.ndarray
    cluster_assignments: Dict[str, int]
    risk_contribution: Dict[str, float]
    diversification_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'weights': self.weights,
            'cluster_assignments': self.cluster_assignments,
            'risk_contribution': self.risk_contribution,
            'diversification_ratio': self.diversification_ratio,
        }


class DiversificationOptimizer:
    """
    Portfolio diversification optimizer using HRP and clustering.

    Implements Hierarchical Risk Parity (HRP) for robust portfolio
    allocation that doesn't rely on inverse covariance matrix.

    Example:
        optimizer = DiversificationOptimizer()

        # HRP optimization
        result = optimizer.hrp_optimize(returns_df)
        print(f"Weights: {result.weights}")

        # Get cluster-aware allocation
        weights = optimizer.get_cluster_aware_weights(
            returns_df,
            target_cluster_risk=0.2
        )
    """

    def __init__(self, config: Optional[DiversificationConfig] = None):
        self.config = config or DiversificationConfig()
        self._last_result: Optional[HRPResult] = None

    def hrp_optimize(
        self,
        returns: pd.DataFrame,
        covariance: Optional[pd.DataFrame] = None,
    ) -> HRPResult:
        """
        Perform Hierarchical Risk Parity optimization.

        Args:
            returns: DataFrame of asset returns
            covariance: Optional precomputed covariance matrix

        Returns:
            HRPResult with optimized weights
        """
        # Step 1: Compute correlation and covariance
        if covariance is None:
            covariance = returns.cov()
        correlation = returns.corr()

        # Step 2: Hierarchical clustering
        dist_matrix = self._correlation_to_distance(correlation)
        link = linkage(squareform(dist_matrix), method=self.config.linkage_method)

        # Step 3: Quasi-diagonalization
        sorted_indices = self._get_quasi_diag(link)
        sorted_columns = [returns.columns[i] for i in sorted_indices]

        # Step 4: Recursive bisection
        weights = self._recursive_bisection(
            covariance.loc[sorted_columns, sorted_columns]
        )

        # Apply constraints
        weights = self._apply_weight_constraints(weights)

        # Compute cluster assignments
        cluster_assignments = self._get_cluster_assignments(
            link, returns.columns.tolist()
        )

        # Compute risk contributions
        risk_contribution = self._compute_risk_contribution(
            weights, covariance
        )

        # Compute diversification ratio
        div_ratio = self._compute_diversification_ratio(
            weights, returns.std(), covariance
        )

        result = HRPResult(
            weights=weights,
            clustering=sorted_indices,
            linkage_matrix=link,
            cluster_assignments=cluster_assignments,
            risk_contribution=risk_contribution,
            diversification_ratio=div_ratio,
        )

        self._last_result = result
        return result

    def _correlation_to_distance(self, correlation: pd.DataFrame) -> np.ndarray:
        """Convert correlation matrix to distance matrix."""
        # Distance = sqrt(0.5 * (1 - correlation))
        dist = np.sqrt(0.5 * (1 - correlation))
        np.fill_diagonal(dist.values, 0)
        return dist.values

    def _get_quasi_diag(self, link: np.ndarray) -> List[int]:
        """
        Quasi-diagonalization: sort assets by hierarchical clustering.

        Returns leaves sorted to place similar assets together.
        """
        # Number of original items
        n = link.shape[0] + 1
        sorted_indices = [int(link[-1, 0]), int(link[-1, 1])]

        while True:
            expanded = []
            for i in sorted_indices:
                if i >= n:
                    # This is a cluster, expand it
                    j = int(link[i - n, 0])
                    k = int(link[i - n, 1])
                    expanded.extend([j, k])
                else:
                    # This is a leaf
                    expanded.append(i)
            sorted_indices = expanded

            if all(i < n for i in sorted_indices):
                break

        return sorted_indices

    def _recursive_bisection(self, covariance: pd.DataFrame) -> Dict[str, float]:
        """
        Recursive bisection for weight allocation.

        Recursively splits the portfolio and allocates weights
        based on inverse variance.
        """
        assets = covariance.columns.tolist()
        weights = pd.Series(1.0, index=assets)

        clusters = [assets]

        while True:
            new_clusters = []

            for cluster in clusters:
                if len(cluster) > 1:
                    # Split cluster in half
                    mid = len(cluster) // 2
                    left = cluster[:mid]
                    right = cluster[mid:]

                    # Compute cluster variances
                    left_var = self._get_cluster_variance(
                        covariance.loc[left, left], weights[left]
                    )
                    right_var = self._get_cluster_variance(
                        covariance.loc[right, right], weights[right]
                    )

                    # Allocate by inverse variance
                    total_var = left_var + right_var
                    if total_var > 0:
                        alpha = 1 - left_var / total_var
                    else:
                        alpha = 0.5

                    weights[left] *= alpha
                    weights[right] *= (1 - alpha)

                    new_clusters.extend([left, right])
                else:
                    new_clusters.append(cluster)

            if len(new_clusters) == len(assets):
                break

            clusters = new_clusters

        return weights.to_dict()

    def _get_cluster_variance(
        self,
        covariance: pd.DataFrame,
        weights: pd.Series,
    ) -> float:
        """Compute variance of a cluster."""
        # Normalize weights within cluster
        w = weights / weights.sum()
        return float(np.dot(w, np.dot(covariance, w)))

    def _apply_weight_constraints(
        self,
        weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply min/max weight constraints."""
        # Clip weights
        constrained = {}
        for asset, weight in weights.items():
            constrained[asset] = np.clip(
                weight,
                self.config.min_weight,
                self.config.max_weight
            )

        # Renormalize
        total = sum(constrained.values())
        return {k: v / total for k, v in constrained.items()}

    def _get_cluster_assignments(
        self,
        link: np.ndarray,
        assets: List[str],
        max_clusters: int = 5,
    ) -> Dict[str, int]:
        """Assign assets to clusters."""
        cluster_labels = fcluster(link, max_clusters, criterion='maxclust')
        return dict(zip(assets, cluster_labels.tolist()))

    def _compute_risk_contribution(
        self,
        weights: Dict[str, float],
        covariance: pd.DataFrame,
    ) -> Dict[str, float]:
        """Compute marginal risk contribution of each asset."""
        w = np.array([weights[c] for c in covariance.columns])
        cov = covariance.values

        # Portfolio variance
        port_var = np.dot(w, np.dot(cov, w))

        if port_var <= 0:
            return {c: 1.0 / len(weights) for c in weights}

        # Marginal contribution
        marginal = np.dot(cov, w)
        risk_contrib = w * marginal / port_var

        return dict(zip(covariance.columns, risk_contrib.tolist()))

    def _compute_diversification_ratio(
        self,
        weights: Dict[str, float],
        volatilities: pd.Series,
        covariance: pd.DataFrame,
    ) -> float:
        """Compute diversification ratio."""
        w = np.array([weights[c] for c in covariance.columns])
        vols = volatilities.values

        # Weighted average volatility
        weighted_vol = np.dot(w, vols)

        # Portfolio volatility
        port_var = np.dot(w, np.dot(covariance.values, w))
        port_vol = np.sqrt(port_var)

        if port_vol > 0:
            return float(weighted_vol / port_vol)
        return 1.0

    def get_cluster_aware_weights(
        self,
        returns: pd.DataFrame,
        target_cluster_risk: float = 0.2,
        n_clusters: int = 5,
    ) -> Dict[str, float]:
        """
        Get weights with cluster-based risk budgeting.

        Args:
            returns: DataFrame of returns
            target_cluster_risk: Maximum risk per cluster
            n_clusters: Number of clusters

        Returns:
            Dictionary of asset weights
        """
        # First, run HRP
        result = self.hrp_optimize(returns)

        # Get cluster assignments
        link = result.linkage_matrix
        cluster_labels = fcluster(link, n_clusters, criterion='maxclust')

        # Compute cluster weights
        assets = returns.columns.tolist()
        cluster_weights = {}

        for i in range(1, n_clusters + 1):
            cluster_assets = [a for a, c in zip(assets, cluster_labels) if c == i]
            cluster_weight = sum(result.weights[a] for a in cluster_assets)
            cluster_weights[i] = cluster_weight

        # Cap cluster weights
        weights = result.weights.copy()
        for i, cluster_weight in cluster_weights.items():
            if cluster_weight > self.config.cluster_weight_limit:
                # Scale down cluster
                scale = self.config.cluster_weight_limit / cluster_weight
                cluster_assets = [a for a, c in zip(assets, cluster_labels) if c == i]
                for a in cluster_assets:
                    weights[a] *= scale

        # Renormalize
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}

    def inverse_volatility_weights(
        self,
        returns: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Simple inverse volatility weighting.

        Args:
            returns: DataFrame of returns

        Returns:
            Dictionary of weights
        """
        vols = returns.std()
        inv_vols = 1 / vols

        # Normalize
        weights = inv_vols / inv_vols.sum()

        return weights.to_dict()

    def equal_risk_contribution(
        self,
        returns: pd.DataFrame,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> Dict[str, float]:
        """
        Equal Risk Contribution (Risk Parity) optimization.

        Args:
            returns: DataFrame of returns
            max_iterations: Maximum iterations for optimization
            tolerance: Convergence tolerance

        Returns:
            Dictionary of weights
        """
        cov = returns.cov().values
        n = cov.shape[0]

        # Start with equal weights
        w = np.ones(n) / n
        target_risk = 1.0 / n

        for _ in range(max_iterations):
            # Compute risk contributions
            port_vol = np.sqrt(np.dot(w, np.dot(cov, w)))
            marginal = np.dot(cov, w) / port_vol
            risk_contrib = w * marginal / port_vol

            # Compute gradient
            diff = risk_contrib - target_risk

            # Check convergence
            if np.max(np.abs(diff)) < tolerance:
                break

            # Update weights (gradient descent)
            w = w * (target_risk / risk_contrib) ** 0.5

            # Normalize
            w = w / w.sum()

        return dict(zip(returns.columns, w.tolist()))

    def maximum_diversification_portfolio(
        self,
        returns: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Maximum Diversification Portfolio (MDP).

        Maximizes the diversification ratio.

        Args:
            returns: DataFrame of returns

        Returns:
            Dictionary of weights
        """
        cov = returns.cov().values
        vols = returns.std().values
        n = len(vols)

        # Start with inverse volatility
        w = 1 / vols
        w = w / w.sum()

        # Iterative optimization
        for _ in range(100):
            port_vol = np.sqrt(np.dot(w, np.dot(cov, w)))

            # Gradient of diversification ratio
            grad = vols / port_vol - np.dot(vols, w) * np.dot(cov, w) / (port_vol ** 3)

            # Update
            w = w + 0.01 * grad
            w = np.clip(w, self.config.min_weight, self.config.max_weight)
            w = w / w.sum()

        return dict(zip(returns.columns, w.tolist()))

    def get_rebalance_signals(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Get rebalancing trades based on threshold.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target weights from optimizer

        Returns:
            Dictionary of required weight changes
        """
        trades = {}

        for asset in target_weights:
            current = current_weights.get(asset, 0)
            target = target_weights[asset]
            diff = target - current

            if abs(diff) > self.config.rebalance_threshold:
                trades[asset] = diff

        return trades

    def analyze_diversification(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Comprehensive diversification analysis.

        Args:
            returns: DataFrame of returns
            weights: Portfolio weights

        Returns:
            Dictionary with diversification metrics
        """
        cov = returns.cov()
        corr = returns.corr()
        vols = returns.std()

        w = np.array([weights.get(c, 0) for c in returns.columns])

        # Portfolio metrics
        port_var = np.dot(w, np.dot(cov.values, w))
        port_vol = np.sqrt(port_var)

        # Diversification ratio
        weighted_vol = np.dot(w, vols.values)
        div_ratio = weighted_vol / port_vol if port_vol > 0 else 1.0

        # Effective number of bets
        risk_contrib = self._compute_risk_contribution(weights, cov)
        rc_array = np.array(list(risk_contrib.values()))
        rc_array = np.clip(rc_array, 1e-10, 1.0)  # Avoid log(0)
        effective_n = np.exp(-np.sum(rc_array * np.log(rc_array)))

        # Average correlation
        n = len(corr)
        upper_corr = corr.values[np.triu_indices(n, k=1)]
        avg_corr = np.mean(upper_corr)

        # Concentration (Herfindahl index)
        concentration = np.sum(w ** 2)

        return {
            'portfolio_volatility': float(port_vol),
            'diversification_ratio': float(div_ratio),
            'effective_number_of_bets': float(effective_n),
            'average_correlation': float(avg_corr),
            'concentration_index': float(concentration),
            'risk_contribution': risk_contrib,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        stats = {
            'has_last_result': self._last_result is not None,
        }

        if self._last_result:
            stats['last_diversification_ratio'] = self._last_result.diversification_ratio
            stats['last_n_assets'] = len(self._last_result.weights)

        return stats
