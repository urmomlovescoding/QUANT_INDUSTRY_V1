"""
Portfolio Optimization Mathematics
==================================
Modern portfolio theory, risk parity, and advanced allocation.

Includes:
- Mean-Variance Optimization (Markowitz)
- Black-Litterman Model
- Risk Parity / Hierarchical Risk Parity
- Kelly Criterion
- CVaR Optimization
"""

import numpy as np
from scipy.optimize import minimize, LinearConstraint
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform
from typing import Optional, Tuple, Dict, List
import logging

logger = logging.getLogger(__name__)


class MeanVarianceOptimizer:
    """
    Markowitz Mean-Variance Optimization.
    
    Maximize: w'μ - (λ/2)w'Σw
    Subject to: Σw = 1, w ≥ 0 (optional)
    
    Efficient frontier: min w'Σw s.t. w'μ = μ_target, Σw = 1
    """
    
    def __init__(
        self,
        returns: np.ndarray,  # (T, n_assets)
        risk_free_rate: float = 0.0
    ):
        self.returns = returns
        self.n_assets = returns.shape[1]
        self.rf = risk_free_rate
        
        # Estimate moments
        self.mu = np.mean(returns, axis=0)  # Expected returns
        self.Sigma = np.cov(returns.T)       # Covariance matrix
        
        # Ensure positive semi-definite
        eigvals = np.linalg.eigvalsh(self.Sigma)
        if np.min(eigvals) < 0:
            self.Sigma += (-np.min(eigvals) + 1e-6) * np.eye(self.n_assets)
    
    def max_sharpe(self, allow_short: bool = False) -> Tuple[np.ndarray, Dict]:
        """
        Find maximum Sharpe ratio portfolio.
        
        max (w'μ - rf) / sqrt(w'Σw)
        """
        def neg_sharpe(w):
            ret = w @ self.mu
            vol = np.sqrt(w @ self.Sigma @ w)
            return -(ret - self.rf) / (vol + 1e-10)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Weights sum to 1
        ]
        
        # Bounds
        if allow_short:
            bounds = [(-1, 1) for _ in range(self.n_assets)]
        else:
            bounds = [(0, 1) for _ in range(self.n_assets)]
        
        # Initial guess: equal weight
        w0 = np.ones(self.n_assets) / self.n_assets
        
        result = minimize(
            neg_sharpe, w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        w_opt = result.x
        ret = w_opt @ self.mu
        vol = np.sqrt(w_opt @ self.Sigma @ w_opt)
        sharpe = (ret - self.rf) / vol
        
        return w_opt, {
            'return': ret,
            'volatility': vol,
            'sharpe': sharpe
        }
    
    def min_variance(self, target_return: Optional[float] = None) -> Tuple[np.ndarray, Dict]:
        """
        Minimum variance portfolio (optionally with target return).
        
        min w'Σw s.t. w'1 = 1, w'μ = target (optional)
        """
        def portfolio_variance(w):
            return w @ self.Sigma @ w
        
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        ]
        
        if target_return is not None:
            constraints.append(
                {'type': 'eq', 'fun': lambda w: w @ self.mu - target_return}
            )
        
        bounds = [(0, 1) for _ in range(self.n_assets)]
        w0 = np.ones(self.n_assets) / self.n_assets
        
        result = minimize(
            portfolio_variance, w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        w_opt = result.x
        ret = w_opt @ self.mu
        vol = np.sqrt(w_opt @ self.Sigma @ w_opt)
        
        return w_opt, {'return': ret, 'volatility': vol}
    
    def efficient_frontier(self, n_points: int = 50) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute efficient frontier.
        
        Returns arrays of returns, volatilities, and weights.
        """
        # Find min and max return portfolios
        w_min_var, _ = self.min_variance()
        min_ret = w_min_var @ self.mu
        max_ret = np.max(self.mu)
        
        target_returns = np.linspace(min_ret, max_ret * 0.95, n_points)
        
        frontier_returns = []
        frontier_vols = []
        frontier_weights = []
        
        for target in target_returns:
            try:
                w, metrics = self.min_variance(target_return=target)
                frontier_returns.append(metrics['return'])
                frontier_vols.append(metrics['volatility'])
                frontier_weights.append(w)
            except:
                continue
        
        return (
            np.array(frontier_returns),
            np.array(frontier_vols),
            np.array(frontier_weights)
        )


class BlackLitterman:
    """
    Black-Litterman Model for combining market equilibrium with views.
    
    Prior: μ ~ N(Π, τΣ)  where Π = δΣw_mkt (equilibrium returns)
    Views: Pμ = Q + ε, ε ~ N(0, Ω)
    
    Posterior: μ|views ~ N(μ_BL, Σ_BL)
    
    μ_BL = [(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹ [(τΣ)⁻¹Π + P'Ω⁻¹Q]
    """
    
    def __init__(
        self,
        Sigma: np.ndarray,          # Covariance matrix
        market_caps: np.ndarray,    # Market capitalizations
        risk_aversion: float = 2.5, # δ
        tau: float = 0.05           # Uncertainty in equilibrium
    ):
        self.Sigma = Sigma
        self.n_assets = len(market_caps)
        self.delta = risk_aversion
        self.tau = tau
        
        # Market weights
        self.w_mkt = market_caps / market_caps.sum()
        
        # Implied equilibrium returns: Π = δΣw_mkt
        self.Pi = self.delta * self.Sigma @ self.w_mkt
    
    def add_views(
        self,
        P: np.ndarray,      # View matrix (K x N)
        Q: np.ndarray,      # View returns (K,)
        confidence: np.ndarray  # View confidences (K,)
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Incorporate investor views.
        
        P: Each row is a view (e.g., [1, -1, 0, 0] = asset 0 outperforms asset 1)
        Q: Expected return for each view
        confidence: Confidence in each view (higher = more certain)
        
        Returns posterior mean and covariance.
        """
        K = len(Q)
        
        # View uncertainty: Ω = diag(1/confidence) * (P @ (τΣ) @ P')
        # Simplified: diagonal Ω based on confidence
        omega_diag = (1 / confidence) * np.diag(P @ (self.tau * self.Sigma) @ P.T)
        Omega = np.diag(omega_diag)
        
        # Precision matrices
        tau_Sigma_inv = np.linalg.inv(self.tau * self.Sigma)
        Omega_inv = np.diag(1 / omega_diag)
        
        # Posterior precision
        posterior_precision = tau_Sigma_inv + P.T @ Omega_inv @ P
        posterior_Sigma = np.linalg.inv(posterior_precision)
        
        # Posterior mean
        posterior_mu = posterior_Sigma @ (
            tau_Sigma_inv @ self.Pi + P.T @ Omega_inv @ Q
        )
        
        return posterior_mu, posterior_Sigma
    
    def optimal_weights(
        self,
        P: np.ndarray,
        Q: np.ndarray,
        confidence: np.ndarray
    ) -> np.ndarray:
        """Get optimal weights incorporating views."""
        mu_BL, Sigma_BL = self.add_views(P, Q, confidence)
        
        # Optimal weights: w* = (δΣ)⁻¹ μ_BL
        w_opt = np.linalg.solve(self.delta * self.Sigma, mu_BL)
        
        # Normalize
        w_opt = w_opt / np.sum(np.abs(w_opt))
        
        return w_opt


class RiskParity:
    """
    Risk Parity / Equal Risk Contribution Portfolio.
    
    Each asset contributes equally to portfolio risk:
    RC_i = w_i * (Σw)_i / sqrt(w'Σw) = σ_p / n
    
    Equivalent to: min Σ(RC_i - RC_j)² 
                   or min Σ(log(w_i(Σw)_i) - log(w_j(Σw)_j))²
    """
    
    def __init__(self, Sigma: np.ndarray):
        self.Sigma = Sigma
        self.n_assets = Sigma.shape[0]
    
    def risk_contribution(self, w: np.ndarray) -> np.ndarray:
        """Compute risk contribution of each asset."""
        portfolio_vol = np.sqrt(w @ self.Sigma @ w)
        marginal_risk = self.Sigma @ w
        risk_contrib = w * marginal_risk / portfolio_vol
        return risk_contrib
    
    def optimize(self, target_risk: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Find risk parity weights.
        
        target_risk: Target risk contribution per asset (default: equal)
        """
        if target_risk is None:
            target_risk = np.ones(self.n_assets) / self.n_assets
        
        def objective(w):
            rc = self.risk_contribution(w)
            # Minimize squared difference from target
            return np.sum((rc - target_risk * np.sum(rc)) ** 2)
        
        # Log-barrier to ensure positivity
        def objective_with_barrier(log_w):
            w = np.exp(log_w)
            w = w / w.sum()
            return objective(w)
        
        log_w0 = np.zeros(self.n_assets)
        
        result = minimize(objective_with_barrier, log_w0, method='BFGS')
        
        w_opt = np.exp(result.x)
        w_opt = w_opt / w_opt.sum()
        
        return w_opt


class HierarchicalRiskParity:
    """
    Hierarchical Risk Parity (HRP) - Lopez de Prado.
    
    Uses hierarchical clustering to build diversified portfolios
    without requiring covariance matrix inversion.
    
    Steps:
    1. Cluster assets by correlation distance
    2. Quasi-diagonalize covariance matrix
    3. Recursive bisection for weights
    """
    
    def __init__(self, returns: np.ndarray):
        self.returns = returns
        self.n_assets = returns.shape[1]
        
        # Correlation and covariance
        self.corr = np.corrcoef(returns.T)
        self.cov = np.cov(returns.T)
        
        # Correlation distance
        self.dist = np.sqrt(0.5 * (1 - self.corr))
    
    def _cluster(self) -> np.ndarray:
        """Hierarchical clustering of assets."""
        dist_condensed = squareform(self.dist)
        link = linkage(dist_condensed, method='single')
        sort_idx = leaves_list(link)
        return sort_idx
    
    def _recursive_bisection(self, sort_idx: np.ndarray) -> np.ndarray:
        """Recursive bisection to allocate weights."""
        weights = np.ones(self.n_assets)
        clusters = [sort_idx]
        
        while clusters:
            new_clusters = []
            
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                
                # Split cluster
                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]
                
                # Variance of each sub-cluster
                var_left = self._cluster_variance(left)
                var_right = self._cluster_variance(right)
                
                # Allocate inversely proportional to variance
                alpha = var_right / (var_left + var_right)
                
                weights[left] *= alpha
                weights[right] *= (1 - alpha)
                
                new_clusters.extend([left, right])
            
            clusters = [c for c in new_clusters if len(c) > 1]
        
        return weights / weights.sum()
    
    def _cluster_variance(self, indices: np.ndarray) -> float:
        """Compute variance of cluster (inverse-variance weighted)."""
        sub_cov = self.cov[np.ix_(indices, indices)]
        ivp = 1 / np.diag(sub_cov)
        ivp = ivp / ivp.sum()
        return ivp @ sub_cov @ ivp
    
    def optimize(self) -> np.ndarray:
        """Get HRP optimal weights."""
        sort_idx = self._cluster()
        weights = self._recursive_bisection(sort_idx)
        return weights


class KellyCriterion:
    """
    Kelly Criterion for optimal bet sizing.
    
    For a single bet with win prob p and odds b:
        f* = (bp - q) / b = p - q/b
    
    For continuous returns:
        f* = μ / σ² (full Kelly)
        
    In practice, use fractional Kelly (f*/2 or f*/4) for safety.
    """
    
    @staticmethod
    def single_bet(win_prob: float, odds: float) -> float:
        """
        Kelly fraction for single binary bet.
        
        win_prob: Probability of winning
        odds: Payout ratio (win $b for every $1 bet)
        """
        q = 1 - win_prob
        kelly = (odds * win_prob - q) / odds
        return max(0, kelly)  # Don't bet negative
    
    @staticmethod
    def continuous(mu: float, sigma: float, risk_free: float = 0) -> float:
        """
        Kelly fraction for continuous returns.
        
        f* = (μ - r) / σ²
        """
        excess_return = mu - risk_free
        kelly = excess_return / (sigma ** 2 + 1e-10)
        return kelly
    
    @staticmethod
    def portfolio(
        mu: np.ndarray,
        Sigma: np.ndarray,
        risk_free: float = 0
    ) -> np.ndarray:
        """
        Kelly weights for portfolio.
        
        w* = Σ⁻¹(μ - r)
        """
        excess = mu - risk_free
        kelly_weights = np.linalg.solve(Sigma, excess)
        return kelly_weights
    
    @staticmethod
    def fractional(kelly: float, fraction: float = 0.5) -> float:
        """Apply fractional Kelly for safety."""
        return kelly * fraction


class CVaROptimizer:
    """
    Conditional Value-at-Risk (CVaR) Optimization.
    
    CVaR (Expected Shortfall) = E[Loss | Loss > VaR]
    
    More coherent risk measure than VaR.
    Can be optimized via linear programming.
    """
    
    def __init__(
        self,
        returns: np.ndarray,
        alpha: float = 0.05  # Tail probability
    ):
        self.returns = returns
        self.n_assets = returns.shape[1]
        self.T = returns.shape[0]
        self.alpha = alpha
    
    def compute_cvar(self, weights: np.ndarray) -> Tuple[float, float]:
        """Compute VaR and CVaR for given weights."""
        portfolio_returns = self.returns @ weights
        
        # Sort returns
        sorted_returns = np.sort(portfolio_returns)
        
        # VaR: α-quantile of losses
        var_idx = int(self.alpha * self.T)
        var = -sorted_returns[var_idx]
        
        # CVaR: mean of losses beyond VaR
        cvar = -np.mean(sorted_returns[:var_idx + 1])
        
        return var, cvar
    
    def optimize(
        self,
        target_return: Optional[float] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Minimize CVaR subject to constraints.
        
        Uses sample-based approximation.
        """
        def cvar_objective(w):
            _, cvar = self.compute_cvar(w)
            return cvar
        
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        ]
        
        if target_return is not None:
            mu = np.mean(self.returns, axis=0)
            constraints.append(
                {'type': 'ineq', 'fun': lambda w: w @ mu - target_return}
            )
        
        bounds = [(0, 1) for _ in range(self.n_assets)]
        w0 = np.ones(self.n_assets) / self.n_assets
        
        result = minimize(
            cvar_objective, w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        w_opt = result.x
        var, cvar = self.compute_cvar(w_opt)
        
        return w_opt, {
            'VaR': var,
            'CVaR': cvar,
            'expected_return': np.mean(self.returns @ w_opt)
        }
