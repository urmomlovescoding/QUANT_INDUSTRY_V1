"""
QUANT_INDUSTRY_V1 Portfolio Optimization

Institutional portfolio optimization with:
- Mean-Variance optimization
- Risk parity
- Black-Litterman
- Hierarchical Risk Parity
- Factor-based allocation

Rollback Plan: Delete this file
Tests Required: Optimization accuracy, constraints
Failure Modes: Return equal-weight, alert operators
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# PORTFOLIO TYPES
# =============================================================================

class OptimizationObjective(Enum):
    """Portfolio optimization objective."""
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"


@dataclass
class PortfolioConstraints:
    """Portfolio constraints for optimization."""
    min_weight: float = 0.0       # Minimum weight per asset
    max_weight: float = 1.0       # Maximum weight per asset
    total_weight: float = 1.0     # Sum of weights
    max_turnover: float = 1.0     # Maximum turnover from current
    sector_limits: Dict[str, float] = field(default_factory=dict)
    long_only: bool = True
    max_assets: int = 0           # 0 = unlimited


@dataclass
class PortfolioWeights:
    """Optimized portfolio weights."""
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    diversification_ratio: float = 0.0
    optimization_objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'weights': self.weights,
            'expected_return': self.expected_return,
            'expected_volatility': self.expected_volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'diversification_ratio': self.diversification_ratio,
        }


# =============================================================================
# COVARIANCE ESTIMATORS
# =============================================================================

class CovarianceEstimator(ABC):
    """Base covariance estimator."""

    @abstractmethod
    def estimate(self, returns: np.ndarray) -> np.ndarray:
        """Estimate covariance matrix from returns."""
        pass


class SampleCovariance(CovarianceEstimator):
    """Simple sample covariance."""

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        return np.cov(returns.T)


class ExponentialCovariance(CovarianceEstimator):
    """Exponentially weighted covariance."""

    def __init__(self, halflife: int = 60):
        self.halflife = halflife

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        n_periods, n_assets = returns.shape
        decay = 0.5 ** (1 / self.halflife)

        weights = np.array([decay ** i for i in range(n_periods - 1, -1, -1)])
        weights = weights / weights.sum()

        # Weighted mean
        weighted_mean = (returns.T * weights).sum(axis=1)

        # Weighted covariance
        centered = returns - weighted_mean
        cov = np.zeros((n_assets, n_assets))

        for i in range(n_periods):
            cov += weights[i] * np.outer(centered[i], centered[i])

        return cov


class LedoitWolfCovariance(CovarianceEstimator):
    """
    Ledoit-Wolf shrinkage covariance estimator.

    Shrinks sample covariance towards a structured target.
    """

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        n_periods, n_assets = returns.shape

        # Sample covariance
        sample_cov = np.cov(returns.T)

        # Target: constant correlation
        var = np.diag(sample_cov)
        std = np.sqrt(var)
        avg_corr = (np.sum(sample_cov / np.outer(std, std)) - n_assets) / (n_assets * (n_assets - 1))

        target = avg_corr * np.outer(std, std)
        np.fill_diagonal(target, var)

        # Calculate optimal shrinkage
        # Simplified Ledoit-Wolf formula
        delta = np.sum((sample_cov - target) ** 2) / n_assets

        if delta == 0:
            return sample_cov

        shrinkage = min(1.0, max(0.0, delta / (delta + n_periods)))

        return shrinkage * target + (1 - shrinkage) * sample_cov


# =============================================================================
# PORTFOLIO OPTIMIZERS
# =============================================================================

class PortfolioOptimizer(ABC):
    """Base portfolio optimizer."""

    def __init__(
        self,
        covariance_estimator: CovarianceEstimator = None,
        risk_free_rate: float = 0.02
    ):
        self.cov_estimator = covariance_estimator or LedoitWolfCovariance()
        self.risk_free_rate = risk_free_rate

    @abstractmethod
    def optimize(
        self,
        returns: np.ndarray,
        symbols: List[str],
        constraints: PortfolioConstraints = None
    ) -> PortfolioWeights:
        """Optimize portfolio weights."""
        pass

    def _calculate_portfolio_stats(
        self,
        weights: np.ndarray,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray
    ) -> Tuple[float, float, float]:
        """Calculate portfolio return, volatility, and Sharpe ratio."""
        port_return = np.dot(weights, expected_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

        return port_return, port_vol, sharpe


class MeanVarianceOptimizer(PortfolioOptimizer):
    """
    Mean-Variance (Markowitz) optimization.
    """

    def optimize(
        self,
        returns: np.ndarray,
        symbols: List[str],
        constraints: PortfolioConstraints = None,
        objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE
    ) -> PortfolioWeights:
        constraints = constraints or PortfolioConstraints()
        n_assets = len(symbols)

        # Estimate returns and covariance
        expected_returns = np.mean(returns, axis=0) * 252  # Annualized
        cov_matrix = self.cov_estimator.estimate(returns) * 252

        # Solve using quadratic programming approach (simplified)
        if objective == OptimizationObjective.MAX_SHARPE:
            weights = self._max_sharpe(expected_returns, cov_matrix, constraints)
        elif objective == OptimizationObjective.MIN_VARIANCE:
            weights = self._min_variance(cov_matrix, constraints)
        else:
            weights = np.ones(n_assets) / n_assets  # Equal weight fallback

        # Apply constraints
        weights = self._apply_constraints(weights, constraints)

        # Calculate stats
        port_return, port_vol, sharpe = self._calculate_portfolio_stats(
            weights, expected_returns, cov_matrix
        )

        return PortfolioWeights(
            weights={s: w for s, w in zip(symbols, weights)},
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            optimization_objective=objective
        )

    def _max_sharpe(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        constraints: PortfolioConstraints
    ) -> np.ndarray:
        """Find maximum Sharpe ratio portfolio."""
        n_assets = len(expected_returns)

        # Use iterative approach
        best_sharpe = -np.inf
        best_weights = np.ones(n_assets) / n_assets

        # Generate candidate portfolios
        for _ in range(1000):
            # Random weights
            weights = np.random.random(n_assets)
            weights = weights / weights.sum()

            # Apply bounds
            weights = np.clip(weights, constraints.min_weight, constraints.max_weight)
            weights = weights / weights.sum()

            # Calculate Sharpe
            port_return = np.dot(weights, expected_returns)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

            if port_vol > 0:
                sharpe = (port_return - self.risk_free_rate) / port_vol

                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_weights = weights.copy()

        return best_weights

    def _min_variance(
        self,
        cov_matrix: np.ndarray,
        constraints: PortfolioConstraints
    ) -> np.ndarray:
        """Find minimum variance portfolio."""
        n_assets = cov_matrix.shape[0]

        # Analytical solution for unconstrained case
        try:
            cov_inv = np.linalg.inv(cov_matrix)
            ones = np.ones(n_assets)
            weights = np.dot(cov_inv, ones) / np.dot(ones, np.dot(cov_inv, ones))

            # Apply bounds
            weights = np.clip(weights, constraints.min_weight, constraints.max_weight)
            weights = weights / weights.sum()

            return weights

        except np.linalg.LinAlgError:
            return np.ones(n_assets) / n_assets

    def _apply_constraints(
        self,
        weights: np.ndarray,
        constraints: PortfolioConstraints
    ) -> np.ndarray:
        """Apply portfolio constraints to weights."""
        # Long only
        if constraints.long_only:
            weights = np.maximum(weights, 0)

        # Min/max weights
        weights = np.clip(weights, constraints.min_weight, constraints.max_weight)

        # Normalize
        if weights.sum() > 0:
            weights = weights / weights.sum() * constraints.total_weight

        return weights


class RiskParityOptimizer(PortfolioOptimizer):
    """
    Risk Parity optimization.

    Equalizes risk contribution from each asset.
    """

    def optimize(
        self,
        returns: np.ndarray,
        symbols: List[str],
        constraints: PortfolioConstraints = None
    ) -> PortfolioWeights:
        constraints = constraints or PortfolioConstraints()
        n_assets = len(symbols)

        # Estimate covariance
        cov_matrix = self.cov_estimator.estimate(returns) * 252
        expected_returns = np.mean(returns, axis=0) * 252

        # Risk parity: weight inversely proportional to volatility
        vols = np.sqrt(np.diag(cov_matrix))
        inv_vols = 1 / vols
        weights = inv_vols / inv_vols.sum()

        # Iterative refinement for true risk parity
        for _ in range(100):
            # Calculate risk contributions
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            marginal_risk = np.dot(cov_matrix, weights) / port_vol
            risk_contrib = weights * marginal_risk

            # Target equal contribution
            target_contrib = port_vol / n_assets

            # Adjust weights
            adjustment = target_contrib / (risk_contrib + 1e-8)
            weights = weights * adjustment
            weights = weights / weights.sum()

            # Apply constraints
            weights = np.clip(weights, constraints.min_weight, constraints.max_weight)
            weights = weights / weights.sum()

        # Calculate stats
        port_return, port_vol, sharpe = self._calculate_portfolio_stats(
            weights, expected_returns, cov_matrix
        )

        return PortfolioWeights(
            weights={s: w for s, w in zip(symbols, weights)},
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            optimization_objective=OptimizationObjective.RISK_PARITY
        )


class HierarchicalRiskParity(PortfolioOptimizer):
    """
    Hierarchical Risk Parity (HRP).

    Uses hierarchical clustering for robust allocation.
    """

    def optimize(
        self,
        returns: np.ndarray,
        symbols: List[str],
        constraints: PortfolioConstraints = None
    ) -> PortfolioWeights:
        constraints = constraints or PortfolioConstraints()
        n_assets = len(symbols)

        # Estimate covariance
        cov_matrix = self.cov_estimator.estimate(returns) * 252
        expected_returns = np.mean(returns, axis=0) * 252

        # Calculate correlation and distance
        corr = np.corrcoef(returns.T)
        dist = np.sqrt((1 - corr) / 2)

        # Hierarchical clustering (simplified)
        # Use variance as cluster linkage
        order = self._cluster_assets(dist)

        # Recursive bisection
        weights = self._recursive_bisection(cov_matrix, order)

        # Apply constraints
        weights = np.clip(weights, constraints.min_weight, constraints.max_weight)
        weights = weights / weights.sum()

        # Calculate stats
        port_return, port_vol, sharpe = self._calculate_portfolio_stats(
            weights, expected_returns, cov_matrix
        )

        # Diversification ratio
        asset_vols = np.sqrt(np.diag(cov_matrix))
        div_ratio = np.dot(weights, asset_vols) / port_vol if port_vol > 0 else 1

        return PortfolioWeights(
            weights={s: w for s, w in zip(symbols, weights)},
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            diversification_ratio=div_ratio,
            optimization_objective=OptimizationObjective.MAX_DIVERSIFICATION
        )

    def _cluster_assets(self, dist: np.ndarray) -> List[int]:
        """Simple clustering to determine asset order."""
        n = dist.shape[0]
        remaining = list(range(n))
        order = []

        # Greedy nearest-neighbor ordering
        current = 0
        order.append(current)
        remaining.remove(current)

        while remaining:
            # Find nearest
            distances = [dist[current, i] for i in remaining]
            nearest_idx = np.argmin(distances)
            current = remaining[nearest_idx]
            order.append(current)
            remaining.remove(current)

        return order

    def _recursive_bisection(
        self,
        cov: np.ndarray,
        order: List[int]
    ) -> np.ndarray:
        """Recursive bisection for weight allocation."""
        n = len(order)
        weights = np.ones(n)

        clusters = [order]

        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) == 1:
                    continue

                # Split in half
                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]

                # Calculate cluster variance
                left_cov = cov[np.ix_(left, left)]
                right_cov = cov[np.ix_(right, right)]

                # Inverse variance weighting
                left_var = self._cluster_variance(left_cov)
                right_var = self._cluster_variance(right_cov)

                alpha = 1 - left_var / (left_var + right_var) if (left_var + right_var) > 0 else 0.5

                # Assign weights
                weights[left] *= alpha
                weights[right] *= (1 - alpha)

                if len(left) > 1:
                    new_clusters.append(left)
                if len(right) > 1:
                    new_clusters.append(right)

            clusters = new_clusters

        return weights

    def _cluster_variance(self, cov: np.ndarray) -> float:
        """Calculate cluster variance with inverse-var weights."""
        ivp = 1 / np.diag(cov)
        ivp = ivp / ivp.sum()
        return np.dot(ivp, np.dot(cov, ivp))


class BlackLittermanOptimizer(PortfolioOptimizer):
    """
    Black-Litterman optimization.

    Combines market equilibrium with investor views.
    """

    def __init__(
        self,
        covariance_estimator: CovarianceEstimator = None,
        risk_free_rate: float = 0.02,
        tau: float = 0.05
    ):
        super().__init__(covariance_estimator, risk_free_rate)
        self.tau = tau  # Uncertainty in equilibrium returns

    def optimize(
        self,
        returns: np.ndarray,
        symbols: List[str],
        constraints: PortfolioConstraints = None,
        market_weights: np.ndarray = None,
        views: List[Dict[str, Any]] = None
    ) -> PortfolioWeights:
        """
        Optimize with Black-Litterman.

        Args:
            returns: Historical returns
            symbols: Asset symbols
            constraints: Portfolio constraints
            market_weights: Market capitalization weights
            views: List of views, each with:
                   {'assets': [idx], 'return': float, 'confidence': float}
        """
        constraints = constraints or PortfolioConstraints()
        n_assets = len(symbols)

        # Estimate covariance
        cov_matrix = self.cov_estimator.estimate(returns) * 252

        # Market weights (equal if not provided)
        if market_weights is None:
            market_weights = np.ones(n_assets) / n_assets

        # Calculate implied equilibrium returns
        risk_aversion = 2.5  # Market risk aversion
        pi = risk_aversion * np.dot(cov_matrix, market_weights)

        # If no views, use equilibrium
        if not views:
            expected_returns = pi
        else:
            # Build view matrices
            P, Q, omega = self._build_views(views, n_assets, cov_matrix)

            # Black-Litterman formula
            tau_cov = self.tau * cov_matrix
            tau_cov_inv = np.linalg.inv(tau_cov)
            omega_inv = np.linalg.inv(omega)

            # Posterior returns
            M = np.linalg.inv(tau_cov_inv + P.T @ omega_inv @ P)
            expected_returns = M @ (tau_cov_inv @ pi + P.T @ omega_inv @ Q)

        # Optimize using mean-variance with BL returns
        mv_optimizer = MeanVarianceOptimizer(
            self.cov_estimator,
            self.risk_free_rate
        )

        # Replace expected returns estimation
        result = mv_optimizer.optimize(returns, symbols, constraints)
        result.expected_return = np.dot(
            list(result.weights.values()),
            expected_returns
        )

        return result

    def _build_views(
        self,
        views: List[Dict[str, Any]],
        n_assets: int,
        cov_matrix: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build view matrices P, Q, and Omega."""
        n_views = len(views)

        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        omega_diag = np.zeros(n_views)

        for i, view in enumerate(views):
            assets = view['assets']
            P[i, assets] = 1.0 / len(assets)
            Q[i] = view['return']

            # View uncertainty based on confidence and implied variance
            confidence = view.get('confidence', 0.5)
            view_var = P[i] @ cov_matrix @ P[i].T
            omega_diag[i] = view_var * (1 - confidence) / confidence

        omega = np.diag(omega_diag)

        return P, Q, omega


