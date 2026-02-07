"""
QUANT INDUSTRY - Portfolio Optimization
========================================
Modern portfolio optimization techniques:
- Mean-Variance (Markowitz)
- Black-Litterman
- Risk Parity
- Hierarchical Risk Parity (HRP)
- Maximum Sharpe
- Minimum Variance
- Maximum Diversification

These are what hedge funds actually use.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import optimize
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """Portfolio optimization methods"""
    MEAN_VARIANCE = "mean_variance"
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    RISK_PARITY = "risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"
    BLACK_LITTERMAN = "black_litterman"
    HRP = "hrp"  # Hierarchical Risk Parity
    EQUAL_WEIGHT = "equal_weight"


@dataclass
class PortfolioAllocation:
    """Result of portfolio optimization"""
    weights: np.ndarray
    asset_names: List[str]
    method: OptimizationMethod
    
    # Performance metrics
    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Risk metrics
    max_weight: float = 0.0
    min_weight: float = 0.0
    effective_n: float = 0.0  # Effective number of assets
    
    # Diversification
    diversification_ratio: float = 0.0
    concentration: float = 0.0  # Herfindahl index
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to asset: weight dict"""
        return {name: float(w) for name, w in zip(self.asset_names, self.weights)}
    
    def summary(self) -> str:
        top_5 = sorted(zip(self.asset_names, self.weights), key=lambda x: -x[1])[:5]
        
        return f"""
Portfolio Allocation ({self.method.value})
{'='*50}
Expected Return: {self.expected_return:.2%}
Volatility: {self.volatility:.2%}
Sharpe Ratio: {self.sharpe_ratio:.2f}

Diversification:
  Effective N: {self.effective_n:.1f}
  Diversification Ratio: {self.diversification_ratio:.2f}
  Concentration (HHI): {self.concentration:.3f}

Top 5 Positions:
""" + "\n".join([f"  {name}: {w:.1%}" for name, w in top_5])


@dataclass
class BlackLittermanViews:
    """Views for Black-Litterman model"""
    # P matrix: which assets are involved in each view
    pick_matrix: np.ndarray
    # Q vector: expected returns for each view
    view_returns: np.ndarray
    # Omega: uncertainty of views (diagonal covariance)
    view_confidence: np.ndarray


