"""
Live/Backtest Drift Detection System
QUANT_INDUSTRY_V1

Industry Problem: Strategies that backtest well often underperform live.
Most platforms have NO WAY to detect when live performance deviates from
expected backtest performance. You find out months later after losing money.

Our Solution:
- Statistical comparison of live vs expected returns
- Early warning system for strategy decay
- Automatic alerts when performance drifts
- Root cause analysis (execution, alpha decay, regime change)
- Confidence intervals and significance testing
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
from scipy import stats
import warnings

logger = logging.getLogger(__name__)


class DriftSeverity(Enum):
    """Drift severity levels."""
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class DriftCause(Enum):
    """Potential causes of drift."""
    EXECUTION = "execution"           # Slippage/fill problems
    ALPHA_DECAY = "alpha_decay"       # Signal stopped working
    REGIME_CHANGE = "regime_change"   # Market changed
    DATA_ISSUE = "data_issue"         # Data quality problem
    IMPLEMENTATION = "implementation" # Code bug
    CAPACITY = "capacity"             # Too much capital
    UNKNOWN = "unknown"


@dataclass
class DriftAlert:
    """Alert generated when drift detected."""
    timestamp: datetime
    severity: DriftSeverity
    cause: DriftCause
    message: str
    metrics: Dict[str, float]
    recommended_action: str
    
    def __str__(self) -> str:
        emoji = {
            DriftSeverity.NONE: "[OK]",
            DriftSeverity.MINOR: "⚡",
            DriftSeverity.MODERATE: "[WARN]️",
            DriftSeverity.SEVERE: "🔴",
            DriftSeverity.CRITICAL: "🚨"
        }[self.severity]
        return f"{emoji} [{self.severity.value.upper()}] {self.message}"


@dataclass
class DriftReport:
    """Comprehensive drift analysis report."""
    # Current status
    is_drifting: bool
    severity: DriftSeverity
    confidence: float  # Statistical confidence
    
    # Performance comparison
    expected_return: float  # From backtest
    actual_return: float
    return_gap: float
    return_gap_zscore: float
    
    expected_sharpe: float
    actual_sharpe: float
    sharpe_gap: float
    
    expected_win_rate: float
    actual_win_rate: float
    
    # Time series of gaps
    rolling_gap: pd.Series
    cumulative_gap: pd.Series
    
    # Root cause analysis
    likely_cause: DriftCause
    cause_probabilities: Dict[DriftCause, float]
    
    # Execution analysis
    expected_slippage_bps: float
    actual_slippage_bps: float
    execution_gap: float
    
    # Statistical tests
    t_statistic: float
    p_value: float
    is_significant: bool
    
    # Recommendations
    alerts: List[DriftAlert]
    recommendations: List[str]
    
    def __str__(self) -> str:
        status = "🔴 DRIFTING" if self.is_drifting else "[OK] ON TRACK"
        return f"""
