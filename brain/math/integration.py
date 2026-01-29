"""
Math Integration Layer
======================
Bridges mathematical primitives to TradingBrain for real-time decisions.

This module:
1. Wraps HMM regime detection with financial interpretation
2. Provides regime-aware position sizing (Kelly + adjustments)
3. Computes risk parameters that adapt to market conditions
"""

import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from .markov import HiddenMarkovModel, MarkovRegimeDetector, BellmanOperator
from .portfolio import KellyCriterion, RiskParity, CVaROptimizer
from .losses import TradingRewardFunction

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""
    CRISIS = "CRISIS"           # High vol, sharp drawdowns
    BEAR_STRONG = "BEAR_STRONG" # Sustained downtrend
    BEAR_WEAK = "BEAR_WEAK"     # Choppy downtrend
    NEUTRAL = "NEUTRAL"         # Low conviction either way
    BULL_WEAK = "BULL_WEAK"     # Choppy uptrend
    BULL_STRONG = "BULL_STRONG" # Sustained uptrend
    EUPHORIA = "EUPHORIA"       # Extreme bullish (caution)


@dataclass
class RegimeState:
    """Current regime state with probabilities."""
    regime: MarketRegime
    confidence: float
    probabilities: Dict[str, float]
    volatility_regime: str  # low, normal, high, extreme
    trend_strength: float   # -1 to 1
    
    # Regime characteristics
    expected_return: float
    expected_volatility: float
    regime_duration: int  # How long in this regime (bars)
    
    # Risk adjustments
    position_scalar: float  # Multiply position sizes by this
    stop_multiplier: float  # Widen/tighten stops
    profit_multiplier: float  # Adjust profit targets


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    base_kelly: float       # Raw Kelly fraction
    adjusted_kelly: float   # After regime adjustment
    final_size: float       # Final position size (% of capital)
    
    # Components
    win_rate: float
    avg_win: float
    avg_loss: float
    edge: float  # Expected value per trade
    
    # Risk metrics
    max_position: float  # Hard cap
    regime_adjustment: float  # Multiplier applied
    confidence_adjustment: float  # Based on signal confidence


