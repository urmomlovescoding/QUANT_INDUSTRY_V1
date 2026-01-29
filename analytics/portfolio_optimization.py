"""
QUANT_INDUSTRY_V1 Advanced Portfolio Optimization

Sophisticated portfolio construction and optimization techniques.

Features:
- Risk Parity (Equal Risk Contribution)
- Black-Litterman Model
- Hierarchical Risk Parity (HRP)
- Mean-CVaR Optimization
- Robust Optimization
- Factor-based Allocation
- Kelly Criterion
- Max Diversification
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PortfolioResult:
    """Portfolio optimization result."""
    weights: np.ndarray
    expected_return: float
    volatility: float
    sharpe_ratio: float
    method: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# RISK PARITY OPTIMIZER
# =============================================================================

class RiskParityOptimizer:
    """
    Risk Parity (Equal Risk Contribution) Portfolio.

    Each asset contributes equally to portfolio risk.
    """

    def __init__(
        self,
        risk_target: float = None,  # Target volatility (optional)
        max_weight: float = 0.25,
        min_weight: float = 0.01,
    ):
        self.risk_target = risk_target
        self.max_weight = max_weight
        self.min_weight = min_weight

    def optimize(
        self,
        cov_matrix: np.ndarray,
        risk_budget: np.ndarray = None,
    ) -> PortfolioResult:
        """
        Optimize for risk parity.

        Args:
            cov_matrix: Covariance matrix
            risk_budget: Target risk contribution per asset (default: equal)

        Returns:
            PortfolioResult with optimal weights
        """
        n = len(cov_matrix)

        if risk_budget is None:
            risk_budget = np.ones(n) / n  # Equal risk contribution

        # Objective: minimize deviation from target risk contributions
        def objective(w):
            portfolio_vol = np.sqrt(w @ cov_matrix @ w)
            marginal_contrib = cov_matrix @ w / portfolio_vol
            risk_contrib = w * marginal_contrib
            risk_contrib_pct = risk_contrib / portfolio_vol

            # Sum of squared deviations from target
            return np.sum((risk_contrib_pct - risk_budget) ** 2)

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Sum to 1
        ]

        bounds = [(self.min_weight, self.max_weight) for _ in range(n)]

        # Initial guess: inverse volatility
        vols = np.sqrt(np.diag(cov_matrix))
        w0 = (1 / vols) / np.sum(1 / vols)

        result = minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )

        weights = result.x
        vol = np.sqrt(weights @ cov_matrix @ weights)

        # Scale to risk target if specified
        if self.risk_target is not None:
            scale = self.risk_target / vol
            weights = weights * scale
            vol = self.risk_target

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,  # Risk parity doesn't optimize return
            volatility=vol,
            sharpe_ratio=0.0,
            method='risk_parity',
            metadata={
                'risk_budget': risk_budget.tolist(),
                'actual_risk_contrib': self._get_risk_contributions(weights, cov_matrix),
            }
        )

    def _get_risk_contributions(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
    ) -> List[float]:
        """Calculate risk contributions of each asset."""
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        marginal = cov_matrix @ weights / port_vol
        contrib = weights * marginal / port_vol
        return contrib.tolist()


# =============================================================================
# BLACK-LITTERMAN MODEL
# =============================================================================

class BlackLittermanOptimizer:
    """
    Black-Litterman Portfolio Optimization.

    Combines market equilibrium returns with investor views.
    """

    def __init__(
        self,
        risk_aversion: float = 2.5,
        tau: float = 0.05,  # Scaling factor for prior uncertainty
    ):
        self.risk_aversion = risk_aversion
        self.tau = tau

    def optimize(
        self,
        market_weights: np.ndarray,
        cov_matrix: np.ndarray,
        views: np.ndarray = None,  # P matrix (K x N)
        view_returns: np.ndarray = None,  # Q vector (K)
        view_confidence: np.ndarray = None,  # Omega diagonal (K)
    ) -> PortfolioResult:
        """
        Black-Litterman optimization.

        Args:
            market_weights: Market capitalization weights
            cov_matrix: Asset covariance matrix
            views: View picking matrix P (K views x N assets)
            view_returns: Expected returns for each view Q
            view_confidence: Confidence in each view (variance)
        """
        n = len(market_weights)

        # Implied equilibrium returns (reverse optimization)
        pi = self.risk_aversion * cov_matrix @ market_weights

        if views is None or view_returns is None:
            # No views: use equilibrium returns
            expected_returns = pi
        else:
            # Incorporate views
            P = views
            Q = view_returns
            K = len(Q)

            if view_confidence is None:
                # Default: proportional to variance of view portfolios
                view_confidence = np.diag(P @ (self.tau * cov_matrix) @ P.T)

            Omega = np.diag(view_confidence)

            # Black-Litterman formula
            tau_sigma = self.tau * cov_matrix
            M = np.linalg.inv(np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(Omega) @ P)
            expected_returns = M @ (np.linalg.inv(tau_sigma) @ pi + P.T @ np.linalg.inv(Omega) @ Q)

        # Optimize with expected returns
        weights = self._mean_variance_optimize(expected_returns, cov_matrix)

        port_return = weights @ expected_returns
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        sharpe = port_return / port_vol if port_vol > 0 else 0

        return PortfolioResult(
            weights=weights,
            expected_return=port_return,
            volatility=port_vol,
            sharpe_ratio=sharpe,
            method='black_litterman',
            metadata={
                'equilibrium_returns': pi.tolist(),
                'posterior_returns': expected_returns.tolist(),
            }
        )

    def _mean_variance_optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
    ) -> np.ndarray:
        """Simple mean-variance optimization."""
        n = len(expected_returns)

        def objective(w):
            ret = w @ expected_returns
            vol = np.sqrt(w @ cov_matrix @ w)
            return -ret / vol  # Negative Sharpe (minimize)

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0, 0.30) for _ in range(n)]
        w0 = np.ones(n) / n

        result = minimize(objective, w0, method='SLSQP', bounds=bounds, constraints=constraints)
        return result.x


# =============================================================================
# HIERARCHICAL RISK PARITY (HRP)
# =============================================================================

class HierarchicalRiskParity:
    """
    Hierarchical Risk Parity.

    Uses hierarchical clustering to allocate risk.
    More robust than standard mean-variance.
    """

    def __init__(self, linkage_method: str = 'ward'):
        self.linkage_method = linkage_method

    def optimize(
        self,
        cov_matrix: np.ndarray,
        corr_matrix: np.ndarray = None,
    ) -> PortfolioResult:
        """
        HRP optimization.

        Args:
            cov_matrix: Covariance matrix
            corr_matrix: Correlation matrix (computed if None)
        """
        n = len(cov_matrix)

        if corr_matrix is None:
            vols = np.sqrt(np.diag(cov_matrix))
            corr_matrix = cov_matrix / np.outer(vols, vols)

        # Step 1: Tree clustering
        dist_matrix = self._correlation_distance(corr_matrix)
        link = linkage(squareform(dist_matrix), method=self.linkage_method)
        sorted_idx = leaves_list(link)

        # Step 2: Quasi-diagonalization
        sorted_cov = cov_matrix[np.ix_(sorted_idx, sorted_idx)]

        # Step 3: Recursive bisection
        weights = self._recursive_bisection(sorted_cov)

        # Unsort weights to original order
        final_weights = np.zeros(n)
        for i, idx in enumerate(sorted_idx):
            final_weights[idx] = weights[i]

        vol = np.sqrt(final_weights @ cov_matrix @ final_weights)

        return PortfolioResult(
            weights=final_weights,
            expected_return=0.0,
            volatility=vol,
            sharpe_ratio=0.0,
            method='hrp',
            metadata={
                'sorted_order': sorted_idx.tolist(),
            }
        )

    def _correlation_distance(self, corr: np.ndarray) -> np.ndarray:
        """Convert correlation to distance matrix."""
        # Ensure correlation is in valid range
        corr = np.clip(corr, -1, 1)
        # Ensure symmetry
        corr = (corr + corr.T) / 2
        np.fill_diagonal(corr, 1.0)
        return np.sqrt(np.maximum(0, 0.5 * (1 - corr)))

    def _recursive_bisection(self, cov: np.ndarray) -> np.ndarray:
        """Recursive bisection for weight allocation."""
        n = len(cov)
        weights = np.ones(n)

        # List of clusters to process: [(start, end), ...]
        clusters = [(0, n)]

        while clusters:
            start, end = clusters.pop(0)
            if end - start <= 1:
                continue

            # Split in half
            mid = (start + end) // 2

            # Variance of each half
            left_cov = cov[start:mid, start:mid]
            right_cov = cov[mid:end, mid:end]

            left_var = self._get_cluster_variance(left_cov)
            right_var = self._get_cluster_variance(right_cov)

            # Allocate inversely to variance
            total_var = left_var + right_var
            if total_var > 0:
                left_weight = right_var / total_var
                right_weight = left_var / total_var
            else:
                left_weight = right_weight = 0.5

            # Apply weights
            weights[start:mid] *= left_weight
            weights[mid:end] *= right_weight

            # Add sub-clusters
            if mid - start > 1:
                clusters.append((start, mid))
            if end - mid > 1:
                clusters.append((mid, end))

        return weights / weights.sum()

    def _get_cluster_variance(self, cov: np.ndarray) -> float:
        """Get variance of inverse-variance weighted portfolio."""
        ivp_weights = 1 / np.diag(cov)
        ivp_weights = ivp_weights / ivp_weights.sum()
        return ivp_weights @ cov @ ivp_weights


# =============================================================================
# MEAN-CVAR OPTIMIZATION
# =============================================================================

class MeanCVaROptimizer:
    """
    Mean-CVaR (Conditional Value at Risk) Optimization.

    Optimizes for expected return while controlling tail risk.
    """

    def __init__(
        self,
        alpha: float = 0.05,  # CVaR confidence level
        lambda_risk: float = 1.0,  # Risk aversion parameter
    ):
        self.alpha = alpha
        self.lambda_risk = lambda_risk

    def optimize(
        self,
        returns: np.ndarray,  # Historical returns (T x N)
        expected_returns: np.ndarray = None,
    ) -> PortfolioResult:
        """
        Mean-CVaR optimization.

        Args:
            returns: Historical return matrix
            expected_returns: Expected returns (uses historical mean if None)
        """
        T, n = returns.shape

        if expected_returns is None:
            expected_returns = np.mean(returns, axis=0)

        # Number of scenarios in CVaR tail
        k = int(np.ceil(T * self.alpha))

        def objective(w):
            portfolio_returns = returns @ w
            sorted_returns = np.sort(portfolio_returns)
            cvar = -np.mean(sorted_returns[:k])  # Average of worst k returns

            expected_ret = w @ expected_returns

            # Maximize return - lambda * CVaR
            return -(expected_ret - self.lambda_risk * cvar)

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0, 0.30) for _ in range(n)]
        w0 = np.ones(n) / n

        result = minimize(objective, w0, method='SLSQP', bounds=bounds, constraints=constraints)
        weights = result.x

        # Calculate metrics
        port_returns = returns @ weights
        expected_ret = weights @ expected_returns
        vol = np.std(port_returns) * np.sqrt(252)
        cvar = -np.mean(np.sort(port_returns)[:k])

        return PortfolioResult(
            weights=weights,
            expected_return=expected_ret * 252,
            volatility=vol,
            sharpe_ratio=expected_ret * 252 / vol if vol > 0 else 0,
            method='mean_cvar',
            metadata={
                'cvar': cvar * np.sqrt(252),
                'alpha': self.alpha,
            }
        )


# =============================================================================
# KELLY CRITERION OPTIMIZER
# =============================================================================

class KellyCriterionOptimizer:
    """
    Kelly Criterion Portfolio Optimization.

    Maximizes geometric growth rate.
    """

    def __init__(self, fraction: float = 0.5):
        """
        Args:
            fraction: Fraction of Kelly to use (0.5 = half Kelly for safety)
        """
        self.fraction = fraction

    def optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
    ) -> PortfolioResult:
        """
        Kelly criterion optimization.

        Full Kelly: w = Sigma^(-1) * mu
        """
        # Full Kelly weights
        try:
            cov_inv = np.linalg.inv(cov_matrix)
        except np.linalg.LinAlgError:
            # Use pseudo-inverse if singular
            cov_inv = np.linalg.pinv(cov_matrix)

        full_kelly = cov_inv @ expected_returns

        # Apply fraction
        weights = full_kelly * self.fraction

        # Normalize if sum > 1 (leverage constraint)
        if np.sum(np.abs(weights)) > 1:
            weights = weights / np.sum(np.abs(weights))

        # Clip negative weights to 0 (no shorting)
        weights = np.maximum(weights, 0)
        if np.sum(weights) > 0:
            weights = weights / np.sum(weights)
        else:
            weights = np.ones(len(weights)) / len(weights)

        port_return = weights @ expected_returns
        port_vol = np.sqrt(weights @ cov_matrix @ weights)

        return PortfolioResult(
            weights=weights,
            expected_return=port_return * 252,
            volatility=port_vol * np.sqrt(252),
            sharpe_ratio=port_return / port_vol if port_vol > 0 else 0,
            method='kelly',
            metadata={
                'full_kelly_weights': full_kelly.tolist(),
                'fraction': self.fraction,
            }
        )


# =============================================================================
# MAXIMUM DIVERSIFICATION
# =============================================================================

class MaxDiversificationOptimizer:
    """
    Maximum Diversification Portfolio.

    Maximizes the diversification ratio.
    """

    def optimize(
        self,
        cov_matrix: np.ndarray,
    ) -> PortfolioResult:
        """
        Optimize for maximum diversification.

        Diversification Ratio = weighted avg vol / portfolio vol
        """
        n = len(cov_matrix)
        vols = np.sqrt(np.diag(cov_matrix))

        def neg_diversification_ratio(w):
            weighted_vol = w @ vols
            port_vol = np.sqrt(w @ cov_matrix @ w)
            return -weighted_vol / port_vol if port_vol > 0 else 0

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0, 0.30) for _ in range(n)]
        w0 = np.ones(n) / n

        result = minimize(
            neg_diversification_ratio,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        weights = result.x

        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        div_ratio = (weights @ vols) / port_vol

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            volatility=port_vol * np.sqrt(252),
            sharpe_ratio=0.0,
            method='max_diversification',
            metadata={
                'diversification_ratio': div_ratio,
            }
        )


# =============================================================================
# UNIFIED PORTFOLIO OPTIMIZER
# =============================================================================

class PortfolioOptimizer:
    """
    Unified portfolio optimization interface.

    Provides access to all optimization methods.
    """

    def __init__(self):
        self.risk_parity = RiskParityOptimizer()
        self.black_litterman = BlackLittermanOptimizer()
        self.hrp = HierarchicalRiskParity()
        self.mean_cvar = MeanCVaROptimizer()
        self.kelly = KellyCriterionOptimizer()
        self.max_div = MaxDiversificationOptimizer()

    def optimize(
        self,
        method: str,
        returns: np.ndarray = None,
        cov_matrix: np.ndarray = None,
        expected_returns: np.ndarray = None,
        **kwargs,
    ) -> PortfolioResult:
        """
        Optimize portfolio using specified method.

        Methods: 'risk_parity', 'black_litterman', 'hrp', 'mean_cvar', 'kelly', 'max_diversification'
        """
        if cov_matrix is None and returns is not None:
            cov_matrix = np.cov(returns.T)

        if method == 'risk_parity':
            return self.risk_parity.optimize(cov_matrix, **kwargs)
        elif method == 'black_litterman':
            market_weights = kwargs.get('market_weights', np.ones(len(cov_matrix)) / len(cov_matrix))
            return self.black_litterman.optimize(market_weights, cov_matrix, **kwargs)
        elif method == 'hrp':
            return self.hrp.optimize(cov_matrix, **kwargs)
        elif method == 'mean_cvar':
            return self.mean_cvar.optimize(returns, expected_returns)
        elif method == 'kelly':
            if expected_returns is None:
                expected_returns = np.mean(returns, axis=0) if returns is not None else np.zeros(len(cov_matrix))
            return self.kelly.optimize(expected_returns, cov_matrix)
        elif method == 'max_diversification':
            return self.max_div.optimize(cov_matrix)
        else:
            raise ValueError(f"Unknown optimization method: {method}")

    def compare_methods(
        self,
        returns: np.ndarray,
        cov_matrix: np.ndarray = None,
        expected_returns: np.ndarray = None,
    ) -> Dict[str, PortfolioResult]:
        """Compare all optimization methods."""
        if cov_matrix is None:
            cov_matrix = np.cov(returns.T)

        if expected_returns is None:
            expected_returns = np.mean(returns, axis=0)

        results = {}

        methods = ['risk_parity', 'hrp', 'mean_cvar', 'kelly', 'max_diversification']

        for method in methods:
            try:
                result = self.optimize(
                    method=method,
                    returns=returns,
                    cov_matrix=cov_matrix,
                    expected_returns=expected_returns,
                )
                results[method] = result
            except Exception as e:
                logger.warning(f"Failed to optimize with {method}: {e}")

        return results


# =============================================================================
# DYNAMIC PORTFOLIO REBALANCING - P2 Task 18
# =============================================================================

class RebalanceTrigger(Enum):
    """Types of rebalancing triggers."""
    PERIODIC = "periodic"  # Time-based
    THRESHOLD = "threshold"  # Drift-based
    VOLATILITY = "volatility"  # Volatility-triggered
    SIGNAL = "signal"  # Signal-triggered
    HYBRID = "hybrid"  # Combination


@dataclass
class RebalanceSignal:
    """Signal indicating rebalance is needed."""
    trigger_type: RebalanceTrigger
    urgency: float  # 0-1, how urgent is rebalance
    drift_magnitude: float  # Total portfolio drift
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RebalanceOrder:
    """Order generated for rebalancing."""
    symbol: str
    current_weight: float
    target_weight: float
    trade_weight: float  # Amount to trade (positive=buy, negative=sell)
    trade_value: float
    priority: int = 0  # Higher = execute first


class DynamicRebalancer:
    """
    Dynamic Portfolio Rebalancing System.
    
    Features:
    - Multiple trigger mechanisms (time, drift, volatility)
    - Intelligent trade scheduling
    - Transaction cost optimization
    - Tax-aware rebalancing
    - Gradual rebalancing for large positions
    
    P2 Task 18: Real-time portfolio rebalancing with predictive analytics.
    """

    def __init__(
        self,
        optimizer: PortfolioOptimizer = None,
        rebalance_threshold: float = 0.05,  # 5% drift threshold
        min_trade_size: float = 0.01,  # Minimum trade as % of portfolio
        max_turnover: float = 0.25,  # Maximum daily turnover
        tax_rate: float = 0.0,  # Short-term capital gains rate
        transaction_cost_bps: float = 10,  # Transaction cost in bps
    ):
        self.optimizer = optimizer or PortfolioOptimizer()
        self.rebalance_threshold = rebalance_threshold
        self.min_trade_size = min_trade_size
        self.max_turnover = max_turnover
        self.tax_rate = tax_rate
        self.transaction_cost_bps = transaction_cost_bps
        
        # State tracking
        self._last_rebalance: Optional[datetime] = None
        self._target_weights: Optional[np.ndarray] = None
        self._rebalance_history: List[Dict[str, Any]] = []
        
    def check_rebalance_needed(
        self,
        current_weights: np.ndarray,
        target_weights: np.ndarray,
        volatilities: np.ndarray = None,
        market_conditions: Dict[str, Any] = None,
    ) -> Optional[RebalanceSignal]:
        """
        Check if rebalancing is needed based on multiple criteria.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            volatilities: Asset volatilities (optional)
            market_conditions: Market regime info (optional)
            
        Returns:
            RebalanceSignal if rebalance needed, None otherwise
        """
        market_conditions = market_conditions or {}
        
        # Calculate drift
        drift = current_weights - target_weights
        drift_magnitude = np.sum(np.abs(drift))
        max_drift = np.max(np.abs(drift))
        
        signals = []
        
        # 1. Threshold-based trigger
        if max_drift > self.rebalance_threshold:
            signals.append({
                'trigger': RebalanceTrigger.THRESHOLD,
                'urgency': min(1.0, max_drift / (self.rebalance_threshold * 2)),
                'detail': f'Max drift {max_drift:.2%} exceeds threshold {self.rebalance_threshold:.2%}'
            })
        
        # 2. Volatility-based trigger (rebalance more frequently in high vol)
        if volatilities is not None:
            vol_adjusted_threshold = self.rebalance_threshold / (1 + np.mean(volatilities) * 10)
            if max_drift > vol_adjusted_threshold:
                signals.append({
                    'trigger': RebalanceTrigger.VOLATILITY,
                    'urgency': 0.7,
                    'detail': f'Vol-adjusted threshold triggered (threshold: {vol_adjusted_threshold:.2%})'
                })
        
        # 3. Time-based trigger (periodic rebalancing)
        if self._last_rebalance:
            days_since = (datetime.now() - self._last_rebalance).days
            periodic_interval = market_conditions.get('rebalance_interval_days', 30)
            if days_since >= periodic_interval:
                signals.append({
                    'trigger': RebalanceTrigger.PERIODIC,
                    'urgency': min(1.0, days_since / (periodic_interval * 2)),
                    'detail': f'{days_since} days since last rebalance'
                })
        
        # 4. Signal-based trigger (regime change, etc.)
        regime_change = market_conditions.get('regime_change', False)
        if regime_change:
            signals.append({
                'trigger': RebalanceTrigger.SIGNAL,
                'urgency': 0.9,
                'detail': 'Market regime change detected'
            })
        
        if not signals:
            return None
        
        # Combine signals
        max_urgency = max(s['urgency'] for s in signals)
        trigger_type = (
            RebalanceTrigger.HYBRID if len(signals) > 1 
            else signals[0]['trigger']
        )
        
        return RebalanceSignal(
            trigger_type=trigger_type,
            urgency=max_urgency,
            drift_magnitude=drift_magnitude,
            details={
                'signals': [s['detail'] for s in signals],
                'max_drift': max_drift,
                'drifts_by_asset': drift.tolist(),
            }
        )
    
    def generate_rebalance_orders(
        self,
        current_weights: np.ndarray,
        target_weights: np.ndarray,
        portfolio_value: float,
        asset_names: List[str],
        prices: np.ndarray = None,
        tax_lots: Dict[str, List[Dict]] = None,
    ) -> List[RebalanceOrder]:
        """
        Generate optimized rebalance orders.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            portfolio_value: Total portfolio value
            asset_names: List of asset names/symbols
            prices: Current asset prices (optional)
            tax_lots: Tax lot information for tax-aware rebalancing
            
        Returns:
            List of RebalanceOrder objects, sorted by execution priority
        """
        n = len(current_weights)
        drift = target_weights - current_weights
        
        orders = []
        
        for i in range(n):
            trade_weight = drift[i]
            
            # Skip small trades
            if abs(trade_weight) < self.min_trade_size:
                continue
            
            trade_value = trade_weight * portfolio_value
            
            # Tax-aware adjustment for sells
            tax_adjustment = 0.0
            if trade_weight < 0 and tax_lots and asset_names[i] in tax_lots:
                tax_adjustment = self._estimate_tax_impact(
                    tax_lots[asset_names[i]], 
                    -trade_value,
                    prices[i] if prices is not None else 1.0
                )
            
            # Transaction cost
            transaction_cost = abs(trade_value) * (self.transaction_cost_bps / 10000)
            
            # Calculate priority (sells first to raise cash, then buys)
            # Also prioritize larger trades and tax-efficient trades
            priority = 0
            if trade_weight < 0:  # Sells
                priority += 100  # Sells get higher priority
            priority += int(abs(trade_weight) * 100)  # Larger trades higher priority
            priority -= int(tax_adjustment * 10)  # Tax-heavy trades lower priority
            
            orders.append(RebalanceOrder(
                symbol=asset_names[i],
                current_weight=current_weights[i],
                target_weight=target_weights[i],
                trade_weight=trade_weight,
                trade_value=trade_value,
                priority=priority,
            ))
        
        # Sort by priority (descending)
        orders.sort(key=lambda x: x.priority, reverse=True)
        
        # Apply turnover constraint
        orders = self._apply_turnover_constraint(orders, portfolio_value)
        
        return orders
    
    def _estimate_tax_impact(
        self,
        tax_lots: List[Dict],
        sell_value: float,
        current_price: float
    ) -> float:
        """Estimate tax impact of selling from tax lots."""
        total_tax = 0.0
        remaining_to_sell = sell_value
        
        # Sort lots by tax efficiency (LIFO for highest basis first)
        sorted_lots = sorted(
            tax_lots, 
            key=lambda x: x.get('cost_basis', 0), 
            reverse=True
        )
        
        for lot in sorted_lots:
            if remaining_to_sell <= 0:
                break
                
            lot_value = lot.get('shares', 0) * current_price
            sell_from_lot = min(remaining_to_sell, lot_value)
            
            cost_basis = lot.get('cost_basis', current_price) * (sell_from_lot / lot_value) * lot.get('shares', 0)
            gain = sell_from_lot - cost_basis
            
            if gain > 0:
                # Determine if short-term or long-term
                purchase_date = datetime.fromisoformat(lot.get('purchase_date', '2020-01-01'))
                holding_days = (datetime.now() - purchase_date).days
                rate = self.tax_rate if holding_days < 365 else self.tax_rate * 0.5
                total_tax += gain * rate
                
            remaining_to_sell -= sell_from_lot
        
        return total_tax
    
    def _apply_turnover_constraint(
        self,
        orders: List[RebalanceOrder],
        portfolio_value: float
    ) -> List[RebalanceOrder]:
        """Apply maximum turnover constraint to orders."""
        max_trade_value = portfolio_value * self.max_turnover
        cumulative_turnover = 0.0
        constrained_orders = []
        
        for order in orders:
            trade_value = abs(order.trade_value)
            
            if cumulative_turnover + trade_value <= max_trade_value:
                constrained_orders.append(order)
                cumulative_turnover += trade_value
            else:
                # Partially execute order
                remaining_capacity = max_trade_value - cumulative_turnover
                if remaining_capacity > 0:
                    scale = remaining_capacity / trade_value
                    partial_order = RebalanceOrder(
                        symbol=order.symbol,
                        current_weight=order.current_weight,
                        target_weight=order.current_weight + order.trade_weight * scale,
                        trade_weight=order.trade_weight * scale,
                        trade_value=order.trade_value * scale,
                        priority=order.priority,
                    )
                    constrained_orders.append(partial_order)
                break
        
        return constrained_orders
    
    def execute_gradual_rebalance(
        self,
        current_weights: np.ndarray,
        target_weights: np.ndarray,
        num_days: int = 5,
        urgency: float = 0.5,
    ) -> List[np.ndarray]:
        """
        Generate gradual rebalancing schedule.
        
        For large position changes, spread trades over multiple days
        to minimize market impact.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            num_days: Number of days to spread trades
            urgency: How urgent is the rebalance (0-1)
            
        Returns:
            List of intermediate target weights for each day
        """
        # Adjust num_days based on urgency
        effective_days = max(1, int(num_days * (1 - urgency * 0.5)))
        
        drift = target_weights - current_weights
        daily_change = drift / effective_days
        
        schedule = []
        for day in range(1, effective_days + 1):
            intermediate_weights = current_weights + daily_change * day
            schedule.append(intermediate_weights)
        
        return schedule
    
    def optimize_and_rebalance(
        self,
        returns: np.ndarray,
        current_weights: np.ndarray,
        method: str = 'hrp',
        portfolio_value: float = 1000000,
        asset_names: List[str] = None,
        **kwargs
    ) -> Tuple[PortfolioResult, List[RebalanceOrder], Optional[RebalanceSignal]]:
        """
        Full rebalancing pipeline: optimize and generate orders.
        
        Args:
            returns: Historical returns matrix
            current_weights: Current portfolio weights
            method: Optimization method
            portfolio_value: Portfolio value
            asset_names: Asset names
            **kwargs: Additional arguments for optimizer
            
        Returns:
            Tuple of (optimization_result, orders, rebalance_signal)
        """
        # Optimize
        cov_matrix = np.cov(returns.T)
        expected_returns = np.mean(returns, axis=0)
        
        result = self.optimizer.optimize(
            method=method,
            returns=returns,
            cov_matrix=cov_matrix,
            expected_returns=expected_returns,
            **kwargs
        )
        
        target_weights = result.weights
        
        # Check if rebalance needed
        volatilities = np.sqrt(np.diag(cov_matrix)) * np.sqrt(252)
        signal = self.check_rebalance_needed(
            current_weights, 
            target_weights, 
            volatilities
        )
        
        # Generate orders if needed
        orders = []
        if signal:
            if asset_names is None:
                asset_names = [f'Asset_{i}' for i in range(len(current_weights))]
            
            orders = self.generate_rebalance_orders(
                current_weights=current_weights,
                target_weights=target_weights,
                portfolio_value=portfolio_value,
                asset_names=asset_names,
            )
            
            # Update state
            self._last_rebalance = datetime.now()
            self._target_weights = target_weights.copy()
            self._rebalance_history.append({
                'timestamp': datetime.now().isoformat(),
                'signal': signal.details,
                'orders': [
                    {
                        'symbol': o.symbol,
                        'trade_weight': o.trade_weight,
                        'trade_value': o.trade_value,
                    }
                    for o in orders
                ],
            })
        
        return result, orders, signal
    
    def get_rebalance_history(self) -> List[Dict[str, Any]]:
        """Get rebalancing history."""
        return self._rebalance_history.copy()
    
    def estimate_rebalance_costs(
        self,
        orders: List[RebalanceOrder],
        spread_bps: float = 5.0,
    ) -> Dict[str, float]:
        """
        Estimate total costs of rebalancing.
        
        Args:
            orders: List of rebalance orders
            spread_bps: Estimated bid-ask spread in bps
            
        Returns:
            Cost breakdown dictionary
        """
        total_turnover = sum(abs(o.trade_value) for o in orders)
        
        # Commission/transaction costs
        commission = total_turnover * (self.transaction_cost_bps / 10000)
        
        # Spread cost (half-spread for market orders)
        spread_cost = total_turnover * (spread_bps / 10000 / 2)
        
        # Market impact estimate (simplified)
        impact_cost = total_turnover * 0.0005 * np.sqrt(total_turnover / 1000000)
        
        total_cost = commission + spread_cost + impact_cost
        
        return {
            'total_turnover': total_turnover,
            'commission': commission,
            'spread_cost': spread_cost,
            'market_impact': impact_cost,
            'total_cost': total_cost,
            'cost_bps': (total_cost / total_turnover * 10000) if total_turnover > 0 else 0,
        }


# Import datetime and Enum for rebalancer
from datetime import datetime
from enum import Enum


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioResult',
    'RiskParityOptimizer',
    'BlackLittermanOptimizer',
    'HierarchicalRiskParity',
    'MeanCVaROptimizer',
    'KellyCriterionOptimizer',
    'MaxDiversificationOptimizer',
    'PortfolioOptimizer',
    'RebalanceTrigger',
    'RebalanceSignal',
    'RebalanceOrder',
    'DynamicRebalancer',
]
