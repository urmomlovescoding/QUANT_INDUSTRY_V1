"""
QUANT_INDUSTRY_V1 Performance Attribution

Detailed return attribution and performance decomposition.

Features:
- Brinson Attribution (allocation, selection, interaction)
- Factor Attribution (Fama-French, Carhart, custom factors)
- Risk Attribution
- Return Decomposition
- Strategy Attribution
- Time-based Attribution
- Transaction Cost Analysis
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class AttributionMethod(Enum):
    """Attribution methods."""
    BRINSON = "brinson"
    FACTOR = "factor"
    RISK = "risk"
    TIME = "time"
    STRATEGY = "strategy"


@dataclass
class AttributionResult:
    """Attribution analysis result."""
    total_return: float
    benchmark_return: float
    active_return: float
    components: Dict[str, float]
    timestamp: datetime
    method: AttributionMethod
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrinsonAttribution:
    """Brinson attribution components."""
    allocation_effect: float  # Sector allocation
    selection_effect: float   # Security selection
    interaction_effect: float # Allocation-selection interaction
    total_active_return: float


@dataclass
class FactorExposure:
    """Factor exposure and attribution."""
    factor_name: str
    exposure: float  # Beta to factor
    factor_return: float
    contribution: float  # exposure * factor_return
    t_stat: float = 0.0


@dataclass
class RiskAttribution:
    """Risk attribution breakdown."""
    total_variance: float
    systematic_variance: float
    idiosyncratic_variance: float
    factor_contributions: Dict[str, float]
    marginal_contributions: Dict[str, float]


# =============================================================================
# BRINSON ATTRIBUTION
# =============================================================================

class BrinsonAttributor:
    """
    Brinson-Fachler attribution model.

    Decomposes active return into:
    - Allocation: over/underweighting sectors
    - Selection: stock picking within sectors
    - Interaction: combination effect
    """

    def __init__(self):
        self.history: List[BrinsonAttribution] = []

    def attribute(
        self,
        portfolio_weights: Dict[str, float],  # sector -> weight
        portfolio_returns: Dict[str, float],  # sector -> return
        benchmark_weights: Dict[str, float],  # sector -> weight
        benchmark_returns: Dict[str, float],  # sector -> return
    ) -> BrinsonAttribution:
        """
        Compute Brinson attribution.

        Allocation Effect = Sum((Wp - Wb) * Rb)
        Selection Effect = Sum(Wb * (Rp - Rb))
        Interaction Effect = Sum((Wp - Wb) * (Rp - Rb))
        """
        sectors = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        allocation = 0.0
        selection = 0.0
        interaction = 0.0

        for sector in sectors:
            wp = portfolio_weights.get(sector, 0.0)
            wb = benchmark_weights.get(sector, 0.0)
            rp = portfolio_returns.get(sector, 0.0)
            rb = benchmark_returns.get(sector, 0.0)

            allocation += (wp - wb) * rb
            selection += wb * (rp - rb)
            interaction += (wp - wb) * (rp - rb)

        result = BrinsonAttribution(
            allocation_effect=allocation,
            selection_effect=selection,
            interaction_effect=interaction,
            total_active_return=allocation + selection + interaction,
        )

        self.history.append(result)
        return result

    def attribute_time_series(
        self,
        portfolio_weights_ts: List[Dict[str, float]],
        portfolio_returns_ts: List[Dict[str, float]],
        benchmark_weights_ts: List[Dict[str, float]],
        benchmark_returns_ts: List[Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Compute cumulative Brinson attribution over time.
        """
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        n = min(
            len(portfolio_weights_ts),
            len(portfolio_returns_ts),
            len(benchmark_weights_ts),
            len(benchmark_returns_ts),
        )

        for i in range(n):
            result = self.attribute(
                portfolio_weights_ts[i],
                portfolio_returns_ts[i],
                benchmark_weights_ts[i],
                benchmark_returns_ts[i],
            )

            total_allocation += result.allocation_effect
            total_selection += result.selection_effect
            total_interaction += result.interaction_effect

        return {
            'allocation_effect': total_allocation,
            'selection_effect': total_selection,
            'interaction_effect': total_interaction,
            'total_active_return': total_allocation + total_selection + total_interaction,
        }


# =============================================================================
# FACTOR ATTRIBUTION
# =============================================================================