class IntegratedRegimeDetector:
    """
    Production regime detector using HMM + additional signals.
    
    Combines:
    - HMM-based regime probabilities
    - Volatility regime classification
    - Trend analysis
    - Change point detection
    """
    
    def __init__(
        self,
        n_regimes: int = 4,
        lookback: int = 252,
        vol_window: int = 20
    ):
        self.n_regimes = n_regimes
        self.lookback = lookback
        self.vol_window = vol_window
        
        # Initialize HMM
        self.hmm = HiddenMarkovModel(
            n_states=n_regimes,
            n_features=3  # returns, vol, trend
        )
        
        self.is_fitted = False
        self.regime_history: List[MarketRegime] = []
        self.current_regime_duration = 0
        
        # Regime mappings (set after fitting)
        self.state_to_regime: Dict[int, MarketRegime] = {}
    
    def _extract_features(self, prices: np.ndarray) -> np.ndarray:
        """Extract regime-relevant features."""
        if len(prices) < self.vol_window + 1:
            raise ValueError(f"Need at least {self.vol_window + 1} prices")
        
        # Returns
        returns = np.diff(np.log(prices))
        
        # Realized volatility (rolling)
        vol = np.array([
            returns[max(0, i - self.vol_window):i].std() * np.sqrt(252)
            if i > 0 else 0.15
            for i in range(len(returns))
        ])
        
        # Trend (rolling mean return, annualized)
        trend = np.array([
            returns[max(0, i - self.vol_window):i].mean() * 252
            if i > 0 else 0
            for i in range(len(returns))
        ])
        
        return np.column_stack([returns, vol, trend])
    
    def fit(self, prices: np.ndarray, n_iter: int = 100) -> 'IntegratedRegimeDetector':
        """Fit HMM to historical price data."""
        features = self._extract_features(prices)
        
        # Fit HMM
        self.hmm.fit(features, n_iter=n_iter)
        
        # Classify states by mean return
        mean_returns = self.hmm.means[:, 0]
        mean_vols = self.hmm.means[:, 1]
        
        # Sort by return to assign regimes
        order = np.argsort(mean_returns)
        
        if self.n_regimes == 4:
            self.state_to_regime = {
                order[0]: MarketRegime.BEAR_STRONG,
                order[1]: MarketRegime.BEAR_WEAK,
                order[2]: MarketRegime.BULL_WEAK,
                order[3]: MarketRegime.BULL_STRONG
            }
        elif self.n_regimes == 3:
            self.state_to_regime = {
                order[0]: MarketRegime.BEAR_STRONG,
                order[1]: MarketRegime.NEUTRAL,
                order[2]: MarketRegime.BULL_STRONG
            }
        else:
            # Generic mapping
            for i, idx in enumerate(order):
                if i < len(order) // 2:
                    self.state_to_regime[idx] = MarketRegime.BEAR_WEAK
                else:
                    self.state_to_regime[idx] = MarketRegime.BULL_WEAK
        
        self.is_fitted = True
        logger.info(f"Regime detector fitted with {self.n_regimes} states")
        
        return self
    
    def detect(self, prices: np.ndarray) -> RegimeState:
        """
        Detect current market regime.
        
        Returns RegimeState with full analysis.
        """
        if not self.is_fitted:
            # Return neutral state if not fitted
            return self._default_state()
        
        try:
            features = self._extract_features(prices)
            
            # Get HMM predictions
            state_probs = self.hmm.predict_proba(features)
            current_probs = state_probs[-1]
            current_state = np.argmax(current_probs)
            
            regime = self.state_to_regime.get(current_state, MarketRegime.NEUTRAL)
            confidence = float(current_probs[current_state])
            
            # Track regime duration
            if self.regime_history and self.regime_history[-1] == regime:
                self.current_regime_duration += 1
            else:
                self.current_regime_duration = 1
            self.regime_history.append(regime)
            
            # Volatility classification
            current_vol = features[-1, 1]
            vol_regime = self._classify_volatility(current_vol)
            
            # Trend strength
            trend_strength = float(np.clip(features[-1, 2] / 0.3, -1, 1))
            
            # Get regime characteristics from HMM parameters
            expected_return = float(self.hmm.means[current_state, 0] * 252)
            expected_vol = float(self.hmm.means[current_state, 1])
            
            # Calculate risk adjustments
            position_scalar, stop_mult, profit_mult = self._get_risk_adjustments(
                regime, confidence, vol_regime
            )
            
            # Check for extreme conditions
            regime = self._check_extreme_conditions(
                regime, current_vol, trend_strength, confidence
            )
            
            return RegimeState(
                regime=regime,
                confidence=confidence,
                probabilities={
                    self.state_to_regime.get(i, MarketRegime.NEUTRAL).value: float(p)
                    for i, p in enumerate(current_probs)
                },
                volatility_regime=vol_regime,
                trend_strength=trend_strength,
                expected_return=expected_return,
                expected_volatility=expected_vol,
                regime_duration=self.current_regime_duration,
                position_scalar=position_scalar,
                stop_multiplier=stop_mult,
                profit_multiplier=profit_mult
            )
            
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
            return self._default_state()
    
    def _classify_volatility(self, vol: float) -> str:
        """Classify volatility regime."""
        if vol < 0.10:
            return "low"
        elif vol < 0.20:
            return "normal"
        elif vol < 0.35:
            return "high"
        else:
            return "extreme"
    
    def _get_risk_adjustments(
        self,
        regime: MarketRegime,
        confidence: float,
        vol_regime: str
    ) -> Tuple[float, float, float]:
        """
        Calculate risk adjustments based on regime.
        
        Returns: (position_scalar, stop_multiplier, profit_multiplier)
        """
        # Base adjustments by regime
        regime_adjustments = {
            MarketRegime.CRISIS: (0.25, 2.0, 0.5),     # Small positions, wide stops
            MarketRegime.BEAR_STRONG: (0.5, 1.5, 0.75),
            MarketRegime.BEAR_WEAK: (0.75, 1.25, 1.0),
            MarketRegime.NEUTRAL: (0.75, 1.0, 1.0),
            MarketRegime.BULL_WEAK: (1.0, 1.0, 1.0),
            MarketRegime.BULL_STRONG: (1.25, 0.9, 1.25),  # Larger positions, tighter stops
            MarketRegime.EUPHORIA: (0.5, 1.5, 0.5),    # Caution in euphoria
        }
        
        pos_scalar, stop_mult, profit_mult = regime_adjustments.get(
            regime, (1.0, 1.0, 1.0)
        )
        
        # Adjust for volatility
        vol_adjustment = {
            "low": 1.2,
            "normal": 1.0,
            "high": 0.7,
            "extreme": 0.4
        }
        pos_scalar *= vol_adjustment.get(vol_regime, 1.0)
        
        # Adjust for confidence
        if confidence < 0.5:
            pos_scalar *= 0.7
        elif confidence > 0.8:
            pos_scalar *= 1.1
        
        return pos_scalar, stop_mult, profit_mult
    
    def _check_extreme_conditions(
        self,
        regime: MarketRegime,
        vol: float,
        trend: float,
        confidence: float
    ) -> MarketRegime:
        """Check for extreme conditions that override base regime."""
        # Crisis detection: very high vol + negative trend
        if vol > 0.40 and trend < -0.3:
            return MarketRegime.CRISIS
        
        # Euphoria detection: low vol + very strong uptrend
        if vol < 0.12 and trend > 0.4 and regime == MarketRegime.BULL_STRONG:
            return MarketRegime.EUPHORIA
        
        return regime
    
    def _default_state(self) -> RegimeState:
        """Return conservative default state."""
        return RegimeState(
            regime=MarketRegime.NEUTRAL,
            confidence=0.5,
            probabilities={"NEUTRAL": 1.0},
            volatility_regime="normal",
            trend_strength=0.0,
            expected_return=0.0,
            expected_volatility=0.20,
            regime_duration=0,
            position_scalar=0.5,  # Conservative
            stop_multiplier=1.5,
            profit_multiplier=1.0
        )


