"""
Strategy Diversification Analysis
QUANT_INDUSTRY_V1

Implements:
- Correlation matrix analysis for strategies
- Diversification ratio calculation
- Portfolio risk decomposition
- Strategy clustering for redundancy detection
- Optimal strategy combination suggestions

Rollback Plan: Delete this file
Tests Required: Correlation accuracy, risk metrics validation
Failure Modes: Return empty analysis, log warnings
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
import json

logger = logging.getLogger(__name__)


class DiversificationLevel(Enum):
    """Diversification quality assessment."""
    POOR = "poor"           # High correlation, low diversification
    MODERATE = "moderate"   # Some diversification
    GOOD = "good"           # Well diversified
    EXCELLENT = "excellent" # Highly diversified


@dataclass
class StrategyStats:
    """Statistics for a single strategy."""
    strategy_id: str
    returns: np.ndarray
    mean_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    
    @classmethod
    def from_returns(cls, strategy_id: str, returns: np.ndarray, rf_rate: float = 0.0) -> 'StrategyStats':
        """Calculate statistics from return series."""
        mean_ret = np.mean(returns)
        vol = np.std(returns)
        sharpe = (mean_ret - rf_rate) / vol if vol > 0 else 0
        
        # Calculate max drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_dd = np.min(drawdowns)
        
        # Win rate
        win_rate = np.mean(returns > 0)
        
        return cls(
            strategy_id=strategy_id,
            returns=returns,
            mean_return=mean_ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate
        )


@dataclass
class CorrelationAnalysis:
    """Results of correlation analysis."""
    correlation_matrix: np.ndarray
    strategy_ids: List[str]
    avg_correlation: float
    max_correlation: float
    min_correlation: float
    highly_correlated_pairs: List[Tuple[str, str, float]]
    
    def get_correlation(self, strat1: str, strat2: str) -> float:
        """Get correlation between two strategies."""
        idx1 = self.strategy_ids.index(strat1)
        idx2 = self.strategy_ids.index(strat2)
        return self.correlation_matrix[idx1, idx2]


@dataclass
class DiversificationReport:
    """Complete diversification analysis report."""
    timestamp: datetime
    n_strategies: int
    diversification_ratio: float
    portfolio_concentration: float
    effective_n_strategies: float
    diversification_level: DiversificationLevel
    correlation_analysis: CorrelationAnalysis
    risk_decomposition: Dict[str, float]
    recommendations: List[str]
    cluster_assignments: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'n_strategies': self.n_strategies,
            'diversification_ratio': self.diversification_ratio,
            'portfolio_concentration': self.portfolio_concentration,
            'effective_n_strategies': self.effective_n_strategies,
            'diversification_level': self.diversification_level.value,
            'avg_correlation': self.correlation_analysis.avg_correlation,
            'highly_correlated_pairs': self.correlation_analysis.highly_correlated_pairs,
            'risk_decomposition': self.risk_decomposition,
            'recommendations': self.recommendations,
            'cluster_assignments': self.cluster_assignments
        }


class StrategyDiversificationAnalyzer:
    """
    Analyzer for strategy diversification and correlation.
    
    Example:
        analyzer = StrategyDiversificationAnalyzer()
        
        # Add strategy returns
        analyzer.add_strategy('momentum', momentum_returns)
        analyzer.add_strategy('mean_reversion', mr_returns)
        analyzer.add_strategy('ml_signal', ml_returns)
        
        # Analyze
        report = analyzer.analyze(weights={'momentum': 0.4, 'mean_reversion': 0.3, 'ml_signal': 0.3})
        
        print(f"Diversification Ratio: {report.diversification_ratio:.2f}")
        print(f"Level: {report.diversification_level.value}")
    """
    
    def __init__(
        self,
        correlation_threshold: float = 0.7,
        min_history_length: int = 30
    ):
        self.correlation_threshold = correlation_threshold
        self.min_history_length = min_history_length
        
        self.strategies: Dict[str, StrategyStats] = {}
        self._returns_matrix: Optional[np.ndarray] = None
        
    def add_strategy(
        self,
        strategy_id: str,
        returns: np.ndarray,
        rf_rate: float = 0.0
    ):
        """Add a strategy's return series."""
        if len(returns) < self.min_history_length:
            logger.warning(f"Strategy {strategy_id} has insufficient history: {len(returns)} < {self.min_history_length}")
            
        stats = StrategyStats.from_returns(strategy_id, returns, rf_rate)
        self.strategies[strategy_id] = stats
        self._returns_matrix = None  # Invalidate cache
        
    def remove_strategy(self, strategy_id: str):
        """Remove a strategy."""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            self._returns_matrix = None
            
    def _build_returns_matrix(self) -> np.ndarray:
        """Build aligned returns matrix."""
        if self._returns_matrix is not None:
            return self._returns_matrix
            
        if not self.strategies:
            return np.array([])
            
        # Find minimum length
        min_len = min(len(s.returns) for s in self.strategies.values())
        
        # Build matrix with aligned returns (use tail)
        matrix = np.column_stack([
            s.returns[-min_len:] for s in self.strategies.values()
        ])
        
        self._returns_matrix = matrix
        return matrix
    
    def calculate_correlation_matrix(self) -> CorrelationAnalysis:
        """Calculate correlation matrix between strategies."""
        returns = self._build_returns_matrix()
        strategy_ids = list(self.strategies.keys())
        
        if len(returns) == 0:
            return CorrelationAnalysis(
                correlation_matrix=np.array([]),
                strategy_ids=[],
                avg_correlation=0,
                max_correlation=0,
                min_correlation=0,
                highly_correlated_pairs=[]
            )
            
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(returns.T)
        
        # Handle single strategy case
        if corr_matrix.ndim == 0:
            corr_matrix = np.array([[1.0]])
            
        # Find statistics
        n = len(strategy_ids)
        if n > 1:
            # Get upper triangle (excluding diagonal)
            upper_idx = np.triu_indices(n, k=1)
            correlations = corr_matrix[upper_idx]
            
            avg_corr = np.mean(correlations)
            max_corr = np.max(correlations)
            min_corr = np.min(correlations)
            
            # Find highly correlated pairs
            high_corr_pairs = []
            for i in range(n):
                for j in range(i + 1, n):
                    corr = corr_matrix[i, j]
                    if abs(corr) >= self.correlation_threshold:
                        high_corr_pairs.append((strategy_ids[i], strategy_ids[j], corr))
        else:
            avg_corr = 1.0
            max_corr = 1.0
            min_corr = 1.0
            high_corr_pairs = []
            
        return CorrelationAnalysis(
            correlation_matrix=corr_matrix,
            strategy_ids=strategy_ids,
            avg_correlation=avg_corr,
            max_correlation=max_corr,
            min_correlation=min_corr,
            highly_correlated_pairs=high_corr_pairs
        )
    
    def calculate_diversification_ratio(
        self,
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate Diversification Ratio (DR).
        
        DR = Weighted average volatility / Portfolio volatility
        DR > 1 indicates diversification benefit
        """
        if not self.strategies:
            return 1.0
            
        strategy_ids = list(self.strategies.keys())
        
        # Use equal weights if not provided
        if weights is None:
            weights = {s: 1.0 / len(strategy_ids) for s in strategy_ids}
            
        # Normalize weights
        total_weight = sum(weights.values())
        w = np.array([weights.get(s, 0) / total_weight for s in strategy_ids])
        
        # Get volatilities
        vols = np.array([self.strategies[s].volatility for s in strategy_ids])
        
        # Weighted average volatility
        weighted_avg_vol = np.dot(w, vols)
        
        # Portfolio volatility
        returns = self._build_returns_matrix()
        if len(returns) == 0:
            return 1.0
            
        portfolio_returns = np.dot(returns, w)
        portfolio_vol = np.std(portfolio_returns)
        
        if portfolio_vol == 0:
            return 1.0
            
        return weighted_avg_vol / portfolio_vol
    
    def calculate_effective_n(
        self,
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate effective number of strategies (Effective N).
        
        Based on Herfindahl-Hirschman Index.
        Effective N = 1 / sum(w_i^2)
        """
        if not self.strategies:
            return 0.0
            
        strategy_ids = list(self.strategies.keys())
        
        if weights is None:
            weights = {s: 1.0 / len(strategy_ids) for s in strategy_ids}
            
        total_weight = sum(weights.values())
        w = np.array([weights.get(s, 0) / total_weight for s in strategy_ids])
        
        hhi = np.sum(w ** 2)
        return 1.0 / hhi if hhi > 0 else len(strategy_ids)
    
    def decompose_portfolio_risk(
        self,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Decompose portfolio risk into strategy contributions.
        
        Returns: Dict of strategy_id -> risk contribution percentage
        """
        if not self.strategies:
            return {}
            
        strategy_ids = list(self.strategies.keys())
        n = len(strategy_ids)
        
        if weights is None:
            weights = {s: 1.0 / n for s in strategy_ids}
            
        total_weight = sum(weights.values())
        w = np.array([weights.get(s, 0) / total_weight for s in strategy_ids])
        
        # Build covariance matrix
        returns = self._build_returns_matrix()
        if len(returns) == 0:
            return {s: 1.0 / n for s in strategy_ids}
            
        cov_matrix = np.cov(returns.T)
        if cov_matrix.ndim == 0:
            cov_matrix = np.array([[cov_matrix]])
            
        # Portfolio variance
        port_var = np.dot(w, np.dot(cov_matrix, w))
        
        if port_var == 0:
            return {s: 1.0 / n for s in strategy_ids}
            
        # Marginal contribution to risk
        mcr = np.dot(cov_matrix, w) / np.sqrt(port_var)
        
        # Risk contribution
        rc = w * mcr
        total_rc = np.sum(np.abs(rc))
        
        if total_rc == 0:
            return {s: 1.0 / n for s in strategy_ids}
            
        return {s: abs(rc[i]) / total_rc for i, s in enumerate(strategy_ids)}
    
    def cluster_strategies(self, n_clusters: int = 3) -> Dict[str, int]:
        """
        Cluster strategies based on return correlation.
        
        Uses simple hierarchical clustering based on correlation distance.
        """
        if len(self.strategies) <= 1:
            return {s: 0 for s in self.strategies}
            
        strategy_ids = list(self.strategies.keys())
        n = len(strategy_ids)
        
        # Get correlation matrix
        corr_analysis = self.calculate_correlation_matrix()
        corr = corr_analysis.correlation_matrix
        
        # Convert correlation to distance
        distance = 1 - np.abs(corr)
        
        # Simple agglomerative clustering
        n_clusters = min(n_clusters, n)
        
        # Start with each strategy in its own cluster
        clusters = {i: [i] for i in range(n)}
        
        while len(clusters) > n_clusters:
            # Find closest clusters
            min_dist = float('inf')
            merge_pair = (0, 1)
            
            cluster_ids = list(clusters.keys())
            for i, c1 in enumerate(cluster_ids):
                for c2 in cluster_ids[i + 1:]:
                    # Average linkage
                    dists = [distance[a, b] for a in clusters[c1] for b in clusters[c2]]
                    avg_dist = np.mean(dists)
                    
                    if avg_dist < min_dist:
                        min_dist = avg_dist
                        merge_pair = (c1, c2)
                        
            # Merge clusters
            c1, c2 = merge_pair
            clusters[c1].extend(clusters[c2])
            del clusters[c2]
            
        # Assign cluster labels
        assignments = {}
        for cluster_idx, (_, members) in enumerate(clusters.items()):
            for member_idx in members:
                assignments[strategy_ids[member_idx]] = cluster_idx
                
        return assignments
    
    def generate_recommendations(
        self,
        corr_analysis: CorrelationAnalysis,
        diversification_ratio: float,
        risk_decomposition: Dict[str, float]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Check for high correlations
        if corr_analysis.highly_correlated_pairs:
            for s1, s2, corr in corr_analysis.highly_correlated_pairs:
                recommendations.append(
                    f"Consider reducing allocation to either '{s1}' or '{s2}' "
                    f"(correlation: {corr:.2f}). They may be redundant."
                )
                
        # Check diversification ratio
        if diversification_ratio < 1.2:
            recommendations.append(
                "Low diversification ratio suggests strategies are highly correlated. "
                "Consider adding strategies with different return drivers."
            )
        elif diversification_ratio > 2.0:
            recommendations.append(
                "Excellent diversification ratio. Portfolio benefits significantly from diversification."
            )
            
        # Check risk concentration
        max_risk_contrib = max(risk_decomposition.values()) if risk_decomposition else 0
        if max_risk_contrib > 0.5:
            dominant = max(risk_decomposition, key=risk_decomposition.get)
            recommendations.append(
                f"Strategy '{dominant}' contributes {max_risk_contrib*100:.1f}% of portfolio risk. "
                "Consider reducing its weight or adding offsetting strategies."
            )
            
        # Check for underweighted strategies
        if risk_decomposition:
            min_contrib = min(risk_decomposition.values())
            if min_contrib < 0.05:
                weakest = min(risk_decomposition, key=risk_decomposition.get)
                recommendations.append(
                    f"Strategy '{weakest}' has minimal risk contribution. "
                    "Consider increasing its weight if it provides diversification."
                )
                
        if not recommendations:
            recommendations.append(
                "Portfolio appears well-diversified. No immediate action recommended."
            )
            
        return recommendations
    
    def analyze(
        self,
        weights: Optional[Dict[str, float]] = None
    ) -> DiversificationReport:
        """
        Perform complete diversification analysis.
        
        Args:
            weights: Strategy weights (equal if not provided)
            
        Returns:
            DiversificationReport with all analysis results
        """
        if not self.strategies:
            logger.warning("No strategies to analyze")
            return DiversificationReport(
                timestamp=datetime.now(timezone.utc),
                n_strategies=0,
                diversification_ratio=1.0,
                portfolio_concentration=0.0,
                effective_n_strategies=0.0,
                diversification_level=DiversificationLevel.POOR,
                correlation_analysis=CorrelationAnalysis(
                    correlation_matrix=np.array([]),
                    strategy_ids=[],
                    avg_correlation=0,
                    max_correlation=0,
                    min_correlation=0,
                    highly_correlated_pairs=[]
                ),
                risk_decomposition={},
                recommendations=["No strategies available for analysis"],
                cluster_assignments={}
            )
            
        # Calculate all metrics
        corr_analysis = self.calculate_correlation_matrix()
        div_ratio = self.calculate_diversification_ratio(weights)
        effective_n = self.calculate_effective_n(weights)
        risk_decomp = self.decompose_portfolio_risk(weights)
        clusters = self.cluster_strategies()
        
        # Portfolio concentration (HHI)
        n = len(self.strategies)
        if weights:
            total_w = sum(weights.values())
            concentration = sum((w / total_w) ** 2 for w in weights.values())
        else:
            concentration = 1.0 / n
            
        # Assess diversification level
        if div_ratio < 1.1 or corr_analysis.avg_correlation > 0.7:
            level = DiversificationLevel.POOR
        elif div_ratio < 1.3 or corr_analysis.avg_correlation > 0.5:
            level = DiversificationLevel.MODERATE
        elif div_ratio < 1.6 or corr_analysis.avg_correlation > 0.3:
            level = DiversificationLevel.GOOD
        else:
            level = DiversificationLevel.EXCELLENT
            
        # Generate recommendations
        recommendations = self.generate_recommendations(corr_analysis, div_ratio, risk_decomp)
        
        return DiversificationReport(
            timestamp=datetime.now(timezone.utc),
            n_strategies=n,
            diversification_ratio=div_ratio,
            portfolio_concentration=concentration,
            effective_n_strategies=effective_n,
            diversification_level=level,
            correlation_analysis=corr_analysis,
            risk_decomposition=risk_decomp,
            recommendations=recommendations,
            cluster_assignments=clusters
        )
    
    def suggest_optimal_weights(
        self,
        target: str = "max_sharpe",
        max_weight: float = 0.4,
        min_weight: float = 0.05
    ) -> Dict[str, float]:
        """
        Suggest optimal strategy weights.
        
        Args:
            target: Optimization target ('max_sharpe', 'min_variance', 'equal_risk')
            max_weight: Maximum weight for any strategy
            min_weight: Minimum weight for any strategy
            
        Returns:
            Dict of strategy_id -> suggested weight
        """
        if not self.strategies:
            return {}
            
        strategy_ids = list(self.strategies.keys())
        n = len(strategy_ids)
        
        returns = self._build_returns_matrix()
        if len(returns) == 0:
            return {s: 1.0 / n for s in strategy_ids}
            
        # Calculate expected returns and covariance
        mean_returns = np.array([self.strategies[s].mean_return for s in strategy_ids])
        cov_matrix = np.cov(returns.T)
        if cov_matrix.ndim == 0:
            cov_matrix = np.array([[cov_matrix]])
            
        if target == "equal_risk":
            # Risk parity weights
            vols = np.sqrt(np.diag(cov_matrix))
            inv_vols = 1.0 / vols
            weights = inv_vols / np.sum(inv_vols)
            
        elif target == "min_variance":
            # Minimum variance weights (simple approximation)
            inv_var = 1.0 / np.diag(cov_matrix)
            weights = inv_var / np.sum(inv_var)
            
        else:  # max_sharpe
            # Simple mean-variance optimization (approximation)
            # In practice, would use quadratic optimization
            sharpes = np.array([self.strategies[s].sharpe_ratio for s in strategy_ids])
            weights = np.maximum(sharpes, 0)
            if np.sum(weights) > 0:
                weights = weights / np.sum(weights)
            else:
                weights = np.ones(n) / n
                
        # Apply constraints
        weights = np.clip(weights, min_weight, max_weight)
        weights = weights / np.sum(weights)
        
        return {s: w for s, w in zip(strategy_ids, weights)}


def quick_diversification_check(
    returns_dict: Dict[str, np.ndarray],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Quick utility function for diversification check.
    
    Args:
        returns_dict: Dict of strategy_id -> return series
        weights: Optional weights
        
    Returns:
        Quick summary dict
    """
    analyzer = StrategyDiversificationAnalyzer()
    
    for strat_id, returns in returns_dict.items():
        analyzer.add_strategy(strat_id, returns)
        
    report = analyzer.analyze(weights)
    
    return {
        'diversification_ratio': report.diversification_ratio,
        'level': report.diversification_level.value,
        'avg_correlation': report.correlation_analysis.avg_correlation,
        'effective_n': report.effective_n_strategies,
        'recommendations': report.recommendations[:3]
    }