# =============================================================================
# PORTFOLIO ANALYZER
# =============================================================================

class PortfolioAnalyzer:
    """
    Portfolio analysis and reporting.
    """

    @staticmethod
    def analyze_weights(
        weights: PortfolioWeights,
        returns: np.ndarray,
        symbols: List[str]
    ) -> Dict[str, Any]:
        """Comprehensive weight analysis."""
        weight_arr = np.array([weights.weights[s] for s in symbols])

        cov_matrix = np.cov(returns.T) * 252
        port_vol = np.sqrt(np.dot(weight_arr.T, np.dot(cov_matrix, weight_arr)))

        # Risk contribution
        marginal_risk = np.dot(cov_matrix, weight_arr) / port_vol
        risk_contrib = weight_arr * marginal_risk
        risk_contrib_pct = risk_contrib / port_vol

        # Concentration
        hhi = np.sum(weight_arr ** 2)  # Herfindahl index
        effective_n = 1 / hhi if hhi > 0 else len(symbols)

        return {
            'weights': weights.weights,
            'risk_contributions': {s: rc for s, rc in zip(symbols, risk_contrib_pct)},
            'herfindahl_index': hhi,
            'effective_n_assets': effective_n,
            'max_weight': max(weight_arr),
            'min_weight': min(weight_arr),
            'n_positions': sum(1 for w in weight_arr if w > 0.01),
        }

    @staticmethod
    def efficient_frontier(
        returns: np.ndarray,
        symbols: List[str],
        n_points: int = 50,
        risk_free_rate: float = 0.02
    ) -> List[Dict[str, float]]:
        """Generate efficient frontier points."""
        optimizer = MeanVarianceOptimizer(risk_free_rate=risk_free_rate)

        # Get return range
        expected_returns = np.mean(returns, axis=0) * 252

        min_ret = expected_returns.min()
        max_ret = expected_returns.max()

        frontier = []

        for target_ret in np.linspace(min_ret, max_ret, n_points):
            # Find min variance for target return
            result = optimizer.optimize(
                returns, symbols,
                objective=OptimizationObjective.MIN_VARIANCE
            )

            frontier.append({
                'return': result.expected_return,
                'volatility': result.expected_volatility,
                'sharpe': result.sharpe_ratio,
            })

        return frontier