class IntegratedPositionSizer:
    """
    Position sizing using Kelly criterion with regime adjustments.
    
    Combines:
    - Kelly criterion for optimal sizing
    - Regime-based adjustments
    - Confidence scaling
    - Hard risk limits
    """
    
    def __init__(
        self,
        max_position: float = 0.10,      # Max 10% of capital per position
        kelly_fraction: float = 0.25,     # Use 1/4 Kelly (conservative)
        min_trades_for_kelly: int = 30,   # Need history for Kelly
    ):
        self.max_position = max_position
        self.kelly_fraction = kelly_fraction
        self.min_trades = min_trades_for_kelly
        
        # Track trade history for Kelly calculation
        self.trade_history: List[Dict] = []
    
    def add_trade(self, pnl: float, is_win: bool):
        """Record a trade for Kelly calculation."""
        self.trade_history.append({
            'pnl': pnl,
            'is_win': is_win
        })
        
        # Keep last 100 trades
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]
    
    def calculate(
        self,
        signal_confidence: float,
        regime_state: RegimeState,
        current_volatility: float,
        account_equity: float,
        risk_per_trade: float = 0.02  # Default 2% risk
    ) -> PositionSizeResult:
        """
        Calculate position size.
        
        Args:
            signal_confidence: How confident is the signal (0-1)
            regime_state: Current market regime
            current_volatility: Asset volatility (annualized)
            account_equity: Account value
            risk_per_trade: Max risk per trade as fraction
        """
        # Calculate Kelly if we have enough history
        if len(self.trade_history) >= self.min_trades:
            win_rate, avg_win, avg_loss, base_kelly = self._calculate_kelly()
        else:
            # Use heuristic before we have history
            win_rate = 0.5
            avg_win = 0.015  # 1.5% average win
            avg_loss = 0.01  # 1% average loss
            base_kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        
        edge = win_rate * avg_win - (1 - win_rate) * avg_loss
        
        # Apply fractional Kelly
        adjusted_kelly = base_kelly * self.kelly_fraction
        
        # Regime adjustment
        regime_adjustment = regime_state.position_scalar
        adjusted_kelly *= regime_adjustment
        
        # Confidence adjustment (scale with sqrt for less aggressive scaling)
        confidence_adjustment = np.sqrt(signal_confidence)
        adjusted_kelly *= confidence_adjustment
        
        # Volatility adjustment (reduce in high vol)
        vol_adjustment = min(1.0, 0.20 / max(current_volatility, 0.05))
        adjusted_kelly *= vol_adjustment
        
        # Apply hard limits
        final_size = min(
            max(adjusted_kelly, 0),  # No negative positions
            self.max_position,        # Max position limit
            risk_per_trade / max(current_volatility, 0.01)  # Vol-based limit
        )
        
        return PositionSizeResult(
            base_kelly=base_kelly,
            adjusted_kelly=adjusted_kelly,
            final_size=final_size,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            edge=edge,
            max_position=self.max_position,
            regime_adjustment=regime_adjustment,
            confidence_adjustment=confidence_adjustment
        )
    
    def _calculate_kelly(self) -> Tuple[float, float, float, float]:
        """Calculate Kelly parameters from trade history."""
        wins = [t for t in self.trade_history if t['is_win']]
        losses = [t for t in self.trade_history if not t['is_win']]
        
        win_rate = len(wins) / len(self.trade_history)
        
        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0.01
        avg_loss = abs(np.mean([t['pnl'] for t in losses])) if losses else 0.01
        
        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = 1-p, b = avg_win / avg_loss
        if avg_loss > 0:
            b = avg_win / avg_loss  # Win/loss ratio
            kelly = (win_rate * b - (1 - win_rate)) / b
        else:
            kelly = 0
        
        return win_rate, avg_win, avg_loss, kelly


