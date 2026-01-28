"""
Strategy Capacity Analyzer
QUANT_INDUSTRY_V1

Industry Problem: Most strategies look great on paper but fail with real capital.
A strategy that returns 50% with $10K might return 5% with $1M due to slippage
and market impact. Retail quants rarely analyze this.

Our Solution:
- Estimate maximum capacity before returns degrade
- Model market impact at various capital levels
- Identify capacity constraints (liquidity, volatility, crowding)
- Recommend optimal position sizes
- Project returns at different AUM levels
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from scipy import optimize

logger = logging.getLogger(__name__)


class CapacityConstraint(Enum):
    """Types of capacity constraints."""
    LIQUIDITY = "liquidity"       # Not enough volume to trade
    MARKET_IMPACT = "market_impact"  # Moving price against yourself
    VOLATILITY = "volatility"      # Can't execute in time
    CROWDING = "crowding"          # Too many people doing same trade
    BORROWING = "borrowing"        # Can't find shares to short


@dataclass
class CapacityReport:
    """Strategy capacity analysis report."""
    # Core capacity metrics
    max_capacity_usd: float
    optimal_capacity_usd: float
    current_capacity_utilization: float
    
    # Return projections at different levels
    return_at_100k: float
    return_at_1m: float
    return_at_10m: float
    return_at_100m: float
    
    # Degradation curve
    capacity_curve: List[Dict[str, float]]
    
    # Constraints
    binding_constraint: CapacityConstraint
    constraint_details: Dict[str, Any]
    
    # Per-symbol analysis
    symbol_capacities: Dict[str, float]
    bottleneck_symbols: List[str]
    
    # Recommendations
    recommendations: List[str]
    
    def __str__(self) -> str:
        return f"""