class FactorAttributor:
    """
    Factor-based attribution model.

    Supports:
    - Fama-French 3-factor
    - Carhart 4-factor
    - Custom factor models
    """

    def __init__(
        self,
        factor_names: List[str] = None,
        risk_free_rate: float = 0.0,
    ):
        self.factor_names = factor_names or ['market', 'size', 'value', 'momentum']
        self.risk_free_rate = risk_free_rate

        # Factor model parameters
        self.factor_loadings: Dict[str, float] = {}
        self.alpha: float = 0.0
        self.r_squared: float = 0.0
        self._fitted = False

    def fit(
        self,
        returns: np.ndarray,
        factor_returns: Dict[str, np.ndarray],
    ) -> 'FactorAttributor':
        """
        Fit factor model using OLS regression.

        R - Rf = alpha + sum(beta_i * F_i) + epsilon
        """
        n = len(returns)
        n_factors = len(self.factor_names)

        # Build factor matrix
        X = np.column_stack([
            factor_returns.get(f, np.zeros(n))
            for f in self.factor_names
        ])

        # Add constant for alpha
        X = np.column_stack([np.ones(n), X])

        # Excess returns
        y = returns - self.risk_free_rate

        # OLS: (X'X)^-1 X'y
        XtX = X.T @ X + 1e-6 * np.eye(X.shape[1])
        Xty = X.T @ y
        coeffs = np.linalg.solve(XtX, Xty)

        self.alpha = coeffs[0]
        self.factor_loadings = {
            f: coeffs[i + 1]
            for i, f in enumerate(self.factor_names)
        }

        # R-squared
        y_pred = X @ coeffs
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self.r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        self._fitted = True
        return self

    def attribute(
        self,
        returns: np.ndarray,
        factor_returns: Dict[str, np.ndarray],
    ) -> List[FactorExposure]:
        """
        Attribute returns to factors.
        """
        if not self._fitted:
            self.fit(returns, factor_returns)

        n = len(returns)
        exposures = []

        for factor in self.factor_names:
            beta = self.factor_loadings.get(factor, 0.0)
            f_returns = factor_returns.get(factor, np.zeros(n))
            avg_factor_return = np.mean(f_returns)
            contribution = beta * avg_factor_return

            # T-statistic (simplified)
            if np.std(f_returns) > 0:
                t_stat = beta / (np.std(f_returns) / np.sqrt(n))
            else:
                t_stat = 0.0

            exposures.append(FactorExposure(
                factor_name=factor,
                exposure=beta,
                factor_return=avg_factor_return,
                contribution=contribution,
                t_stat=t_stat,
            ))

        return exposures

    def get_attribution_summary(
        self,
        returns: np.ndarray,
        factor_returns: Dict[str, np.ndarray],
    ) -> Dict[str, float]:
        """Get summary of factor attribution."""
        exposures = self.attribute(returns, factor_returns)

        total_return = np.mean(returns)
        factor_contribution = sum(e.contribution for e in exposures)
        residual = total_return - factor_contribution - self.alpha

        return {
            'total_return': total_return,
            'alpha': self.alpha,
            'factor_contribution': factor_contribution,
            'residual': residual,
            'r_squared': self.r_squared,
            **{e.factor_name + '_contrib': e.contribution for e in exposures},
        }


# =============================================================================
# RISK ATTRIBUTION
# =============================================================================

class RiskAttributor:
    """
    Risk contribution and attribution analysis.
    """

    def __init__(self):
        pass

    def attribute_variance(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        factor_loadings: np.ndarray = None,  # N x K factor loadings
        factor_cov: np.ndarray = None,  # K x K factor covariance
    ) -> RiskAttribution:
        """
        Decompose portfolio variance into components.
        """
        n = len(weights)
        total_variance = weights @ cov_matrix @ weights

        # Marginal contributions
        marginal_var = cov_matrix @ weights
        component_var = weights * marginal_var
        marginal_contributions = {
            f'asset_{i}': float(component_var[i])
            for i in range(n)
        }

        # Factor decomposition (if provided)
        if factor_loadings is not None and factor_cov is not None:
            # Portfolio factor exposures
            port_loadings = weights @ factor_loadings  # 1 x K

            # Systematic variance
            systematic_variance = port_loadings @ factor_cov @ port_loadings.T
            idiosyncratic_variance = total_variance - systematic_variance

            # Factor contributions
            k = factor_loadings.shape[1]
            factor_contributions = {}
            for i in range(k):
                # Single factor contribution
                contrib = port_loadings[i] ** 2 * factor_cov[i, i]
                factor_contributions[f'factor_{i}'] = float(contrib)

            # Add cross-factor contributions
            for i in range(k):
                for j in range(i + 1, k):
                    cross = 2 * port_loadings[i] * port_loadings[j] * factor_cov[i, j]
                    factor_contributions[f'cross_{i}_{j}'] = float(cross)

        else:
            systematic_variance = total_variance
            idiosyncratic_variance = 0.0
            factor_contributions = {}

        return RiskAttribution(
            total_variance=float(total_variance),
            systematic_variance=float(systematic_variance),
            idiosyncratic_variance=float(idiosyncratic_variance),
            factor_contributions=factor_contributions,
            marginal_contributions=marginal_contributions,
        )

    def calculate_risk_contribution(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
    ) -> Dict[str, float]:
        """
        Calculate percentage risk contribution of each asset.
        """
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        marginal_risk = cov_matrix @ weights / portfolio_vol
        risk_contribution = weights * marginal_risk

        # Percentage contribution
        pct_contribution = risk_contribution / portfolio_vol

        return {
            f'asset_{i}': {
                'weight': float(weights[i]),
                'marginal_risk': float(marginal_risk[i]),
                'risk_contribution': float(risk_contribution[i]),
                'pct_contribution': float(pct_contribution[i]),
            }
            for i in range(len(weights))
        }