class RiskManager:
    """
    Integrated risk management using regime-aware parameters.
    
    Handles:
    - Position-level risk
    - Portfolio-level risk
    - Drawdown management
    - Exposure limits
    """
    
    def __init__(
        self,
        max_portfolio_risk: float = 0.20,     # Max 20% portfolio at risk
        max_sector_exposure: float = 0.30,    # Max 30% in one sector
        max_correlation_exposure: float = 0.40,  # Max correlated exposure
        drawdown_threshold: float = 0.10,     # Start reducing at 10% DD
        critical_drawdown: float = 0.20       # Stop trading at 20% DD
    ):
        self.max_portfolio_risk = max_portfolio_risk
        self.max_sector_exposure = max_sector_exposure
        self.max_correlation_exposure = max_correlation_exposure
        self.drawdown_threshold = drawdown_threshold
        self.critical_drawdown = critical_drawdown
        
        self.peak_equity = 0
        self.current_equity = 0
    
    def update_equity(self, equity: float):
        """Update equity tracking."""
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity
    
    @property
    def current_drawdown(self) -> float:
        """Current drawdown from peak."""
        if self.peak_equity <= 0:
            return 0
        return (self.peak_equity - self.current_equity) / self.peak_equity
    
    def get_risk_multiplier(self, regime_state: RegimeState) -> float:
        """
        Get risk multiplier based on drawdown and regime.
        
        Returns value between 0 (stop trading) and 1 (full risk).
        """
        dd = self.current_drawdown
        
        # Drawdown-based reduction
        if dd >= self.critical_drawdown:
            dd_multiplier = 0.0  # Stop trading
        elif dd >= self.drawdown_threshold:
            # Linear reduction
            dd_multiplier = 1.0 - (dd - self.drawdown_threshold) / (
                self.critical_drawdown - self.drawdown_threshold
            )
        else:
            dd_multiplier = 1.0
        
        # Regime adjustment
        regime_multiplier = regime_state.position_scalar
        
        return dd_multiplier * regime_multiplier
    
    def check_position_risk(
        self,
        position_size: float,
        stop_distance: float,
        current_positions: Dict[str, float],
        sector: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if a new position passes risk checks.
        
        Returns: (is_allowed, reason)
        """
        # Portfolio risk check
        total_risk = sum(abs(p) for p in current_positions.values())
        new_total = total_risk + position_size * stop_distance
        
        if new_total > self.max_portfolio_risk:
            return False, f"Portfolio risk exceeded: {new_total:.1%} > {self.max_portfolio_risk:.1%}"
        
        # Drawdown check
        if self.current_drawdown >= self.critical_drawdown:
            return False, f"Critical drawdown: {self.current_drawdown:.1%}"
        
        return True, "OK"


# Factory functions for easy instantiation

def create_regime_detector(
    prices: Optional[np.ndarray] = None,
    n_regimes: int = 4
) -> IntegratedRegimeDetector:
    """Create and optionally fit a regime detector."""
    detector = IntegratedRegimeDetector(n_regimes=n_regimes)
    
    if prices is not None and len(prices) > 50:
        detector.fit(prices)
    
    return detector


def create_position_sizer(
    max_position: float = 0.10,
    kelly_fraction: float = 0.25
) -> IntegratedPositionSizer:
    """Create a position sizer."""
    return IntegratedPositionSizer(
        max_position=max_position,
        kelly_fraction=kelly_fraction
    )


def create_risk_manager(
    drawdown_threshold: float = 0.10,
    critical_drawdown: float = 0.20
) -> RiskManager:
    """Create a risk manager."""
    return RiskManager(
        drawdown_threshold=drawdown_threshold,
        critical_drawdown=critical_drawdown
    )


# =============================================================================
# PHASE 2: ALPHA GENERATION & EXECUTION
# =============================================================================

from .factors import CAPM, FamaFrench, AlphaModel
from .microstructure import KyleModel, AlmgrenChriss


@dataclass
class AlphaSignal:
    """Combined alpha signal with factor attribution."""
    composite_alpha: float  # -1 to 1
    confidence: float
    
    # Factor contributions
    momentum_alpha: float
    mean_reversion_alpha: float
    trend_alpha: float
    
    # CAPM metrics (if available)
    beta: Optional[float] = None
    capm_alpha: Optional[float] = None
    
    # Signal metadata
    signal_strength: str = "weak"  # weak, moderate, strong
    primary_driver: str = "mixed"


@dataclass  
class ExecutionPlan:
    """Optimal execution plan with impact estimates."""
    strategy: str  # "immediate", "twap", "vwap", "optimal"
    urgency: str   # "low", "medium", "high"
    
    # Trajectory (for multi-period execution)
    n_periods: int
    trajectory: List[float]  # Remaining shares after each period
    
    # Cost estimates
    estimated_impact_pct: float
    estimated_cost_bps: float
    
    # Kyle lambda (if estimated)
    kyle_lambda: Optional[float] = None
    
    # Recommendations
    slice_size_pct: float = 10.0  # % of order per slice
    time_between_slices: int = 60  # seconds


class IntegratedAlphaGenerator:
    """
    Generates alpha signals from price data using multiple factors.
    
    Combines:
    - Momentum (trend-following)
    - Mean reversion (contrarian)
    - CAPM alpha (vs market)
    - Technical factors
    """
    
    def __init__(
        self,
        momentum_lookback: int = 20,
        mean_reversion_lookback: int = 5,
        trend_lookback: int = 50
    ):
        self.momentum_lookback = momentum_lookback
        self.mean_reversion_lookback = mean_reversion_lookback
        self.trend_lookback = trend_lookback
        
        self.alpha_model = AlphaModel(lookback=momentum_lookback)
    
    def generate(
        self,
        prices: np.ndarray,
        market_prices: Optional[np.ndarray] = None
    ) -> AlphaSignal:
        """
        Generate composite alpha signal.
        
        Args:
            prices: Asset price series
            market_prices: Market (SPY/benchmark) prices for CAPM
        """
        if len(prices) < self.trend_lookback:
            return self._default_signal()
        
        returns = np.diff(np.log(prices))
        
        # 1. Momentum alpha (trend-following)
        momentum = self._momentum_signal(returns)
        
        # 2. Mean reversion alpha (contrarian)
        mean_rev = self._mean_reversion_signal(prices)
        
        # 3. Trend alpha (long-term direction)
        trend = self._trend_signal(prices)
        
        # 4. CAPM alpha (if market data available)
        beta = None
        capm_alpha = None
        if market_prices is not None and len(market_prices) == len(prices):
            market_returns = np.diff(np.log(market_prices))
            try:
                capm = CAPM(returns, market_returns)
                beta = capm.beta
                capm_alpha = capm.alpha * 252  # Annualized
            except Exception:
                pass
        
        # Combine signals
        self.alpha_model.signals = {}
        self.alpha_model.weights = {}
        
        self.alpha_model.add_signal("momentum", np.array([momentum]), weight=0.35)
        self.alpha_model.add_signal("mean_reversion", np.array([mean_rev]), weight=0.25)
        self.alpha_model.add_signal("trend", np.array([trend]), weight=0.40)
        
        # Composite
        composite = (
            0.35 * momentum +
            0.25 * mean_rev +
            0.40 * trend
        )
        composite = np.clip(composite, -1, 1)
        
        # Confidence based on signal agreement
        signals = [momentum, mean_rev, trend]
        signal_std = np.std(signals)
        confidence = max(0.3, 1 - signal_std)  # Lower std = higher confidence
        
        # Signal strength
        abs_alpha = abs(composite)
        if abs_alpha > 0.6:
            strength = "strong"
        elif abs_alpha > 0.3:
            strength = "moderate"
        else:
            strength = "weak"
        
        # Primary driver
        abs_signals = [abs(momentum), abs(mean_rev), abs(trend)]
        drivers = ["momentum", "mean_reversion", "trend"]
        primary = drivers[np.argmax(abs_signals)]
        
        return AlphaSignal(
            composite_alpha=composite,
            confidence=confidence,
            momentum_alpha=momentum,
            mean_reversion_alpha=mean_rev,
            trend_alpha=trend,
            beta=beta,
            capm_alpha=capm_alpha,
            signal_strength=strength,
            primary_driver=primary
        )
    
    def _momentum_signal(self, returns: np.ndarray) -> float:
        """Momentum: recent return relative to history."""
        if len(returns) < self.momentum_lookback:
            return 0.0
        
        recent = returns[-self.momentum_lookback:]
        cumulative_return = np.exp(recent.sum()) - 1
        
        # Normalize to -1, 1
        # Assume >10% monthly return is extreme
        return np.clip(cumulative_return / 0.10, -1, 1)
    
    def _mean_reversion_signal(self, prices: np.ndarray) -> float:
        """Mean reversion: deviation from recent average."""
        if len(prices) < self.mean_reversion_lookback * 2:
            return 0.0
        
        current = prices[-1]
        recent_avg = np.mean(prices[-self.mean_reversion_lookback:])
        longer_avg = np.mean(prices[-self.mean_reversion_lookback * 4:])
        
        # How far from mean (negative = sell, positive = buy back)
        deviation = (recent_avg - current) / longer_avg
        
        return np.clip(deviation * 10, -1, 1)  # Scale
    
    def _trend_signal(self, prices: np.ndarray) -> float:
        """Trend: slope of price over lookback period."""
        if len(prices) < self.trend_lookback:
            return 0.0
        
        recent_prices = prices[-self.trend_lookback:]
        x = np.arange(len(recent_prices))
        
        # Linear regression slope
        slope = np.polyfit(x, recent_prices, 1)[0]
        
        # Normalize by average price
        avg_price = np.mean(recent_prices)
        trend_pct = slope / avg_price * self.trend_lookback
        
        return np.clip(trend_pct * 10, -1, 1)
    
    def _default_signal(self) -> AlphaSignal:
        """Return neutral signal when data insufficient."""
        return AlphaSignal(
            composite_alpha=0.0,
            confidence=0.3,
            momentum_alpha=0.0,
            mean_reversion_alpha=0.0,
            trend_alpha=0.0,
            signal_strength="weak",
            primary_driver="insufficient_data"
        )


class IntegratedExecutionOptimizer:
    """
    Execution optimization using Almgren-Chriss and Kyle models.
    
    Determines:
    - Order slicing strategy
    - Expected market impact
    - Optimal execution trajectory
    """
    
    def __init__(
        self,
        default_volatility: float = 0.20,
        default_eta: float = 0.01,      # Temporary impact
        default_gamma: float = 0.001    # Permanent impact
    ):
        self.default_vol = default_volatility
        self.default_eta = default_eta
        self.default_gamma = default_gamma
        
        self.kyle_model = KyleModel()
        self.kyle_lambda = None
    
    def estimate_impact(
        self,
        order_size: float,
        avg_daily_volume: float,
        volatility: float,
        price: float
    ) -> float:
        """
        Estimate market impact as percentage.
        
        Uses square-root impact model:
        Impact = k * sigma * sqrt(Q / ADV)
        
        Where k ~ 0.5 for liquid stocks.
        """
        if avg_daily_volume <= 0:
            return 0.05  # 5 bps default
        
        # Participation rate
        participation = order_size / avg_daily_volume
        
        # Square-root model
        k = 0.5
        impact = k * volatility * np.sqrt(participation)
        
        # Apply Kyle lambda if estimated
        if self.kyle_lambda is not None:
            impact *= (1 + self.kyle_lambda)
        
        return impact
    
    def calibrate_kyle(
        self,
        price_changes: np.ndarray,
        order_flow: np.ndarray
    ):
        """Calibrate Kyle's lambda from historical data."""
        try:
            self.kyle_lambda = self.kyle_model.estimate(price_changes, order_flow)
            logger.info(f"Kyle lambda calibrated: {self.kyle_lambda:.6f}")
        except Exception as e:
            logger.warning(f"Kyle calibration failed: {e}")
    
    def plan_execution(
        self,
        shares: float,
        price: float,
        avg_daily_volume: float,
        volatility: float,
        urgency: str = "medium",
        risk_aversion: float = 1.0
    ) -> ExecutionPlan:
        """
        Create optimal execution plan.
        
        Args:
            shares: Number of shares to execute
            price: Current price
            avg_daily_volume: Average daily volume
            volatility: Annualized volatility
            urgency: "low", "medium", "high"
            risk_aversion: Risk aversion parameter for Almgren-Chriss
        """
        dollar_value = shares * price
        participation = shares / max(avg_daily_volume, 1)
        
        # Determine strategy based on order size
        if participation < 0.01:
            # Small order: execute immediately
            return ExecutionPlan(
                strategy="immediate",
                urgency=urgency,
                n_periods=1,
                trajectory=[shares, 0],
                estimated_impact_pct=self.estimate_impact(
                    shares, avg_daily_volume, volatility, price
                ),
                estimated_cost_bps=5,
                slice_size_pct=100.0,
                time_between_slices=0
            )
        
        # Larger orders: use Almgren-Chriss
        if urgency == "high":
            n_periods = 5
            risk_aversion *= 2
        elif urgency == "low":
            n_periods = 20
            risk_aversion *= 0.5
        else:
            n_periods = 10
        
        # Create Almgren-Chriss model
        ac = AlmgrenChriss(
            total_shares=shares,
            time_periods=n_periods,
            volatility=volatility / np.sqrt(252),  # Daily vol
            eta=self.default_eta,
            gamma=self.default_gamma
        )
        
        # Optimal trajectory
        trajectory = ac.optimal_trajectory(risk_aversion)
        
        # Cost estimates
        costs = ac.execution_cost(trajectory)
        total_cost_pct = costs['total'] / (shares * price)
        cost_bps = total_cost_pct * 10000
        
        # Impact estimate
        impact_pct = self.estimate_impact(shares, avg_daily_volume, volatility, price)
        
        # Slice size
        avg_trade = shares / n_periods
        slice_pct = (avg_trade / shares) * 100
        
        # Time between (assume 6.5 hour trading day)
        minutes_per_period = int(390 / n_periods)
        
        return ExecutionPlan(
            strategy="optimal" if urgency != "high" else "accelerated",
            urgency=urgency,
            n_periods=n_periods,
            trajectory=trajectory.tolist(),
            estimated_impact_pct=impact_pct,
            estimated_cost_bps=cost_bps,
            kyle_lambda=self.kyle_lambda,
            slice_size_pct=slice_pct,
            time_between_slices=minutes_per_period * 60
        )
    
    def adjust_size_for_impact(
        self,
        desired_shares: float,
        price: float,
        avg_daily_volume: float,
        volatility: float,
        max_impact_pct: float = 0.005  # 50 bps
    ) -> float:
        """
        Reduce order size to stay within impact limits.
        
        Returns adjusted share count.
        """
        impact = self.estimate_impact(desired_shares, avg_daily_volume, volatility, price)
        
        if impact <= max_impact_pct:
            return desired_shares
        
        # Scale down proportionally
        scale = (max_impact_pct / impact) ** 2  # Square root relationship
        adjusted = desired_shares * scale
        
        logger.info(
            f"Reduced order from {desired_shares:.0f} to {adjusted:.0f} shares "
            f"(impact: {impact:.2%} -> {max_impact_pct:.2%})"
        )
        
        return adjusted


# Factory functions for Phase 2

def create_alpha_generator(
    momentum_lookback: int = 20,
    trend_lookback: int = 50
) -> IntegratedAlphaGenerator:
    """Create an alpha signal generator."""
    return IntegratedAlphaGenerator(
        momentum_lookback=momentum_lookback,
        trend_lookback=trend_lookback
    )


def create_execution_optimizer(
    volatility: float = 0.20
) -> IntegratedExecutionOptimizer:
    """Create an execution optimizer."""
    return IntegratedExecutionOptimizer(
        default_volatility=volatility
    )


# =============================================================================
# PHASE 3: RISK LAYER - CVaR, Circuit Breakers, Regime Alerts
# =============================================================================

from .portfolio import CVaROptimizer
from .statistics import ChangePointDetection


@dataclass
class RiskAlert:
    """Risk alert from monitoring system."""
    alert_type: str  # "drawdown", "var_breach", "regime_shift", "volatility_spike"
    severity: str    # "info", "warning", "critical"
    message: str
    value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TailRiskMetrics:
    """Tail risk metrics from CVaR analysis."""
    var_95: float      # Value at Risk (95%)
    var_99: float      # Value at Risk (99%)
    cvar_95: float     # Conditional VaR (95%)
    cvar_99: float     # Conditional VaR (99%)
    max_loss: float    # Worst historical loss
    
    # Risk-adjusted
    expected_shortfall: float  # Same as CVaR
    tail_ratio: float          # Gain in best days / loss in worst days


class IntegratedRiskMonitor:
    """
    Real-time risk monitoring with alerts and circuit breakers.
    
    Monitors:
    - Portfolio drawdown
    - VaR/CVaR breaches
    - Volatility spikes
    - Regime shifts (via change point detection)
    """
    
    def __init__(
        self,
        # Drawdown thresholds
        drawdown_warning: float = 0.05,    # 5% warning
        drawdown_critical: float = 0.10,   # 10% reduce positions
        drawdown_halt: float = 0.20,       # 20% stop trading
        
        # VaR thresholds
        var_limit_pct: float = 0.02,       # 2% daily VaR limit
        
        # Volatility thresholds
        vol_warning_mult: float = 1.5,     # 1.5x normal vol = warning
        vol_critical_mult: float = 2.5,    # 2.5x = critical
        
        # Lookback periods
        vol_lookback: int = 20,
        var_lookback: int = 252
    ):
        self.drawdown_warning = drawdown_warning
        self.drawdown_critical = drawdown_critical
        self.drawdown_halt = drawdown_halt
        
        self.var_limit = var_limit_pct
        
        self.vol_warning = vol_warning_mult
        self.vol_critical = vol_critical_mult
        
        self.vol_lookback = vol_lookback
        self.var_lookback = var_lookback
        
        # State tracking
        self.peak_equity = 0
        self.current_equity = 0
        self.returns_history: List[float] = []
        self.baseline_vol: Optional[float] = None
        
        # Alerts
        self.active_alerts: List[RiskAlert] = []
        self.circuit_breaker_active = False
    
    def update(
        self,
        equity: float,
        daily_return: Optional[float] = None
    ) -> List[RiskAlert]:
        """
        Update risk state and check for alerts.
        
        Returns list of new alerts.
        """
        alerts = []
        
        # Update equity tracking
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        # Update returns history
        if daily_return is not None:
            self.returns_history.append(daily_return)
            if len(self.returns_history) > self.var_lookback:
                self.returns_history = self.returns_history[-self.var_lookback:]
        
        # Check drawdown
        dd_alert = self._check_drawdown()
        if dd_alert:
            alerts.append(dd_alert)
        
        # Check VaR
        var_alert = self._check_var()
        if var_alert:
            alerts.append(var_alert)
        
        # Check volatility
        vol_alert = self._check_volatility()
        if vol_alert:
            alerts.append(vol_alert)
        
        # Update active alerts
        self.active_alerts = [a for a in alerts if a.severity in ["warning", "critical"]]
        
        # Circuit breaker
        self.circuit_breaker_active = any(
            a.severity == "critical" for a in alerts
        )
        
        return alerts
    
    @property
    def current_drawdown(self) -> float:
        """Current drawdown from peak."""
        if self.peak_equity <= 0:
            return 0
        return (self.peak_equity - self.current_equity) / self.peak_equity
    
    def _check_drawdown(self) -> Optional[RiskAlert]:
        """Check drawdown levels."""
        dd = self.current_drawdown
        
        if dd >= self.drawdown_halt:
            return RiskAlert(
                alert_type="drawdown",
                severity="critical",
                message=f"CIRCUIT BREAKER: Drawdown {dd:.1%} exceeds halt threshold",
                value=dd,
                threshold=self.drawdown_halt
            )
        elif dd >= self.drawdown_critical:
            return RiskAlert(
                alert_type="drawdown",
                severity="warning",
                message=f"Drawdown {dd:.1%} exceeds critical threshold - reduce positions",
                value=dd,
                threshold=self.drawdown_critical
            )
        elif dd >= self.drawdown_warning:
            return RiskAlert(
                alert_type="drawdown",
                severity="info",
                message=f"Drawdown {dd:.1%} exceeds warning threshold",
                value=dd,
                threshold=self.drawdown_warning
            )
        return None
    
    def _check_var(self) -> Optional[RiskAlert]:
        """Check VaR limits."""
        if len(self.returns_history) < 20:
            return None
        
        returns = np.array(self.returns_history)
        var_95 = np.percentile(returns, 5)  # 5th percentile = 95% VaR
        
        if abs(var_95) > self.var_limit:
            return RiskAlert(
                alert_type="var_breach",
                severity="warning",
                message=f"Daily VaR ({abs(var_95):.2%}) exceeds limit ({self.var_limit:.2%})",
                value=abs(var_95),
                threshold=self.var_limit
            )
        return None
    
    def _check_volatility(self) -> Optional[RiskAlert]:
        """Check for volatility spikes."""
        if len(self.returns_history) < self.vol_lookback * 2:
            return None
        
        returns = np.array(self.returns_history)
        
        # Recent vs historical volatility
        recent_vol = np.std(returns[-self.vol_lookback:])
        
        if self.baseline_vol is None:
            self.baseline_vol = np.std(returns[:-self.vol_lookback])
        
        if self.baseline_vol > 0:
            vol_ratio = recent_vol / self.baseline_vol
            
            if vol_ratio >= self.vol_critical:
                return RiskAlert(
                    alert_type="volatility_spike",
                    severity="critical",
                    message=f"Volatility spike: {vol_ratio:.1f}x normal",
                    value=vol_ratio,
                    threshold=self.vol_critical
                )
            elif vol_ratio >= self.vol_warning:
                return RiskAlert(
                    alert_type="volatility_spike",
                    severity="warning",
                    message=f"Elevated volatility: {vol_ratio:.1f}x normal",
                    value=vol_ratio,
                    threshold=self.vol_warning
                )
        return None
    
    def compute_tail_risk(self, returns: Optional[np.ndarray] = None) -> TailRiskMetrics:
        """
        Compute comprehensive tail risk metrics.
        
        Uses CVaR (Expected Shortfall) for coherent risk measurement.
        """
        if returns is None:
            returns = np.array(self.returns_history)
        
        if len(returns) < 20:
            # Default conservative estimates
            return TailRiskMetrics(
                var_95=0.02,
                var_99=0.04,
                cvar_95=0.03,
                cvar_99=0.05,
                max_loss=0.05,
                expected_shortfall=0.03,
                tail_ratio=1.0
            )
        
        sorted_returns = np.sort(returns)
        n = len(returns)
        
        # VaR (negative returns = losses)
        var_95 = -np.percentile(returns, 5)
        var_99 = -np.percentile(returns, 1)
        
        # CVaR (Expected Shortfall) - mean of losses beyond VaR
        idx_95 = int(0.05 * n)
        idx_99 = int(0.01 * n)
        
        cvar_95 = -np.mean(sorted_returns[:max(idx_95, 1)])
        cvar_99 = -np.mean(sorted_returns[:max(idx_99, 1)])
        
        # Max loss
        max_loss = -np.min(returns)
        
        # Tail ratio: best days / worst days
        best_5pct = np.mean(sorted_returns[-max(idx_95, 1):])
        worst_5pct = np.mean(sorted_returns[:max(idx_95, 1)])
        tail_ratio = abs(best_5pct / worst_5pct) if worst_5pct != 0 else 1.0
        
        return TailRiskMetrics(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_loss=max_loss,
            expected_shortfall=cvar_95,
            tail_ratio=tail_ratio
        )
    
    def get_position_limit(self, regime_state: Optional['RegimeState'] = None) -> float:
        """
        Get position limit multiplier based on current risk state.
        
        Returns value between 0 (no trading) and 1 (full capacity).
        """
        if self.circuit_breaker_active:
            return 0.0
        
        base = 1.0
        
        # Drawdown adjustment
        dd = self.current_drawdown
        if dd >= self.drawdown_critical:
            base *= 0.5
        elif dd >= self.drawdown_warning:
            base *= 0.75
        
        # Regime adjustment
        if regime_state is not None:
            base *= regime_state.position_scalar
        
        # Volatility adjustment
        if self.active_alerts:
            vol_alerts = [a for a in self.active_alerts if a.alert_type == "volatility_spike"]
            if vol_alerts:
                if vol_alerts[0].severity == "critical":
                    base *= 0.25
                else:
                    base *= 0.5
        
        return max(0, min(1, base))


class RegimeShiftDetector:
    """
    Detects regime shifts using change point detection.
    
    Monitors for:
    - Mean shifts (trend reversals)
    - Variance shifts (volatility regime changes)
    - Structural breaks
    """
    
    def __init__(
        self,
        min_segment: int = 20,
        sensitivity: float = 1.0  # Higher = more sensitive
    ):
        self.min_segment = min_segment
        self.sensitivity = sensitivity
        
        self.last_change_point: Optional[int] = None
        self.regime_history: List[Dict] = []
    
    def detect(self, prices: np.ndarray) -> Dict:
        """
        Detect regime shifts in price series.
        
        Returns:
            has_shift: Whether a recent shift was detected
            change_points: List of detected change points
            current_regime: Description of current regime
        """
        if len(prices) < self.min_segment * 2:
            return {
                "has_shift": False,
                "change_points": [],
                "current_regime": "insufficient_data"
            }
        
        returns = np.diff(np.log(prices))
        
        # Detect mean shifts (CUSUM)
        cusum_result = ChangePointDetection.cusum(
            returns,
            threshold=1.5 / self.sensitivity
        )
        
        # Detect variance shifts (on squared returns)
        vol_changes = ChangePointDetection.binary_segmentation(
            returns ** 2,
            min_segment=self.min_segment,
            threshold=np.log(len(returns)) / self.sensitivity
        )
        
        # Combine change points
        all_changes = sorted(set(cusum_result["change_points"] + vol_changes))
        
        # Check for recent shift
        recent_threshold = min(20, len(returns) // 5)
        has_recent_shift = any(
            cp > len(returns) - recent_threshold
            for cp in all_changes
        )
        
        # Characterize current regime
        if len(returns) >= self.min_segment:
            recent_returns = returns[-self.min_segment:]
            recent_mean = np.mean(recent_returns) * 252
            recent_vol = np.std(recent_returns) * np.sqrt(252)
            
            if recent_mean > 0.10 and recent_vol < 0.20:
                current_regime = "strong_uptrend"
            elif recent_mean > 0.05:
                current_regime = "uptrend"
            elif recent_mean < -0.10 and recent_vol > 0.25:
                current_regime = "crisis"
            elif recent_mean < -0.05:
                current_regime = "downtrend"
            elif recent_vol > 0.30:
                current_regime = "high_volatility"
            else:
                current_regime = "neutral"
        else:
            current_regime = "neutral"
        
        # Generate alert if shift detected
        result = {
            "has_shift": has_recent_shift,
            "change_points": all_changes,
            "current_regime": current_regime,
            "cusum_max": cusum_result["max_cusum"],
            "n_variance_shifts": len(vol_changes)
        }
        
        if has_recent_shift and self.last_change_point != all_changes[-1] if all_changes else True:
            self.last_change_point = all_changes[-1] if all_changes else None
            self.regime_history.append({
                "timestamp": datetime.now(),
                "regime": current_regime,
                "change_point": self.last_change_point
            })
        
        return result
    
    def get_regime_alert(self, detection_result: Dict) -> Optional[RiskAlert]:
        """Convert detection result to alert if warranted."""
        if not detection_result["has_shift"]:
            return None
        
        regime = detection_result["current_regime"]
        
        severity = "info"
        if regime in ["crisis", "high_volatility"]:
            severity = "critical"
        elif regime in ["downtrend"]:
            severity = "warning"
        
        return RiskAlert(
            alert_type="regime_shift",
            severity=severity,
            message=f"Regime shift detected: now in {regime} regime",
            value=detection_result["cusum_max"],
            threshold=1.5 / self.sensitivity
        )


# Factory functions for Phase 3

def create_risk_monitor(
    drawdown_critical: float = 0.10,
    drawdown_halt: float = 0.20,
    var_limit: float = 0.02
) -> IntegratedRiskMonitor:
    """Create a risk monitor with circuit breakers."""
    return IntegratedRiskMonitor(
        drawdown_critical=drawdown_critical,
        drawdown_halt=drawdown_halt,
        var_limit_pct=var_limit
    )


def create_regime_shift_detector(
    sensitivity: float = 1.0
) -> RegimeShiftDetector:
    """Create a regime shift detector."""
    return RegimeShiftDetector(sensitivity=sensitivity)