╔═══════════════════════════════════════════════════════════════════╗
║                     DRIFT DETECTION REPORT                        ║
║                    Status: {status:^20}                     ║
╠═══════════════════════════════════════════════════════════════════╣
║                       RETURN COMPARISON                           ║
╠═══════════════════════════════════════════════════════════════════╣
║  Expected Return:  {self.expected_return*100:>7.2f}%    Actual Return:  {self.actual_return*100:>7.2f}%    ║
║  Return Gap:       {self.return_gap*100:>7.2f}%    Z-Score:        {self.return_gap_zscore:>7.2f}     ║
║  Expected Sharpe:  {self.expected_sharpe:>7.2f}     Actual Sharpe:  {self.actual_sharpe:>7.2f}     ║
╠═══════════════════════════════════════════════════════════════════╣
║                       EXECUTION ANALYSIS                          ║
╠═══════════════════════════════════════════════════════════════════╣
║  Expected Slippage: {self.expected_slippage_bps:>5.1f} bps    Actual: {self.actual_slippage_bps:>5.1f} bps         ║
║  Execution Gap:     {self.execution_gap*100:>5.2f}%                                     ║
╠═══════════════════════════════════════════════════════════════════╣
║                       ROOT CAUSE ANALYSIS                         ║
╠═══════════════════════════════════════════════════════════════════╣
║  Most Likely Cause: {self.likely_cause.value:<20}                       ║
║  Confidence:        {self.confidence*100:>5.1f}%    p-value: {self.p_value:.4f}              ║
╚═══════════════════════════════════════════════════════════════════╝
"""


class ExpectedPerformanceModel:
    """
    Model expected performance from backtest results.
    
    Accounts for:
    - Sampling uncertainty in backtest
    - Regime-dependent performance
    - Seasonal patterns
    """
    
    def __init__(
        self,
        backtest_returns: pd.Series,
        regime_labels: Optional[pd.Series] = None
    ):
        self.backtest_returns = backtest_returns
        self.regime_labels = regime_labels
        
        # Calculate expected metrics
        self.expected_return = backtest_returns.mean() * 252
        self.expected_vol = backtest_returns.std() * np.sqrt(252)
        self.expected_sharpe = self.expected_return / self.expected_vol if self.expected_vol > 0 else 0
        self.expected_win_rate = (backtest_returns > 0).mean()
        
        # Calculate confidence intervals
        self._calculate_confidence_intervals()
        
        # Build regime-specific models
        if regime_labels is not None:
            self._build_regime_models()
            
    def _calculate_confidence_intervals(self):
        """Calculate confidence intervals for expected metrics."""
        n = len(self.backtest_returns)
        
        # Return confidence interval
        se_return = self.backtest_returns.std() / np.sqrt(n) * np.sqrt(252)
        self.return_ci_95 = (
            self.expected_return - 1.96 * se_return,
            self.expected_return + 1.96 * se_return
        )
        
        # Sharpe confidence interval (approximate)
        se_sharpe = np.sqrt((1 + 0.5 * self.expected_sharpe**2) / n)
        self.sharpe_ci_95 = (
            self.expected_sharpe - 1.96 * se_sharpe,
            self.expected_sharpe + 1.96 * se_sharpe
        )
        
    def _build_regime_models(self):
        """Build regime-specific expected performance models."""
        self.regime_expectations = {}
        
        for regime in self.regime_labels.unique():
            mask = self.regime_labels == regime
            regime_returns = self.backtest_returns[mask]
            
            self.regime_expectations[regime] = {
                'return': regime_returns.mean() * 252,
                'vol': regime_returns.std() * np.sqrt(252),
                'sharpe': regime_returns.mean() / regime_returns.std() * np.sqrt(252) if regime_returns.std() > 0 else 0,
                'win_rate': (regime_returns > 0).mean()
            }
            
    def get_expected(
        self,
        window_days: int = 21,
        current_regime: Optional[str] = None
    ) -> Dict[str, Tuple[float, float]]:
        """
        Get expected performance with confidence intervals.
        
        Returns dict with (expected, std) for each metric.
        """
        if current_regime and hasattr(self, 'regime_expectations'):
            exp = self.regime_expectations.get(current_regime, {})
            return {
                'return': (exp.get('return', self.expected_return), self.expected_vol / np.sqrt(252/window_days)),
                'sharpe': (exp.get('sharpe', self.expected_sharpe), 0.5),
                'win_rate': (exp.get('win_rate', self.expected_win_rate), 0.1)
            }
        else:
            return {
                'return': (self.expected_return, self.expected_vol / np.sqrt(252/window_days)),
                'sharpe': (self.expected_sharpe, 0.5),
                'win_rate': (self.expected_win_rate, 0.1)
            }


class DriftDetector:
    """
    Detect drift between live and expected performance.
    """
    
    def __init__(
        self,
        expected_model: ExpectedPerformanceModel,
        alert_threshold_zscore: float = 2.0,
        severe_threshold_zscore: float = 3.0,
        min_observations: int = 20
    ):
        self.expected_model = expected_model
        self.alert_threshold = alert_threshold_zscore
        self.severe_threshold = severe_threshold_zscore
        self.min_observations = min_observations
        
        # Track alerts
        self.alerts: List[DriftAlert] = []
        
    def analyze(
        self,
        live_returns: pd.Series,
        live_fills: Optional[pd.DataFrame] = None,  # For execution analysis
        expected_fills: Optional[pd.DataFrame] = None,
        current_regime: Optional[str] = None
    ) -> DriftReport:
        """
        Analyze drift between live and expected performance.
        
        Args:
            live_returns: Live strategy returns
            live_fills: Actual trade fills (price, size, timestamp)
            expected_fills: Expected fills from backtest
            current_regime: Current market regime
            
        Returns:
            DriftReport with analysis
        """
        if len(live_returns) < self.min_observations:
            logger.warning(f"Only {len(live_returns)} observations, need {self.min_observations}")
            
        # Get expected performance
        expected = self.expected_model.get_expected(
            window_days=len(live_returns),
            current_regime=current_regime
        )
        
        # Calculate actual metrics
        actual_return = live_returns.mean() * 252
        actual_vol = live_returns.std() * np.sqrt(252)
        actual_sharpe = actual_return / actual_vol if actual_vol > 0 else 0
        actual_win_rate = (live_returns > 0).mean()
        
        # Calculate gaps
        expected_return, return_std = expected['return']
        return_gap = actual_return - expected_return
        return_gap_zscore = return_gap / return_std if return_std > 0 else 0
        
        expected_sharpe, sharpe_std = expected['sharpe']
        sharpe_gap = actual_sharpe - expected_sharpe
        
        expected_win_rate, win_rate_std = expected['win_rate']
        win_rate_gap = actual_win_rate - expected_win_rate
        
        # Statistical test
        t_stat, p_value = self._significance_test(
            live_returns,
            self.expected_model.backtest_returns
        )
        
        # Calculate rolling gaps
        rolling_gap, cumulative_gap = self._calculate_rolling_gaps(
            live_returns,
            expected_return / 252  # Daily expected
        )
        
        # Execution analysis
        execution_gap = 0.0
        expected_slippage = 5.0  # Default 5 bps
        actual_slippage = 5.0
        
        if live_fills is not None and expected_fills is not None:
            execution_analysis = self._analyze_execution(live_fills, expected_fills)
            expected_slippage = execution_analysis['expected_slippage_bps']
            actual_slippage = execution_analysis['actual_slippage_bps']
            execution_gap = execution_analysis['gap']
            
        # Root cause analysis
        likely_cause, cause_probs = self._root_cause_analysis(
            return_gap_zscore=return_gap_zscore,
            execution_gap=execution_gap,
            sharpe_gap=sharpe_gap,
            win_rate_gap=win_rate_gap,
            live_returns=live_returns
        )
        
        # Determine severity
        severity = self._determine_severity(return_gap_zscore, p_value)
        is_drifting = severity not in [DriftSeverity.NONE, DriftSeverity.MINOR]
        
        # Generate alerts
        alerts = self._generate_alerts(
            severity=severity,
            cause=likely_cause,
            return_gap=return_gap,
            zscore=return_gap_zscore
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            severity=severity,
            cause=likely_cause,
            metrics={
                'return_gap': return_gap,
                'execution_gap': execution_gap,
                'sharpe_gap': sharpe_gap
            }
        )
        
        return DriftReport(
            is_drifting=is_drifting,
            severity=severity,
            confidence=1 - p_value,
            expected_return=expected_return,
            actual_return=actual_return,
            return_gap=return_gap,
            return_gap_zscore=return_gap_zscore,
            expected_sharpe=expected_sharpe,
            actual_sharpe=actual_sharpe,
            sharpe_gap=sharpe_gap,
            expected_win_rate=expected_win_rate,
            actual_win_rate=actual_win_rate,
            rolling_gap=rolling_gap,
            cumulative_gap=cumulative_gap,
            likely_cause=likely_cause,
            cause_probabilities=cause_probs,
            expected_slippage_bps=expected_slippage,
            actual_slippage_bps=actual_slippage,
            execution_gap=execution_gap,
            t_statistic=t_stat,
            p_value=p_value,
            is_significant=p_value < 0.05,
            alerts=alerts,
            recommendations=recommendations
        )
        
    def _significance_test(
        self,
        live_returns: pd.Series,
        backtest_returns: pd.Series
    ) -> Tuple[float, float]:
        """Test if difference is statistically significant."""
        # Welch's t-test (unequal variances)
        t_stat, p_value = stats.ttest_ind(
            live_returns,
            backtest_returns,
            equal_var=False
        )
        return t_stat, p_value
        
    def _calculate_rolling_gaps(
        self,
        live_returns: pd.Series,
        expected_daily: float
    ) -> Tuple[pd.Series, pd.Series]:
        """Calculate rolling and cumulative performance gaps."""
        # Rolling 21-day gap
        rolling_actual = live_returns.rolling(21).mean() * 252
        rolling_expected = expected_daily * 252
        rolling_gap = rolling_actual - rolling_expected
        
        # Cumulative gap
        cumulative_actual = (1 + live_returns).cumprod() - 1
        days = np.arange(1, len(live_returns) + 1)
        cumulative_expected = (1 + expected_daily) ** days - 1
        cumulative_gap = cumulative_actual - cumulative_expected
        
        return rolling_gap, cumulative_gap
        
    def _analyze_execution(
        self,
        live_fills: pd.DataFrame,
        expected_fills: pd.DataFrame
    ) -> Dict[str, float]:
        """Analyze execution quality vs expected."""
        # Expected columns: timestamp, symbol, side, price, quantity
        
        # Calculate slippage (difference from expected price)
        merged = live_fills.merge(
            expected_fills,
            on=['timestamp', 'symbol', 'side'],
            suffixes=('_live', '_expected')
        )
        
        if len(merged) == 0:
            return {
                'expected_slippage_bps': 5.0,
                'actual_slippage_bps': 5.0,
                'gap': 0.0
            }
            
        # Calculate per-trade slippage
        merged['slippage_bps'] = (
            (merged['price_live'] - merged['price_expected']) / 
            merged['price_expected'] * 10000
        )
        
        # Adjust sign for sells
        merged.loc[merged['side'] == 'sell', 'slippage_bps'] *= -1
        
        actual_slippage = merged['slippage_bps'].mean()
        expected_slippage = 5.0  # Base expectation
        
        gap = (actual_slippage - expected_slippage) / 10000  # Convert to decimal
        
        return {
            'expected_slippage_bps': expected_slippage,
            'actual_slippage_bps': actual_slippage,
            'gap': gap
        }
        
    def _root_cause_analysis(
        self,
        return_gap_zscore: float,
        execution_gap: float,
        sharpe_gap: float,
        win_rate_gap: float,
        live_returns: pd.Series
    ) -> Tuple[DriftCause, Dict[DriftCause, float]]:
        """Analyze root cause of drift."""
        probs = {cause: 0.1 for cause in DriftCause}  # Prior
        
        # Execution problems: high execution gap
        if abs(execution_gap) > 0.005:  # >50 bps
            probs[DriftCause.EXECUTION] += 0.4
            
        # Alpha decay: gradual decline
        if len(live_returns) > 20:
            trend = np.polyfit(range(len(live_returns)), live_returns.values, 1)[0]
            if trend < -0.0001:  # Declining
                probs[DriftCause.ALPHA_DECAY] += 0.3
                
        # Regime change: sudden shift
        if len(live_returns) > 10:
            recent_vol = live_returns[-10:].std()
            overall_vol = live_returns.std()
            if recent_vol > overall_vol * 1.5:
                probs[DriftCause.REGIME_CHANGE] += 0.3
                
        # Win rate collapse might indicate alpha decay
        if win_rate_gap < -0.1:  # 10% lower
            probs[DriftCause.ALPHA_DECAY] += 0.2
            
        # Normalize
        total = sum(probs.values())
        probs = {k: v/total for k, v in probs.items()}
        
        # Most likely cause
        likely_cause = max(probs, key=probs.get)
        
        return likely_cause, probs
        
    def _determine_severity(
        self,
        zscore: float,
        p_value: float
    ) -> DriftSeverity:
        """Determine drift severity."""
        abs_zscore = abs(zscore)
        
        if abs_zscore < 1.0:
            return DriftSeverity.NONE
        elif abs_zscore < self.alert_threshold:
            return DriftSeverity.MINOR
        elif abs_zscore < self.severe_threshold:
            return DriftSeverity.MODERATE
        elif abs_zscore < 4.0:
            return DriftSeverity.SEVERE
        else:
            return DriftSeverity.CRITICAL
            
    def _generate_alerts(
        self,
        severity: DriftSeverity,
        cause: DriftCause,
        return_gap: float,
        zscore: float
    ) -> List[DriftAlert]:
        """Generate alerts based on analysis."""
        alerts = []
        
        if severity == DriftSeverity.NONE:
            return alerts
            
        direction = "underperforming" if return_gap < 0 else "overperforming"
        
        alert = DriftAlert(
            timestamp=datetime.now(),
            severity=severity,
            cause=cause,
            message=f"Strategy {direction} by {abs(return_gap)*100:.1f}% (z={zscore:.1f})",
            metrics={'return_gap': return_gap, 'zscore': zscore},
            recommended_action=self._get_recommended_action(severity, cause)
        )
        alerts.append(alert)
        
        self.alerts.append(alert)  # Track
        return alerts
        
    def _get_recommended_action(
        self,
        severity: DriftSeverity,
        cause: DriftCause
    ) -> str:
        """Get recommended action for alert."""
        if severity == DriftSeverity.CRITICAL:
            return "IMMEDIATE: Consider halting strategy and investigating"
            
        if cause == DriftCause.EXECUTION:
            return "Review execution logs and broker fills"
        elif cause == DriftCause.ALPHA_DECAY:
            return "Analyze signal efficacy and consider reducing position"
        elif cause == DriftCause.REGIME_CHANGE:
            return "Check market regime and strategy assumptions"
        elif cause == DriftCause.CAPACITY:
            return "Reduce position size to lower market impact"
        else:
            return "Monitor closely and investigate data sources"
            
    def _generate_recommendations(
        self,
        severity: DriftSeverity,
        cause: DriftCause,
        metrics: Dict[str, float]
    ) -> List[str]:
        """Generate recommendations."""
        recs = []
        
        if severity in [DriftSeverity.NONE, DriftSeverity.MINOR]:
            recs.append("[OK] Performance within expected range. Continue monitoring.")
            return recs
            
        if cause == DriftCause.EXECUTION:
            recs.append("[FIX] Check broker execution quality")
            recs.append("[FIX] Review order routing and timing")
            recs.append("[FIX] Consider switching to limit orders or better execution algos")
            
        elif cause == DriftCause.ALPHA_DECAY:
            recs.append("[DOWN] Signal may be decaying - reduce position size")
            recs.append("[DOWN] Analyze if competitors discovered same signal")
            recs.append("[DOWN] Consider refreshing or retiring strategy")
            
        elif cause == DriftCause.REGIME_CHANGE:
            recs.append("🌊 Market regime may have changed")
            recs.append("🌊 Review strategy assumptions for current environment")
            recs.append("🌊 Consider regime-specific adjustments")
            
        elif cause == DriftCause.CAPACITY:
            recs.append("[CHART] Strategy may be hitting capacity constraints")
            recs.append("[CHART] Reduce AUM or improve execution")
            
        if severity in [DriftSeverity.SEVERE, DriftSeverity.CRITICAL]:
            recs.append("🚨 Consider reducing or halting strategy")
            recs.append("🚨 Perform full diagnostic before resuming")
            
        return recs


class AlphaDecayMonitor:
    """
    Monitor for gradual alpha decay.
    
    Strategies don't fail suddenly - they slowly stop working.
    This monitors for that gradual decay.
    """
    
    def __init__(
        self,
        baseline_sharpe: float,
        decay_threshold: float = 0.5,  # Alert when Sharpe drops to 50% of baseline
        rolling_window: int = 63  # ~3 months
    ):
        self.baseline_sharpe = baseline_sharpe
        self.decay_threshold = decay_threshold
        self.rolling_window = rolling_window
        
        self.sharpe_history: List[float] = []
        self.decay_alerts: List[DriftAlert] = []
        
    def update(self, returns: pd.Series) -> Optional[DriftAlert]:
        """
        Update with new returns and check for decay.
        
        Returns alert if decay detected.
        """
        if len(returns) < self.rolling_window:
            return None
            
        # Calculate rolling Sharpe
        rolling_sharpe = (
            returns.rolling(self.rolling_window).mean() / 
            returns.rolling(self.rolling_window).std() * 
            np.sqrt(252)
        ).iloc[-1]
        
        self.sharpe_history.append(rolling_sharpe)
        
        # Check for decay
        current_ratio = rolling_sharpe / self.baseline_sharpe if self.baseline_sharpe != 0 else 0
        
        if current_ratio < self.decay_threshold:
            alert = DriftAlert(
                timestamp=datetime.now(),
                severity=DriftSeverity.SEVERE,
                cause=DriftCause.ALPHA_DECAY,
                message=f"Alpha decay: Sharpe at {current_ratio*100:.0f}% of baseline",
                metrics={
                    'current_sharpe': rolling_sharpe,
                    'baseline_sharpe': self.baseline_sharpe,
                    'ratio': current_ratio
                },
                recommended_action="Review strategy performance and consider reducing exposure"
            )
            self.decay_alerts.append(alert)
            return alert
            
        return None
        
    def get_trend(self) -> Dict[str, Any]:
        """Get decay trend analysis."""
        if len(self.sharpe_history) < 10:
            return {'trend': 'insufficient_data'}
            
        # Fit linear trend
        x = np.arange(len(self.sharpe_history))
        slope, intercept = np.polyfit(x, self.sharpe_history, 1)
        
        # Project time to decay threshold
        threshold_sharpe = self.baseline_sharpe * self.decay_threshold
        if slope < 0:
            current_sharpe = self.sharpe_history[-1]
            if current_sharpe > threshold_sharpe:
                periods_to_threshold = (current_sharpe - threshold_sharpe) / abs(slope)
            else:
                periods_to_threshold = 0
        else:
            periods_to_threshold = float('inf')
            
        return {
            'trend': 'declining' if slope < 0 else 'stable',
            'slope': slope,
            'current_sharpe': self.sharpe_history[-1] if self.sharpe_history else 0,
            'periods_to_threshold': periods_to_threshold,
            'decay_rate_per_month': slope * 21 if slope < 0 else 0
        }