# =============================================================================
# TRANSACTION COST ANALYSIS
# =============================================================================

class TransactionCostAnalyzer:
    """
    Analyze transaction costs and execution quality.
    """

    def __init__(self):
        self.trade_history: List[Dict[str, Any]] = []

    def add_trade(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        quantity: float,
        execution_price: float,
        benchmark_price: float,  # VWAP, arrival price, etc.
        commission: float = 0.0,
        timestamp: datetime = None,
    ) -> None:
        """Record a trade for analysis."""
        self.trade_history.append({
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'execution_price': execution_price,
            'benchmark_price': benchmark_price,
            'commission': commission,
            'timestamp': timestamp or datetime.now(timezone.utc),
        })

    def calculate_slippage(
        self,
        execution_price: float,
        benchmark_price: float,
        side: str,
    ) -> float:
        """Calculate slippage in basis points."""
        if side == 'buy':
            slippage = (execution_price - benchmark_price) / benchmark_price
        else:
            slippage = (benchmark_price - execution_price) / benchmark_price

        return slippage * 10000  # Convert to bps

    def analyze_trades(
        self,
        trades: List[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """
        Analyze trading costs.
        """
        trades = trades or self.trade_history

        if not trades:
            return {}

        total_notional = 0.0
        total_commission = 0.0
        total_slippage_bps = 0.0
        positive_slippage = 0
        negative_slippage = 0

        for trade in trades:
            notional = trade['quantity'] * trade['execution_price']
            total_notional += notional
            total_commission += trade.get('commission', 0)

            slippage = self.calculate_slippage(
                trade['execution_price'],
                trade['benchmark_price'],
                trade['side'],
            )
            total_slippage_bps += slippage * notional

            if slippage > 0:
                positive_slippage += 1
            else:
                negative_slippage += 1

        avg_slippage = total_slippage_bps / total_notional if total_notional > 0 else 0

        return {
            'total_trades': len(trades),
            'total_notional': total_notional,
            'total_commission': total_commission,
            'commission_bps': total_commission / total_notional * 10000 if total_notional > 0 else 0,
            'avg_slippage_bps': avg_slippage,
            'positive_slippage_trades': positive_slippage,
            'negative_slippage_trades': negative_slippage,
            'total_cost_bps': (total_commission / total_notional * 10000 + avg_slippage) if total_notional > 0 else 0,
        }

    def implementation_shortfall(
        self,
        decision_price: float,
        arrival_price: float,
        execution_price: float,
        quantity: float,
        side: str,
    ) -> Dict[str, float]:
        """
        Calculate implementation shortfall breakdown.

        Components:
        - Delay cost: (arrival - decision)
        - Market impact: (execution - arrival)
        - Total: (execution - decision)
        """
        if side == 'buy':
            delay_cost = (arrival_price - decision_price) / decision_price
            market_impact = (execution_price - arrival_price) / decision_price
            total_shortfall = (execution_price - decision_price) / decision_price
        else:
            delay_cost = (decision_price - arrival_price) / decision_price
            market_impact = (arrival_price - execution_price) / decision_price
            total_shortfall = (decision_price - execution_price) / decision_price

        return {
            'delay_cost_bps': delay_cost * 10000,
            'market_impact_bps': market_impact * 10000,
            'total_shortfall_bps': total_shortfall * 10000,
            'notional_cost': total_shortfall * quantity * decision_price,
        }


# =============================================================================
# STRATEGY ATTRIBUTION
# =============================================================================

class StrategyAttributor:
    """
    Attribute performance to individual strategies in a multi-strategy system.
    """

    def __init__(self):
        self.strategy_returns: Dict[str, List[float]] = defaultdict(list)
        self.strategy_allocations: Dict[str, List[float]] = defaultdict(list)

    def record_returns(
        self,
        strategy_returns: Dict[str, float],
        strategy_allocations: Dict[str, float] = None,
    ) -> None:
        """Record strategy returns for a period."""
        for strat, ret in strategy_returns.items():
            self.strategy_returns[strat].append(ret)

        if strategy_allocations:
            for strat, alloc in strategy_allocations.items():
                self.strategy_allocations[strat].append(alloc)

    def calculate_contributions(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate each strategy's contribution to portfolio return.
        """
        contributions = {}

        for strat in self.strategy_returns.keys():
            returns = np.array(self.strategy_returns[strat])
            allocations = np.array(self.strategy_allocations.get(strat, [1.0 / len(self.strategy_returns)] * len(returns)))

            # Contribution = allocation * return
            weighted_returns = allocations * returns

            contributions[strat] = {
                'avg_return': float(np.mean(returns)),
                'avg_allocation': float(np.mean(allocations)),
                'total_contribution': float(np.sum(weighted_returns)),
                'avg_contribution': float(np.mean(weighted_returns)),
                'volatility': float(np.std(returns) * np.sqrt(252)),
                'sharpe': float(np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0,
                'hit_rate': float(np.mean(returns > 0)),
            }

        return contributions

    def calculate_correlation_matrix(self) -> np.ndarray:
        """
        Calculate correlation matrix between strategies.
        """
        strategies = list(self.strategy_returns.keys())
        n = len(strategies)

        # Align lengths
        min_len = min(len(self.strategy_returns[s]) for s in strategies)
        returns_matrix = np.column_stack([
            np.array(self.strategy_returns[s][-min_len:])
            for s in strategies
        ])

        return np.corrcoef(returns_matrix.T)


# =============================================================================
# UNIFIED PERFORMANCE ANALYZER
# =============================================================================

class PerformanceAnalyzer:
    """
    Comprehensive performance analysis and attribution.
    """

    def __init__(self):
        self.brinson = BrinsonAttributor()
        self.factor = FactorAttributor()
        self.risk = RiskAttributor()
        self.tca = TransactionCostAnalyzer()
        self.strategy = StrategyAttributor()

    def analyze(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray = None,
        weights: np.ndarray = None,
        cov_matrix: np.ndarray = None,
        factor_returns: Dict[str, np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive performance analysis.
        """
        analysis = {}

        # Basic metrics
        total_return = float(np.prod(1 + returns) - 1)
        annualized_return = float((1 + total_return) ** (252 / len(returns)) - 1) if len(returns) > 0 else 0
        volatility = float(np.std(returns) * np.sqrt(252))
        sharpe = annualized_return / volatility if volatility > 0 else 0

        analysis['basic'] = {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': float(self._max_drawdown(returns)),
            'calmar_ratio': annualized_return / abs(self._max_drawdown(returns)) if self._max_drawdown(returns) != 0 else 0,
        }

        # Benchmark comparison
        if benchmark_returns is not None:
            bench_return = float(np.prod(1 + benchmark_returns) - 1)
            active_return = total_return - bench_return
            tracking_error = float(np.std(returns - benchmark_returns) * np.sqrt(252))
            information_ratio = active_return / tracking_error if tracking_error > 0 else 0

            # Beta and alpha
            if len(returns) > 1:
                cov = np.cov(returns, benchmark_returns)
                beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0
                alpha = annualized_return - beta * float((1 + bench_return) ** (252 / len(returns)) - 1)
            else:
                beta = 0
                alpha = 0

            analysis['benchmark'] = {
                'benchmark_return': bench_return,
                'active_return': active_return,
                'tracking_error': tracking_error,
                'information_ratio': information_ratio,
                'beta': float(beta),
                'alpha': float(alpha),
            }

        # Factor attribution
        if factor_returns is not None:
            self.factor.fit(returns, factor_returns)
            analysis['factor'] = self.factor.get_attribution_summary(returns, factor_returns)

        # Risk attribution
        if weights is not None and cov_matrix is not None:
            risk_attr = self.risk.attribute_variance(weights, cov_matrix)
            analysis['risk'] = {
                'total_variance': risk_attr.total_variance,
                'systematic_variance': risk_attr.systematic_variance,
                'idiosyncratic_variance': risk_attr.idiosyncratic_variance,
                'factor_contributions': risk_attr.factor_contributions,
            }

        return analysis

    def _max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        return float(np.min(drawdowns))


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AttributionMethod',
    'AttributionResult',
    'BrinsonAttribution',
    'FactorExposure',
    'RiskAttribution',
    'BrinsonAttributor',
    'FactorAttributor',
    'RiskAttributor',
    'TransactionCostAnalyzer',
    'StrategyAttributor',
    'PerformanceAnalyzer',
]
