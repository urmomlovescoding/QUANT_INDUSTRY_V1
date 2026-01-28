"""
Multi-Strategy Orchestrator
QUANT_INDUSTRY_V1

Industry Problem: Running multiple strategies is chaotic.
No good way to allocate capital across strategies dynamically.
Strategies compete for capital instead of working together.

Our Solution:
- Intelligent capital allocation based on regime
- Strategy correlation-aware diversification
- Automatic rebalancing based on performance
- Risk budget allocation
- Drawdown-triggered deleveraging
- Strategy lifecycle management (scale up winners, cut losers)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
from collections import defaultdict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AllocationMethod(Enum):
    """Capital allocation methods."""
    EQUAL = "equal"                      # Equal weight
    RISK_PARITY = "risk_parity"          # Equal risk contribution
    KELLY = "kelly"                      # Kelly criterion
    MEAN_VARIANCE = "mean_variance"      # Markowitz
    REGIME_ADAPTIVE = "regime_adaptive"  # Adjust based on market regime
    PERFORMANCE_WEIGHTED = "performance_weighted"  # Weight by recent performance


class StrategyStatus(Enum):
    """Strategy lifecycle status."""
    INCUBATION = "incubation"    # Testing with small capital
    ACTIVE = "active"            # Fully deployed
    WATCH = "watch"              # Underperforming, reduced capital
    SUSPENDED = "suspended"      # Temporarily halted
    RETIRED = "retired"          # Permanently stopped


@dataclass
class StrategyConfig:
    """Configuration for a managed strategy."""
    strategy_id: str
    name: str
    
    # Allocation constraints
    min_allocation: float = 0.0       # Minimum capital %
    max_allocation: float = 1.0       # Maximum capital %
    target_allocation: float = 0.2    # Target capital %
    
    # Risk constraints
    max_drawdown: float = 0.15        # Max allowed drawdown
    max_volatility: float = 0.25      # Max annualized vol
    var_limit: float = 0.05           # 95% VaR limit
    
    # Performance thresholds
    min_sharpe: float = 0.5           # Sharpe below this triggers watch
    min_win_rate: float = 0.45        # Win rate below this triggers watch
    
    # Status
    status: StrategyStatus = StrategyStatus.INCUBATION
    
    # Metadata
    inception_date: datetime = field(default_factory=datetime.now)
    description: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class StrategyMetrics:
    """Real-time metrics for a strategy."""
    strategy_id: str
    timestamp: datetime
    
    # Returns
    daily_return: float = 0.0
    mtd_return: float = 0.0
    ytd_return: float = 0.0
    total_return: float = 0.0
    
    # Risk
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    volatility_30d: float = 0.0
    var_95: float = 0.0
    
    # Performance
    sharpe_30d: float = 0.0
    sharpe_inception: float = 0.0
    win_rate_30d: float = 0.0
    profit_factor: float = 0.0
    
    # Correlation with portfolio
    correlation_with_portfolio: float = 0.0
    marginal_contribution_to_risk: float = 0.0
    
    # Current state
    current_allocation: float = 0.0
    current_positions: int = 0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0


@dataclass
class AllocationDecision:
    """Capital allocation decision."""
    timestamp: datetime
    strategy_id: str
    
    previous_allocation: float
    new_allocation: float
    change: float
    
    reason: str
    confidence: float = 1.0
    
    # Execution
    executed: bool = False
    execution_time: Optional[datetime] = None


@dataclass 
class OrchestratorState:
    """Current state of the orchestrator."""
    timestamp: datetime
    total_capital: float
    
    # Allocations
    allocations: Dict[str, float] = field(default_factory=dict)
    
    # Portfolio metrics
    portfolio_return: float = 0.0
    portfolio_volatility: float = 0.0
    portfolio_sharpe: float = 0.0
    portfolio_drawdown: float = 0.0
    
    # Risk budget usage
    risk_budget_used: float = 0.0
    risk_budget_remaining: float = 0.0
    
    # Recent decisions
    recent_decisions: List[AllocationDecision] = field(default_factory=list)


class RegimeDetector:
    """
    Detect market regime for regime-adaptive allocation.
    """
    
    def __init__(
        self,
        lookback_days: int = 63,
        vol_threshold_high: float = 0.25,
        vol_threshold_low: float = 0.12,
        trend_threshold: float = 0.05
    ):
        self.lookback_days = lookback_days
        self.vol_threshold_high = vol_threshold_high
        self.vol_threshold_low = vol_threshold_low
        self.trend_threshold = trend_threshold
        
    def detect(self, market_returns: pd.Series) -> str:
        """
        Detect current market regime.
        
        Returns: 'bull_low_vol', 'bull_high_vol', 'bear_low_vol', 'bear_high_vol', 'neutral'
        """
        if len(market_returns) < self.lookback_days:
            return 'neutral'
            
        recent = market_returns.tail(self.lookback_days)
        
        # Calculate metrics
        cumulative_return = (1 + recent).prod() - 1
        annualized_vol = recent.std() * np.sqrt(252)
        
        # Determine trend
        if cumulative_return > self.trend_threshold:
            trend = 'bull'
        elif cumulative_return < -self.trend_threshold:
            trend = 'bear'
        else:
            trend = 'neutral'
            
        # Determine volatility
        if annualized_vol > self.vol_threshold_high:
            vol = 'high_vol'
        elif annualized_vol < self.vol_threshold_low:
            vol = 'low_vol'
        else:
            vol = 'normal_vol'
            
        if trend == 'neutral':
            return 'neutral'
            
        return f"{trend}_{vol}"


class AllocationOptimizer:
    """
    Optimize capital allocation across strategies.
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.04,
        target_portfolio_vol: float = 0.15
    ):
        self.risk_free_rate = risk_free_rate
        self.target_vol = target_portfolio_vol
        
    def optimize(
        self,
        strategies: List[StrategyConfig],
        metrics: Dict[str, StrategyMetrics],
        returns_history: pd.DataFrame,  # Columns = strategy_id
        method: AllocationMethod = AllocationMethod.RISK_PARITY,
        regime: str = 'neutral'
    ) -> Dict[str, float]:
        """
        Calculate optimal allocations.
        
        Args:
            strategies: Strategy configurations
            metrics: Current metrics per strategy
            returns_history: Historical returns DataFrame
            method: Allocation method
            regime: Current market regime
            
        Returns:
            Dict of {strategy_id: allocation}
        """
        strategy_ids = [s.strategy_id for s in strategies if s.status == StrategyStatus.ACTIVE]
        
        if not strategy_ids:
            return {}
            
        # Filter to active strategies
        returns = returns_history[[s for s in strategy_ids if s in returns_history.columns]]
        
        if returns.empty or len(returns) < 30:
            # Not enough data, use equal weight
            return {s: 1.0 / len(strategy_ids) for s in strategy_ids}
            
        if method == AllocationMethod.EQUAL:
            weights = self._equal_weight(strategy_ids)
        elif method == AllocationMethod.RISK_PARITY:
            weights = self._risk_parity(returns)
        elif method == AllocationMethod.KELLY:
            weights = self._kelly(returns, metrics)
        elif method == AllocationMethod.MEAN_VARIANCE:
            weights = self._mean_variance(returns)
        elif method == AllocationMethod.REGIME_ADAPTIVE:
            weights = self._regime_adaptive(returns, metrics, regime)
        elif method == AllocationMethod.PERFORMANCE_WEIGHTED:
            weights = self._performance_weighted(metrics, strategy_ids)
        else:
            weights = self._equal_weight(strategy_ids)
            
        # Apply constraints
        weights = self._apply_constraints(weights, strategies)
        
        return weights
        
    def _equal_weight(self, strategy_ids: List[str]) -> Dict[str, float]:
        """Equal weight allocation."""
        n = len(strategy_ids)
        return {s: 1.0 / n for s in strategy_ids}
        
    def _risk_parity(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Risk parity allocation (equal risk contribution)."""
        # Calculate volatilities
        vols = returns.std() * np.sqrt(252)
        
        # Inverse volatility weighting (simplified risk parity)
        inv_vols = 1 / vols
        weights = inv_vols / inv_vols.sum()
        
        return weights.to_dict()
        
    def _kelly(
        self,
        returns: pd.DataFrame,
        metrics: Dict[str, StrategyMetrics]
    ) -> Dict[str, float]:
        """Kelly criterion allocation."""
        weights = {}
        
        for col in returns.columns:
            r = returns[col].dropna()
            if len(r) < 30:
                weights[col] = 0.1
                continue
                
            # Win rate and payoff ratio
            wins = r[r > 0]
            losses = r[r < 0]
            
            if len(losses) == 0 or len(wins) == 0:
                weights[col] = 0.1
                continue
                
            win_rate = len(wins) / len(r)
            avg_win = wins.mean()
            avg_loss = abs(losses.mean())
            
            if avg_loss == 0:
                weights[col] = 0.1
                continue
                
            payoff_ratio = avg_win / avg_loss
            
            # Kelly formula: f = p - (1-p)/b
            kelly = win_rate - (1 - win_rate) / payoff_ratio
            
            # Half-Kelly for safety
            weights[col] = max(0, kelly * 0.5)
            
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
            
        return weights
        
    def _mean_variance(self, returns: pd.DataFrame) -> Dict[str, float]:
        """Mean-variance optimization (Markowitz)."""
        from scipy.optimize import minimize
        
        n = len(returns.columns)
        
        # Expected returns and covariance
        mu = returns.mean() * 252
        cov = returns.cov() * 252
        
        def neg_sharpe(w):
            port_return = w @ mu
            port_vol = np.sqrt(w @ cov @ w)
            return -(port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
            
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Weights sum to 1
        ]
        bounds = [(0, 1) for _ in range(n)]
        
        # Initial guess
        w0 = np.ones(n) / n
        
        result = minimize(neg_sharpe, w0, method='SLSQP', bounds=bounds, constraints=constraints)
        
        return dict(zip(returns.columns, result.x))
        
    def _regime_adaptive(
        self,
        returns: pd.DataFrame,
        metrics: Dict[str, StrategyMetrics],
        regime: str
    ) -> Dict[str, float]:
        """Regime-adaptive allocation."""
        # Base weights from risk parity
        weights = self._risk_parity(returns)
        
        # Adjust based on regime
        if 'bear' in regime:
            # In bear markets, favor strategies with negative correlation
            for sid, w in weights.items():
                if sid in metrics:
                    corr = metrics[sid].correlation_with_portfolio
                    if corr < 0:
                        weights[sid] *= 1.5  # Boost uncorrelated strategies
                    elif corr > 0.5:
                        weights[sid] *= 0.7  # Reduce highly correlated
                        
        elif 'bull' in regime:
            # In bull markets, favor momentum strategies
            for sid, w in weights.items():
                if sid in metrics:
                    if metrics[sid].sharpe_30d > 1:
                        weights[sid] *= 1.3
                        
        if 'high_vol' in regime:
            # In high vol, reduce overall exposure
            weights = {k: v * 0.7 for k, v in weights.items()}
            
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
            
        return weights
        
    def _performance_weighted(
        self,
        metrics: Dict[str, StrategyMetrics],
        strategy_ids: List[str]
    ) -> Dict[str, float]:
        """Weight by recent performance (Sharpe)."""
        weights = {}
        
        for sid in strategy_ids:
            if sid in metrics:
                # Use 30-day Sharpe, but floor at 0
                weights[sid] = max(metrics[sid].sharpe_30d, 0)
            else:
                weights[sid] = 0.5  # Default
                
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
        else:
            weights = {s: 1.0/len(strategy_ids) for s in strategy_ids}
            
        return weights
        
    def _apply_constraints(
        self,
        weights: Dict[str, float],
        strategies: List[StrategyConfig]
    ) -> Dict[str, float]:
        """Apply min/max constraints."""
        config_map = {s.strategy_id: s for s in strategies}
        
        constrained = {}
        for sid, w in weights.items():
            if sid in config_map:
                cfg = config_map[sid]
                constrained[sid] = max(cfg.min_allocation, min(cfg.max_allocation, w))
            else:
                constrained[sid] = w
                
        # Re-normalize
        total = sum(constrained.values())
        if total > 0:
            constrained = {k: v/total for k, v in constrained.items()}
            
        return constrained


class DrawdownProtection:
    """
    Automatic deleveraging when drawdowns exceed thresholds.
    """
    
    def __init__(
        self,
        level_1_drawdown: float = 0.05,   # Reduce by 25%
        level_2_drawdown: float = 0.10,   # Reduce by 50%
        level_3_drawdown: float = 0.15,   # Reduce by 75%
        emergency_drawdown: float = 0.20  # Go to cash
    ):
        self.levels = [
            (level_1_drawdown, 0.75),
            (level_2_drawdown, 0.50),
            (level_3_drawdown, 0.25),
            (emergency_drawdown, 0.0)
        ]
        
    def get_scale_factor(self, current_drawdown: float) -> float:
        """Get scaling factor based on current drawdown."""
        for threshold, scale in self.levels:
            if current_drawdown >= threshold:
                return scale
        return 1.0
        
    def check_strategy(
        self,
        metrics: StrategyMetrics,
        config: StrategyConfig
    ) -> Tuple[bool, float, str]:
        """
        Check if strategy needs deleveraging.
        
        Returns: (needs_action, scale_factor, reason)
        """
        if metrics.current_drawdown >= config.max_drawdown:
            return True, 0.0, f"Max drawdown exceeded ({metrics.current_drawdown:.1%})"
            
        scale = self.get_scale_factor(metrics.current_drawdown)
        if scale < 1.0:
            return True, scale, f"Drawdown protection ({metrics.current_drawdown:.1%})"
            
        return False, 1.0, ""


class StrategyOrchestrator:
    """
    Main orchestrator for managing multiple strategies.
    """
    
    def __init__(
        self,
        total_capital: float,
        allocation_method: AllocationMethod = AllocationMethod.RISK_PARITY,
        rebalance_frequency: str = 'daily',
        risk_budget: float = 0.20  # Max 20% portfolio VaR
    ):
        self.total_capital = total_capital
        self.allocation_method = allocation_method
        self.rebalance_frequency = rebalance_frequency
        self.risk_budget = risk_budget
        
        # Components
        self.strategies: Dict[str, StrategyConfig] = {}
        self.metrics: Dict[str, StrategyMetrics] = {}
        self.returns_history: pd.DataFrame = pd.DataFrame()
        
        self.regime_detector = RegimeDetector()
        self.optimizer = AllocationOptimizer()
        self.drawdown_protection = DrawdownProtection()
        
        # State
        self.current_allocations: Dict[str, float] = {}
        self.decision_history: List[AllocationDecision] = []
        self.current_regime: str = 'neutral'
        
        # Callbacks
        self.on_rebalance: List[Callable[[Dict[str, float]], None]] = []
        self.on_alert: List[Callable[[str, str], None]] = []
        
    def add_strategy(self, config: StrategyConfig):
        """Add a strategy to the orchestrator."""
        self.strategies[config.strategy_id] = config
        self.current_allocations[config.strategy_id] = 0.0
        logger.info(f"Added strategy: {config.name} ({config.strategy_id})")
        
    def remove_strategy(self, strategy_id: str):
        """Remove a strategy."""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            self.current_allocations.pop(strategy_id, None)
            logger.info(f"Removed strategy: {strategy_id}")
            
    def update_metrics(self, strategy_id: str, metrics: StrategyMetrics):
        """Update metrics for a strategy."""
        self.metrics[strategy_id] = metrics
        
        # Check for alerts
        if strategy_id in self.strategies:
            config = self.strategies[strategy_id]
            self._check_strategy_health(strategy_id, metrics, config)
            
    def update_returns(self, returns: pd.Series):
        """
        Update returns history.
        
        Args:
            returns: Series with strategy_id as index, daily returns as values
        """
        today = datetime.now().date()
        new_row = pd.DataFrame([returns], index=[today])
        
        self.returns_history = pd.concat([self.returns_history, new_row])
        self.returns_history = self.returns_history.tail(504)  # Keep 2 years
        
    def update_market(self, market_returns: pd.Series):
        """Update market regime detection."""
        self.current_regime = self.regime_detector.detect(market_returns)
        logger.debug(f"Current regime: {self.current_regime}")
        
    def rebalance(self, force: bool = False) -> Dict[str, AllocationDecision]:
        """
        Rebalance capital across strategies.
        
        Returns dict of allocation decisions made.
        """
        # Get active strategies
        active_strategies = [
            s for s in self.strategies.values()
            if s.status in [StrategyStatus.ACTIVE, StrategyStatus.WATCH]
        ]
        
        if not active_strategies:
            logger.warning("No active strategies to allocate to")
            return {}
            
        # Calculate optimal allocations
        optimal = self.optimizer.optimize(
            strategies=active_strategies,
            metrics=self.metrics,
            returns_history=self.returns_history,
            method=self.allocation_method,
            regime=self.current_regime
        )
        
        # Apply drawdown protection
        for sid, alloc in optimal.items():
            if sid in self.metrics and sid in self.strategies:
                needs_action, scale, reason = self.drawdown_protection.check_strategy(
                    self.metrics[sid],
                    self.strategies[sid]
                )
                if needs_action:
                    optimal[sid] = alloc * scale
                    self._trigger_alert(sid, reason)
                    
        # Re-normalize after protection
        total = sum(optimal.values())
        if total > 0:
            optimal = {k: v/total for k, v in optimal.items()}
            
        # Create decisions
        decisions = {}
        for sid, new_alloc in optimal.items():
            old_alloc = self.current_allocations.get(sid, 0)
            change = new_alloc - old_alloc
            
            if abs(change) > 0.01 or force:  # Only act on >1% changes
                decision = AllocationDecision(
                    timestamp=datetime.now(),
                    strategy_id=sid,
                    previous_allocation=old_alloc,
                    new_allocation=new_alloc,
                    change=change,
                    reason=self._get_rebalance_reason(sid, old_alloc, new_alloc),
                    confidence=0.9
                )
                decisions[sid] = decision
                self.decision_history.append(decision)
                self.current_allocations[sid] = new_alloc
                
        # Notify callbacks
        if decisions:
            for callback in self.on_rebalance:
                try:
                    callback(self.current_allocations)
                except Exception as e:
                    logger.error(f"Rebalance callback error: {e}")
                    
        return decisions
        
    def _check_strategy_health(
        self,
        strategy_id: str,
        metrics: StrategyMetrics,
        config: StrategyConfig
    ):
        """Check strategy health and potentially change status."""
        # Check for problems
        problems = []
        
        if metrics.sharpe_30d < config.min_sharpe:
            problems.append(f"Low Sharpe ({metrics.sharpe_30d:.2f})")
            
        if metrics.win_rate_30d < config.min_win_rate:
            problems.append(f"Low win rate ({metrics.win_rate_30d:.1%})")
            
        if metrics.current_drawdown > config.max_drawdown * 0.8:
            problems.append(f"Approaching max drawdown ({metrics.current_drawdown:.1%})")
            
        if metrics.volatility_30d > config.max_volatility:
            problems.append(f"Volatility limit ({metrics.volatility_30d:.1%})")
            
        # Update status based on problems
        if len(problems) >= 2 and config.status == StrategyStatus.ACTIVE:
            config.status = StrategyStatus.WATCH
            self._trigger_alert(strategy_id, f"Strategy moved to WATCH: {', '.join(problems)}")
            
        elif len(problems) == 0 and config.status == StrategyStatus.WATCH:
            config.status = StrategyStatus.ACTIVE
            self._trigger_alert(strategy_id, "Strategy recovered to ACTIVE")
            
    def _get_rebalance_reason(
        self,
        strategy_id: str,
        old_alloc: float,
        new_alloc: float
    ) -> str:
        """Generate human-readable reason for allocation change."""
        if strategy_id not in self.metrics:
            return "Initial allocation"
            
        metrics = self.metrics[strategy_id]
        reasons = []
        
        if new_alloc > old_alloc:
            if metrics.sharpe_30d > 1.5:
                reasons.append("Strong recent performance")
            if 'bear' in self.current_regime and metrics.correlation_with_portfolio < 0:
                reasons.append("Low correlation in bear market")
        else:
            if metrics.current_drawdown > 0.05:
                reasons.append("Drawdown protection")
            if metrics.sharpe_30d < 0.5:
                reasons.append("Weak recent performance")
                
        return "; ".join(reasons) if reasons else "Periodic rebalance"
        
    def _trigger_alert(self, strategy_id: str, message: str):
        """Trigger alert to callbacks."""
        logger.warning(f"Alert [{strategy_id}]: {message}")
        for callback in self.on_alert:
            try:
                callback(strategy_id, message)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
                
    def get_state(self) -> OrchestratorState:
        """Get current orchestrator state."""
        # Calculate portfolio metrics
        portfolio_returns = pd.Series(dtype=float)
        for sid, alloc in self.current_allocations.items():
            if sid in self.returns_history.columns:
                portfolio_returns = portfolio_returns.add(
                    self.returns_history[sid] * alloc,
                    fill_value=0
                )
                
        portfolio_vol = portfolio_returns.std() * np.sqrt(252) if len(portfolio_returns) > 0 else 0
        portfolio_ret = portfolio_returns.mean() * 252 if len(portfolio_returns) > 0 else 0
        portfolio_sharpe = portfolio_ret / portfolio_vol if portfolio_vol > 0 else 0
        
        return OrchestratorState(
            timestamp=datetime.now(),
            total_capital=self.total_capital,
            allocations=self.current_allocations.copy(),
            portfolio_return=portfolio_ret,
            portfolio_volatility=portfolio_vol,
            portfolio_sharpe=portfolio_sharpe,
            portfolio_drawdown=0,  # Would calculate from equity curve
            risk_budget_used=portfolio_vol / self.risk_budget if self.risk_budget > 0 else 0,
            risk_budget_remaining=max(0, self.risk_budget - portfolio_vol),
            recent_decisions=self.decision_history[-10:]
        )
        
    def get_allocation_in_dollars(self) -> Dict[str, float]:
        """Get current allocations in dollar terms."""
        return {
            sid: alloc * self.total_capital
            for sid, alloc in self.current_allocations.items()
        }