class PortfolioOptimizer:
    """
    Modern portfolio optimization engine.
    
    Implements multiple optimization methods from basic Markowitz
    to advanced techniques like Black-Litterman and HRP.
    
    Usage:
    ------
    >>> optimizer = PortfolioOptimizer(
    ...     returns=historical_returns_df,
    ...     risk_free_rate=0.05
    ... )
    >>> 
    >>> # Maximum Sharpe portfolio
    >>> result = optimizer.optimize(OptimizationMethod.MAX_SHARPE)
    >>> print(result.summary())
    >>>
    >>> # Risk Parity
    >>> rp_result = optimizer.optimize(OptimizationMethod.RISK_PARITY)
    >>> print(f"Weights: {rp_result.to_dict()}")
    >>>
    >>> # Black-Litterman with views
    >>> views = BlackLittermanViews(
    ...     pick_matrix=np.array([[1, -1, 0]]),  # Asset 0 vs Asset 1
    ...     view_returns=np.array([0.02]),        # Asset 0 outperforms by 2%
    ...     view_confidence=np.array([0.001])
    ... )
    >>> bl_result = optimizer.optimize(
    ...     OptimizationMethod.BLACK_LITTERMAN,
    ...     views=views
    ... )
    """
    
    def __init__(
        self,
        returns: np.ndarray,
        asset_names: List[str] = None,
        risk_free_rate: float = 0.05,
        covariance: np.ndarray = None,
        expected_returns: np.ndarray = None
    ):
        """
        Initialize optimizer.
        
        Args:
            returns: Historical returns matrix (n_periods x n_assets)
            asset_names: Names for each asset
            risk_free_rate: Annual risk-free rate
            covariance: Optional pre-computed covariance matrix
            expected_returns: Optional expected returns vector
        """
        self.returns = np.array(returns)
        self.n_assets = self.returns.shape[1] if len(self.returns.shape) > 1 else 1
        self.asset_names = asset_names or [f"Asset_{i}" for i in range(self.n_assets)]
        self.risk_free_rate = risk_free_rate
        
        # Compute or use provided covariance
        if covariance is not None:
            self.cov_matrix = np.array(covariance)
        else:
            self.cov_matrix = np.cov(self.returns.T) * 252  # Annualize
        
        # Ensure covariance is 2D
        if len(self.cov_matrix.shape) == 0:
            self.cov_matrix = np.array([[self.cov_matrix]])
        
        # Expected returns
        if expected_returns is not None:
            self.expected_returns = np.array(expected_returns)
        else:
            self.expected_returns = np.mean(self.returns, axis=0) * 252  # Annualize
        
        # Correlation matrix
        std = np.sqrt(np.diag(self.cov_matrix))
        std_outer = np.outer(std, std)
        self.corr_matrix = self.cov_matrix / std_outer
        np.fill_diagonal(self.corr_matrix, 1.0)
        
        logger.info(f"PortfolioOptimizer: {self.n_assets} assets")
    
    def optimize(
        self,
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        constraints: Dict = None,
        views: BlackLittermanViews = None,
        target_return: float = None,
        target_volatility: float = None
    ) -> PortfolioAllocation:
        """
        Optimize portfolio allocation.
        
        Args:
            method: Optimization method to use
            constraints: Dict with 'min_weight', 'max_weight', 'long_only'
            views: Views for Black-Litterman model
            target_return: Target return for mean-variance
            target_volatility: Target volatility constraint
            
        Returns:
            PortfolioAllocation with optimal weights
        """
        constraints = constraints or {}
        min_weight = constraints.get('min_weight', 0.0)
        max_weight = constraints.get('max_weight', 1.0)
        long_only = constraints.get('long_only', True)
        
        if long_only:
            min_weight = max(min_weight, 0.0)
        
        # Dispatch to method
        if method == OptimizationMethod.EQUAL_WEIGHT:
            weights = self._equal_weight()
        elif method == OptimizationMethod.MIN_VARIANCE:
            weights = self._min_variance(min_weight, max_weight)
        elif method == OptimizationMethod.MAX_SHARPE:
            weights = self._max_sharpe(min_weight, max_weight)
        elif method == OptimizationMethod.RISK_PARITY:
            weights = self._risk_parity()
        elif method == OptimizationMethod.MAX_DIVERSIFICATION:
            weights = self._max_diversification(min_weight, max_weight)
        elif method == OptimizationMethod.BLACK_LITTERMAN:
            weights = self._black_litterman(views, min_weight, max_weight)
        elif method == OptimizationMethod.HRP:
            weights = self._hierarchical_risk_parity()
        elif method == OptimizationMethod.MEAN_VARIANCE:
            weights = self._mean_variance(target_return, min_weight, max_weight)
        else:
            weights = self._equal_weight()
        
        # Calculate metrics
        return self._create_allocation(weights, method)
    
    def _equal_weight(self) -> np.ndarray:
        """Equal weight allocation"""
        return np.ones(self.n_assets) / self.n_assets
    
    def _min_variance(self, min_w: float, max_w: float) -> np.ndarray:
        """Minimum variance portfolio"""
        def portfolio_variance(weights):
            return np.dot(weights, np.dot(self.cov_matrix, weights))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        bounds = [(min_w, max_w) for _ in range(self.n_assets)]
        
        x0 = self._equal_weight()
        result = optimize.minimize(
            portfolio_variance,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _max_sharpe(self, min_w: float, max_w: float) -> np.ndarray:
        """Maximum Sharpe ratio portfolio"""
        def neg_sharpe(weights):
            ret = np.dot(weights, self.expected_returns)
            vol = np.sqrt(np.dot(weights, np.dot(self.cov_matrix, weights)))
            return -(ret - self.risk_free_rate) / vol if vol > 0 else 0
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        bounds = [(min_w, max_w) for _ in range(self.n_assets)]
        
        x0 = self._equal_weight()
        result = optimize.minimize(
            neg_sharpe,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _risk_parity(self) -> np.ndarray:
        """
        Risk parity: equal risk contribution from each asset.
        
        Each asset contributes equally to total portfolio risk.
        """
        def risk_contribution(weights):
            port_var = np.dot(weights, np.dot(self.cov_matrix, weights))
            port_vol = np.sqrt(port_var)
            
            # Marginal risk contribution
            marginal = np.dot(self.cov_matrix, weights) / port_vol
            
            # Risk contribution
            rc = weights * marginal
            
            # Target: equal risk contribution
            target_rc = port_vol / self.n_assets
            
            return np.sum((rc - target_rc) ** 2)
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        bounds = [(0.001, 1.0) for _ in range(self.n_assets)]
        
        x0 = self._equal_weight()
        result = optimize.minimize(
            risk_contribution,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _max_diversification(self, min_w: float, max_w: float) -> np.ndarray:
        """
        Maximum diversification portfolio.
        
        Maximizes the diversification ratio: 
        (weighted average vol) / (portfolio vol)
        """
        asset_vols = np.sqrt(np.diag(self.cov_matrix))
        
        def neg_diversification_ratio(weights):
            weighted_vol = np.dot(weights, asset_vols)
            port_vol = np.sqrt(np.dot(weights, np.dot(self.cov_matrix, weights)))
            return -weighted_vol / port_vol if port_vol > 0 else 0
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]
        bounds = [(min_w, max_w) for _ in range(self.n_assets)]
        
        x0 = self._equal_weight()
        result = optimize.minimize(
            neg_diversification_ratio,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _black_litterman(
        self,
        views: BlackLittermanViews,
        min_w: float,
        max_w: float
    ) -> np.ndarray:
        """
        Black-Litterman model.
        
        Combines market equilibrium with investor views.
        """
        # Market capitalization weights (use equal if not provided)
        market_weights = self._equal_weight()
        
        # Risk aversion parameter
        delta = (np.mean(self.expected_returns) - self.risk_free_rate) / np.var(self.expected_returns)
        delta = max(delta, 1.0)  # Reasonable default
        
        # Implied equilibrium returns
        pi = delta * np.dot(self.cov_matrix, market_weights)
        
        if views is None:
            # No views - just use equilibrium
            bl_returns = pi
        else:
            # Tau: uncertainty of prior
            tau = 0.05
            
            P = views.pick_matrix
            Q = views.view_returns
            omega = np.diag(views.view_confidence)
            
            # Black-Litterman formula
            tau_sigma = tau * self.cov_matrix
            
            # M = [(tau*Sigma)^-1 + P'*Omega^-1*P]^-1
            inv_tau_sigma = np.linalg.inv(tau_sigma)
            inv_omega = np.linalg.inv(omega)
            
            M = np.linalg.inv(inv_tau_sigma + P.T @ inv_omega @ P)
            
            # BL expected returns
            bl_returns = M @ (inv_tau_sigma @ pi + P.T @ inv_omega @ Q)
        
        # Optimize with BL returns
        original_returns = self.expected_returns.copy()
        self.expected_returns = bl_returns
        weights = self._max_sharpe(min_w, max_w)
        self.expected_returns = original_returns
        
        return weights
    
    def _hierarchical_risk_parity(self) -> np.ndarray:
        """
        Hierarchical Risk Parity (HRP).
        
        Lopez de Prado's method that uses hierarchical clustering
        to allocate risk without needing to invert the covariance matrix.
        """
        # Step 1: Tree clustering
        dist = self._correlation_distance()
        link = hierarchy.linkage(squareform(dist), method='single')
        sort_ix = hierarchy.leaves_list(hierarchy.optimal_leaf_ordering(link, squareform(dist)))
        
        # Step 2: Quasi-diagonalization
        sorted_cov = self.cov_matrix[sort_ix][:, sort_ix]
        
        # Step 3: Recursive bisection
        weights = np.zeros(self.n_assets)
        self._recursive_bisection(weights, sort_ix, sorted_cov)
        
        # Reorder weights back
        final_weights = np.zeros(self.n_assets)
        for i, ix in enumerate(sort_ix):
            final_weights[ix] = weights[i]
        
        return final_weights
    
    def _correlation_distance(self) -> np.ndarray:
        """Calculate correlation distance matrix"""
        return np.sqrt((1 - self.corr_matrix) / 2)
    
    def _recursive_bisection(
        self,
        weights: np.ndarray,
        indices: np.ndarray,
        cov: np.ndarray
    ):
        """Recursive bisection for HRP"""
        if len(indices) == 1:
            weights[0] = 1.0
            return
        
        # Split indices
        mid = len(indices) // 2
        left_ix = list(range(mid))
        right_ix = list(range(mid, len(indices)))
        
        # Calculate cluster variances
        left_cov = cov[np.ix_(left_ix, left_ix)]
        right_cov = cov[np.ix_(right_ix, right_ix)]
        
        left_var = self._cluster_variance(left_cov)
        right_var = self._cluster_variance(right_cov)
        
        # Allocate
        alpha = 1 - left_var / (left_var + right_var)
        
        # Initialize weights
        left_weights = np.zeros(mid)
        right_weights = np.zeros(len(indices) - mid)
        
        # Recurse
        if mid > 1:
            self._recursive_bisection(left_weights, indices[:mid], left_cov)
        else:
            left_weights[0] = 1.0
        
        if len(indices) - mid > 1:
            self._recursive_bisection(right_weights, indices[mid:], right_cov)
        else:
            right_weights[0] = 1.0
        
        # Combine
        weights[:mid] = alpha * left_weights
        weights[mid:] = (1 - alpha) * right_weights
    
    def _cluster_variance(self, cov: np.ndarray) -> float:
        """Calculate inverse-variance weighted cluster variance"""
        ivp = 1 / np.diag(cov)
        ivp /= ivp.sum()
        return np.dot(ivp, np.dot(cov, ivp))
    
    def _mean_variance(
        self,
        target_return: float,
        min_w: float,
        max_w: float
    ) -> np.ndarray:
        """Mean-variance optimization with target return"""
        if target_return is None:
            return self._max_sharpe(min_w, max_w)
        
        def portfolio_variance(weights):
            return np.dot(weights, np.dot(self.cov_matrix, weights))
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'eq', 'fun': lambda x: np.dot(x, self.expected_returns) - target_return}
        ]
        bounds = [(min_w, max_w) for _ in range(self.n_assets)]
        
        x0 = self._equal_weight()
        result = optimize.minimize(
            portfolio_variance,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else x0
    
    def _create_allocation(
        self,
        weights: np.ndarray,
        method: OptimizationMethod
    ) -> PortfolioAllocation:
        """Create allocation object with metrics"""
        weights = np.array(weights)
        
        # Ensure weights sum to 1
        weights = weights / np.sum(weights) if np.sum(weights) > 0 else self._equal_weight()
        
        # Calculate metrics
        exp_ret = np.dot(weights, self.expected_returns)
        vol = np.sqrt(np.dot(weights, np.dot(self.cov_matrix, weights)))
        sharpe = (exp_ret - self.risk_free_rate) / vol if vol > 0 else 0
        
        # Diversification
        asset_vols = np.sqrt(np.diag(self.cov_matrix))
        weighted_vol = np.dot(weights, asset_vols)
        div_ratio = weighted_vol / vol if vol > 0 else 1
        
        # Concentration (Herfindahl)
        concentration = np.sum(weights ** 2)
        
        # Effective N
        effective_n = 1 / concentration if concentration > 0 else self.n_assets
        
        return PortfolioAllocation(
            weights=weights,
            asset_names=self.asset_names,
            method=method,
            expected_return=exp_ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            max_weight=np.max(weights),
            min_weight=np.min(weights),
            effective_n=effective_n,
            diversification_ratio=div_ratio,
            concentration=concentration
        )
    
    def efficient_frontier(
        self,
        n_points: int = 50,
        min_w: float = 0.0,
        max_w: float = 1.0
    ) -> List[PortfolioAllocation]:
        """
        Generate efficient frontier.
        
        Args:
            n_points: Number of portfolios on frontier
            min_w: Minimum weight
            max_w: Maximum weight
            
        Returns:
            List of allocations along the frontier
        """
        # Get min and max return portfolios
        min_vol = self.optimize(OptimizationMethod.MIN_VARIANCE)
        max_ret = self.optimize(OptimizationMethod.MAX_SHARPE)
        
        min_return = min_vol.expected_return
        max_return = max_ret.expected_return
        
        target_returns = np.linspace(min_return, max_return, n_points)
        
        frontier = []
        for target in target_returns:
            try:
                alloc = self.optimize(
                    OptimizationMethod.MEAN_VARIANCE,
                    target_return=target,
                    constraints={'min_weight': min_w, 'max_weight': max_w}
                )
                frontier.append(alloc)
            except Exception as e:
                logger.debug(f"Frontier point at target return {target:.4f} failed: {e}")
                continue
        
        return frontier


# ============== CONVENIENCE FUNCTIONS ==============

def optimize_portfolio(
    returns: np.ndarray,
    method: str = "max_sharpe",
    risk_free_rate: float = 0.05
) -> Dict[str, float]:
    """
    Quick portfolio optimization.
    
    Args:
        returns: Historical returns (n_periods x n_assets)
        method: "max_sharpe", "min_variance", "risk_parity", "hrp"
        risk_free_rate: Risk-free rate
        
    Returns:
        Dict of asset index: weight
    """
    method_map = {
        "max_sharpe": OptimizationMethod.MAX_SHARPE,
        "min_variance": OptimizationMethod.MIN_VARIANCE,
        "risk_parity": OptimizationMethod.RISK_PARITY,
        "hrp": OptimizationMethod.HRP,
        "equal": OptimizationMethod.EQUAL_WEIGHT,
    }
    
    optimizer = PortfolioOptimizer(returns, risk_free_rate=risk_free_rate)
    result = optimizer.optimize(method_map.get(method, OptimizationMethod.MAX_SHARPE))
    
    return result.to_dict()
