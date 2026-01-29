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