╔══════════════════════════════════════════════════════════════════╗
║                  STRATEGY CAPACITY REPORT                        ║
╠══════════════════════════════════════════════════════════════════╣
║  Maximum Capacity:    ${self.max_capacity_usd:>15,.0f}                    ║
║  Optimal Capacity:    ${self.optimal_capacity_usd:>15,.0f}                    ║
║  Binding Constraint:  {self.binding_constraint.value:<20}                    ║
╠══════════════════════════════════════════════════════════════════╣
║                    PROJECTED RETURNS (Annual)                    ║
╠══════════════════════════════════════════════════════════════════╣
║  At $100K:      {self.return_at_100k*100:>6.1f}%                                      ║
║  At $1M:        {self.return_at_1m*100:>6.1f}%                                      ║
║  At $10M:       {self.return_at_10m*100:>6.1f}%                                      ║
║  At $100M:      {self.return_at_100m*100:>6.1f}%                                      ║
╠══════════════════════════════════════════════════════════════════╣
║  Bottleneck Symbols: {', '.join(self.bottleneck_symbols[:5]):<30}         ║
╚══════════════════════════════════════════════════════════════════╝
"""


class MarketImpactModel:
    """
    Market impact model for estimating execution costs.
    
    Uses the Almgren-Chriss model and empirical adjustments.
    """
    
    def __init__(
        self,
        temporary_impact: float = 0.1,    # Temporary impact coefficient
        permanent_impact: float = 0.05,    # Permanent impact coefficient
        volatility_scaling: float = 0.5    # How much volatility affects impact
    ):
        self.temporary_impact = temporary_impact
        self.permanent_impact = permanent_impact
        self.volatility_scaling = volatility_scaling
        
    def estimate_impact(
        self,
        trade_value: float,
        adv: float,          # Average daily volume in dollars
        volatility: float,    # Daily volatility
        spread_bps: float = 5.0,
        side: str = 'buy'
    ) -> Dict[str, float]:
        """
        Estimate market impact for a trade.
        
        Args:
            trade_value: Dollar value of trade
            adv: Average daily trading volume in dollars
            volatility: Daily return volatility
            spread_bps: Bid-ask spread in basis points
            side: 'buy' or 'sell'
            
        Returns:
            Dictionary with impact components
        """
        # Participation rate
        participation = trade_value / adv if adv > 0 else 1.0
        
        # Spread cost (always pay half spread)
        spread_cost = spread_bps / 10000 / 2
        
        # Temporary impact (square root model)
        temp_impact = self.temporary_impact * volatility * np.sqrt(participation)
        
        # Permanent impact (linear model)
        perm_impact = self.permanent_impact * volatility * participation
        
        # Volatility adjustment
        vol_adj = 1 + self.volatility_scaling * (volatility / 0.02 - 1)
        
        # Total impact
        total_impact = (spread_cost + temp_impact + perm_impact) * vol_adj
        
        # For sells, impact is typically worse
        if side == 'sell':
            total_impact *= 1.1
            
        return {
            'spread_cost': spread_cost,
            'temporary_impact': temp_impact,
            'permanent_impact': perm_impact,
            'volatility_adjustment': vol_adj,
            'total_impact': total_impact,
            'participation_rate': participation
        }
        
    def estimate_execution_cost(
        self,
        trade_value: float,
        adv: float,
        volatility: float,
        urgency: float = 0.5  # 0 = patient, 1 = urgent
    ) -> float:
        """
        Estimate total execution cost as fraction of trade value.
        
        Higher urgency = more impact but less timing risk.
        """
        # Patient execution (TWAP over day)
        patient_impact = self.estimate_impact(trade_value, adv, volatility)['total_impact']
        
        # Urgent execution (trade immediately)
        urgent_impact = patient_impact * 2.5
        
        # Blend based on urgency
        return patient_impact * (1 - urgency) + urgent_impact * urgency


class LiquidityAnalyzer:
    """
    Analyze liquidity constraints for a strategy.
    """
    
    def __init__(
        self,
        max_participation_rate: float = 0.10,  # Max 10% of daily volume
        max_spread_bps: float = 50.0,          # Max acceptable spread
        min_adv: float = 1_000_000             # Minimum $1M daily volume
    ):
        self.max_participation_rate = max_participation_rate
        self.max_spread_bps = max_spread_bps
        self.min_adv = min_adv
        
    def analyze_symbol(
        self,
        symbol: str,
        adv: float,
        spread_bps: float,
        target_position: float,
        execution_days: int = 1
    ) -> Dict[str, Any]:
        """
        Analyze liquidity constraints for a single symbol.
        
        Returns:
            max_position: Maximum position value
            constraint: What limits position size
            liquidity_score: 0-100 score
        """
        # Calculate max position based on ADV
        max_from_participation = adv * self.max_participation_rate * execution_days
        
        # Check spread constraint
        spread_ok = spread_bps <= self.max_spread_bps
        
        # Check minimum liquidity
        adv_ok = adv >= self.min_adv
        
        # Determine binding constraint
        if not adv_ok:
            constraint = CapacityConstraint.LIQUIDITY
            max_position = 0
        elif not spread_ok:
            constraint = CapacityConstraint.LIQUIDITY
            max_position = max_from_participation * 0.5  # Reduce for wide spread
        else:
            constraint = CapacityConstraint.MARKET_IMPACT
            max_position = max_from_participation
            
        # Liquidity score
        adv_score = min(adv / 10_000_000 * 50, 50)  # 0-50 based on ADV
        spread_score = max(50 - spread_bps, 0)       # 0-50 based on spread
        liquidity_score = adv_score + spread_score
        
        return {
            'symbol': symbol,
            'max_position': max_position,
            'constraint': constraint,
            'liquidity_score': liquidity_score,
            'adv': adv,
            'spread_bps': spread_bps,
            'can_trade': adv_ok
        }


class CapacityAnalyzer:
    """
    Complete strategy capacity analysis.
    
    Estimates how much capital a strategy can deploy before returns degrade.
    """
    
    def __init__(
        self,
        impact_model: Optional[MarketImpactModel] = None,
        liquidity_analyzer: Optional[LiquidityAnalyzer] = None,
        target_return_retention: float = 0.8  # Keep 80% of backtest returns
    ):
        self.impact_model = impact_model or MarketImpactModel()
        self.liquidity_analyzer = liquidity_analyzer or LiquidityAnalyzer()
        self.target_return_retention = target_return_retention
        
    def analyze(
        self,
        strategy_returns: pd.Series,
        positions: pd.DataFrame,  # DataFrame with columns: date, symbol, weight
        market_data: Dict[str, Dict[str, float]],  # {symbol: {adv, spread, volatility}}
        rebalance_frequency: str = 'weekly',
        base_aum: float = 100_000
    ) -> CapacityReport:
        """
        Analyze strategy capacity.
        
        Args:
            strategy_returns: Strategy return series (at base AUM)
            positions: Position history
            market_data: Market data per symbol
            rebalance_frequency: How often strategy rebalances
            base_aum: AUM used in backtest
            
        Returns:
            CapacityReport with analysis
        """
        # Calculate base metrics
        base_annual_return = strategy_returns.mean() * 252
        base_volatility = strategy_returns.std() * np.sqrt(252)
        base_sharpe = base_annual_return / base_volatility if base_volatility > 0 else 0
        
        # Analyze liquidity per symbol
        symbol_analysis = {}
        for symbol in positions['symbol'].unique():
            if symbol in market_data:
                data = market_data[symbol]
                max_weight = positions[positions['symbol'] == symbol]['weight'].abs().max()
                analysis = self.liquidity_analyzer.analyze_symbol(
                    symbol=symbol,
                    adv=data.get('adv', 10_000_000),
                    spread_bps=data.get('spread', 5),
                    target_position=max_weight * base_aum
                )
                symbol_analysis[symbol] = analysis
                
        # Calculate capacity at different AUM levels
        aum_levels = [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000, 
                      50_000_000, 100_000_000, 500_000_000]
        capacity_curve = []
        
        for aum in aum_levels:
            projected = self._project_returns_at_aum(
                base_return=base_annual_return,
                base_aum=base_aum,
                target_aum=aum,
                positions=positions,
                market_data=market_data,
                rebalance_frequency=rebalance_frequency
            )
            capacity_curve.append({
                'aum': aum,
                'projected_return': projected['return'],
                'return_retention': projected['return'] / base_annual_return if base_annual_return > 0 else 0,
                'total_impact': projected['total_impact'],
                'turnover_cost': projected['turnover_cost']
            })
            
        # Find maximum and optimal capacity
        max_capacity = self._find_max_capacity(capacity_curve)
        optimal_capacity = self._find_optimal_capacity(capacity_curve, base_annual_return)
        
        # Identify bottleneck symbols
        bottlenecks = sorted(
            symbol_analysis.items(),
            key=lambda x: x[1]['liquidity_score']
        )[:5]
        bottleneck_symbols = [b[0] for b in bottlenecks]
        
        # Determine binding constraint
        binding_constraint = self._identify_binding_constraint(
            capacity_curve, symbol_analysis
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            max_capacity, optimal_capacity, binding_constraint,
            bottleneck_symbols, symbol_analysis
        )
        
        # Get returns at specific levels
        return_at_100k = self._get_return_at_aum(capacity_curve, 100_000)
        return_at_1m = self._get_return_at_aum(capacity_curve, 1_000_000)
        return_at_10m = self._get_return_at_aum(capacity_curve, 10_000_000)
        return_at_100m = self._get_return_at_aum(capacity_curve, 100_000_000)
        
        return CapacityReport(
            max_capacity_usd=max_capacity,
            optimal_capacity_usd=optimal_capacity,
            current_capacity_utilization=base_aum / optimal_capacity if optimal_capacity > 0 else 1.0,
            return_at_100k=return_at_100k,
            return_at_1m=return_at_1m,
            return_at_10m=return_at_10m,
            return_at_100m=return_at_100m,
            capacity_curve=capacity_curve,
            binding_constraint=binding_constraint,
            constraint_details={'symbol_analysis': symbol_analysis},
            symbol_capacities={s: a['max_position'] for s, a in symbol_analysis.items()},
            bottleneck_symbols=bottleneck_symbols,
            recommendations=recommendations
        )
        
    def _project_returns_at_aum(
        self,
        base_return: float,
        base_aum: float,
        target_aum: float,
        positions: pd.DataFrame,
        market_data: Dict[str, Dict[str, float]],
        rebalance_frequency: str
    ) -> Dict[str, float]:
        """Project returns at a given AUM level."""
        # Estimate turnover
        rebalances_per_year = {
            'daily': 252,
            'weekly': 52,
            'biweekly': 26,
            'monthly': 12,
            'quarterly': 4
        }.get(rebalance_frequency, 52)
        
        # Estimate average turnover per rebalance
        avg_turnover = 0.5  # 50% turnover assumed
        annual_turnover = avg_turnover * rebalances_per_year
        
        # Calculate average market impact
        total_impact = 0
        total_weight = 0
        
        for symbol in positions['symbol'].unique():
            if symbol not in market_data:
                continue
                
            data = market_data[symbol]
            avg_weight = positions[positions['symbol'] == symbol]['weight'].abs().mean()
            
            trade_value = target_aum * avg_weight * avg_turnover
            
            impact = self.impact_model.estimate_impact(
                trade_value=trade_value,
                adv=data.get('adv', 10_000_000),
                volatility=data.get('volatility', 0.02),
                spread_bps=data.get('spread', 5)
            )
            
            total_impact += impact['total_impact'] * avg_weight
            total_weight += avg_weight
            
        if total_weight > 0:
            avg_impact = total_impact / total_weight
        else:
            avg_impact = 0
            
        # Total cost from turnover
        turnover_cost = avg_impact * annual_turnover
        
        # Projected return (subtract costs from base return)
        projected_return = base_return - turnover_cost
        
        # Apply capacity decay (returns degrade faster at high AUM)
        scale_factor = target_aum / base_aum
        decay = 1 - 0.1 * np.log10(max(scale_factor, 1))  # 10% decay per 10x scale
        decay = max(decay, 0.1)  # Floor at 10% of original
        
        projected_return *= decay
        
        return {
            'return': max(projected_return, -0.5),  # Floor at -50%
            'total_impact': avg_impact,
            'turnover_cost': turnover_cost,
            'scale_decay': decay
        }
        
    def _find_max_capacity(self, curve: List[Dict]) -> float:
        """Find AUM where returns go to zero."""
        for point in curve:
            if point['projected_return'] <= 0:
                return point['aum']
        return curve[-1]['aum']  # If never hits zero, return max tested
        
    def _find_optimal_capacity(self, curve: List[Dict], base_return: float) -> float:
        """Find AUM that maximizes absolute dollar returns."""
        max_dollar_return = 0
        optimal_aum = curve[0]['aum']
        
        for point in curve:
            dollar_return = point['aum'] * point['projected_return']
            if dollar_return > max_dollar_return:
                max_dollar_return = dollar_return
                optimal_aum = point['aum']
                
        return optimal_aum
        
    def _get_return_at_aum(self, curve: List[Dict], target_aum: float) -> float:
        """Interpolate return at specific AUM."""
        for i, point in enumerate(curve):
            if point['aum'] >= target_aum:
                if i == 0:
                    return point['projected_return']
                # Linear interpolation
                prev = curve[i-1]
                ratio = (target_aum - prev['aum']) / (point['aum'] - prev['aum'])
                return prev['projected_return'] + ratio * (point['projected_return'] - prev['projected_return'])
        return curve[-1]['projected_return']
        
    def _identify_binding_constraint(
        self,
        curve: List[Dict],
        symbol_analysis: Dict
    ) -> CapacityConstraint:
        """Identify the primary constraint on capacity."""
        # Check if liquidity is the main issue
        illiquid_count = sum(1 for s in symbol_analysis.values() if not s['can_trade'])
        if illiquid_count > len(symbol_analysis) * 0.2:
            return CapacityConstraint.LIQUIDITY
            
        # Check impact degradation
        if len(curve) > 1:
            impact_growth = curve[-1]['total_impact'] / curve[0]['total_impact'] if curve[0]['total_impact'] > 0 else 1
            if impact_growth > 5:
                return CapacityConstraint.MARKET_IMPACT
                
        # Default to market impact (most common)
        return CapacityConstraint.MARKET_IMPACT
        
    def _generate_recommendations(
        self,
        max_capacity: float,
        optimal_capacity: float,
        constraint: CapacityConstraint,
        bottlenecks: List[str],
        symbol_analysis: Dict
    ) -> List[str]:
        """Generate actionable recommendations."""
        recs = []
        
        if max_capacity < 1_000_000:
            recs.append("⚠️ Low capacity (<$1M). Strategy may not be scalable for serious capital.")
            
        if constraint == CapacityConstraint.LIQUIDITY:
            recs.append(f"💧 Liquidity constrained. Consider removing illiquid symbols: {', '.join(bottlenecks[:3])}")
            
        if constraint == CapacityConstraint.MARKET_IMPACT:
            recs.append("📊 Market impact is main constraint. Consider: slower execution, more symbols, less turnover.")
            
        if optimal_capacity > max_capacity * 0.8:
            recs.append("📈 Returns degrade smoothly. Scale up gradually and monitor impact.")
        else:
            recs.append("⚡ Sharp capacity cliff. Do not exceed optimal capacity.")
            
        if len(bottlenecks) > 0:
            recs.append(f"🔍 Bottleneck symbols to watch: {', '.join(bottlenecks)}")
            
        return recs


class CrowdingDetector:
    """
    Detect strategy crowding - when too many people run similar strategies.
    
    Crowded strategies have:
    - Correlated returns with known factors
    - Capacity constraints from aggregate flow
    - Higher risk of "crowded unwinds"
    """
    
    def __init__(self):
        self.factor_exposures = {}
        
    def estimate_crowding(
        self,
        strategy_returns: pd.Series,
        factor_returns: pd.DataFrame,  # Common factors (momentum, value, etc.)
        strategy_positions: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Estimate how crowded a strategy is.
        
        Returns:
            crowding_score: 0-100 (higher = more crowded)
            correlated_factors: Which factors strategy correlates with
            crowding_risk: Risk of crowded unwind
        """
        # Correlation with known factors
        factor_corrs = {}
        for factor in factor_returns.columns:
            corr = strategy_returns.corr(factor_returns[factor])
            factor_corrs[factor] = corr
            
        # High correlation with popular factors = crowded
        max_factor_corr = max(abs(c) for c in factor_corrs.values())
        
        # Calculate crowding score
        crowding_score = max_factor_corr * 100
        
        # Identify which factors
        correlated_factors = [
            f for f, c in factor_corrs.items() if abs(c) > 0.5
        ]
        
        # Estimate crowding risk (correlation with momentum is particularly dangerous)
        momentum_corr = abs(factor_corrs.get('momentum', 0))
        value_corr = abs(factor_corrs.get('value', 0))
        
        if momentum_corr > 0.7:
            crowding_risk = 'HIGH'
        elif momentum_corr > 0.5 or value_corr > 0.5:
            crowding_risk = 'MODERATE'
        else:
            crowding_risk = 'LOW'
            
        return {
            'crowding_score': crowding_score,
            'factor_correlations': factor_corrs,
            'correlated_factors': correlated_factors,
            'crowding_risk': crowding_risk,
            'recommendations': self._crowding_recommendations(crowding_score, correlated_factors)
        }
        
    def _crowding_recommendations(
        self,
        score: float,
        factors: List[str]
    ) -> List[str]:
        recs = []
        
        if score > 70:
            recs.append("🚨 HIGH crowding risk. Strategy highly correlated with popular factors.")
            recs.append("Consider: differentiating signal, hedging factor exposure, timing entry differently.")
            
        if 'momentum' in factors:
            recs.append("📈 Momentum exposure detected. Watch for momentum crashes/reversals.")
            
        if 'value' in factors:
            recs.append("💰 Value exposure detected. Be prepared for extended underperformance periods.")
            
        if score < 30:
            recs.append("✓ Low crowding. Strategy appears differentiated.")
            
        return recs
