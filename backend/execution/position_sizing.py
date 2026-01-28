"""
QUANT INDUSTRY - Dynamic Position Sizing
========================================
Institutional-grade position sizing with:
- Kelly Criterion (fractional)
- Volatility targeting
- Correlation-adjusted sizing
- Risk parity allocation

The #1 reason traders blow up: position sizing too large.
Kelly says 10%, you should use 2.5-5% (0.25-0.5 Kelly).

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class SizingMethod(Enum):
    """Position sizing methods"""
    FIXED_PCT = "fixed_pct"           # Fixed % of equity
    KELLY = "kelly"                   # Kelly criterion
    VOLATILITY_TARGET = "vol_target"  # Target volatility
    RISK_PARITY = "risk_parity"       # Equal risk contribution
    ATR_BASED = "atr_based"           # ATR-scaled sizing


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation"""
    shares: int
    notional: float
    risk_pct: float          # % of equity at risk
    kelly_fraction: float    # What fraction of Kelly we're using
    vol_adjusted: bool       # Whether vol scaling was applied
    notes: str = ""


class DynamicPositionSizer:
    """
    Dynamic position sizing engine.
    
    Implements multiple sizing methods with safety limits:
    1. Never exceed max_position_pct
    2. Scale down when volatility spikes
    3. Apply Kelly with safety margin
    
    Usage:
    ------
    >>> sizer = DynamicPositionSizer(
    ...     method=SizingMethod.VOLATILITY_TARGET,
    ...     target_volatility=0.15,  # 15% annualized target
    ...     max_position_pct=10.0
    ... )
    >>> result = sizer.calculate_size(
    ...     equity=100_000,
    ...     price=150.0,
    ...     current_volatility=0.25,  # 25% realized vol
    ...     win_rate=0.55,
    ...     avg_win_loss_ratio=1.5
    ... )
    >>> print(f"Position: {result.shares} shares (${result.notional:,.0f})")
    """
    
    def __init__(
        self,
        method: SizingMethod = SizingMethod.VOLATILITY_TARGET,
        base_position_pct: float = 10.0,    # Base position size as % of equity
        max_position_pct: float = 20.0,     # Hard cap
        min_position_pct: float = 1.0,      # Minimum size
        target_volatility: float = 0.15,    # 15% annualized vol target
        kelly_fraction: float = 0.25,       # Use 25% of Kelly (conservative)
        vol_lookback_days: int = 20,        # Days for vol calculation
        vol_scale_factor: float = 1.5,      # Scale down when vol > 1.5x target
        max_vol_multiplier: float = 3.0,    # Don't scale more than 3x
    ):
        """
        Initialize position sizer.
        
        Args:
            method: Sizing method to use
            base_position_pct: Default position size
            max_position_pct: Maximum allowed position (hard stop)
            min_position_pct: Minimum position size
            target_volatility: Target portfolio volatility (annualized)
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
            vol_lookback_days: Days to calculate realized vol
            vol_scale_factor: Vol threshold for scaling
            max_vol_multiplier: Max scaling factor
        """
        self.method = method
        self.base_position_pct = base_position_pct
        self.max_position_pct = max_position_pct
        self.min_position_pct = min_position_pct
        self.target_volatility = target_volatility
        self.kelly_fraction = kelly_fraction
        self.vol_lookback_days = vol_lookback_days
        self.vol_scale_factor = vol_scale_factor
        self.max_vol_multiplier = max_vol_multiplier
        
        logger.info(
            f"DynamicPositionSizer initialized: method={method.value}, "
            f"target_vol={target_volatility:.0%}, kelly_frac={kelly_fraction}"
        )
    
    def calculate_size(
        self,
        equity: float,
        price: float,
        current_volatility: float = None,
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 1.0,
        atr: float = None,
        correlation_to_portfolio: float = 0.0
    ) -> PositionSizeResult:
        """
        Calculate position size.
        
        Args:
            equity: Current portfolio equity
            price: Current price of instrument
            current_volatility: Current realized volatility (annualized)
            win_rate: Historical win rate (for Kelly)
            avg_win_loss_ratio: Avg win / avg loss (for Kelly)
            atr: Average True Range (for ATR-based sizing)
            correlation_to_portfolio: Correlation with existing positions
            
        Returns:
            PositionSizeResult with shares and details
        """
        # Start with base position
        position_pct = self.base_position_pct
        vol_adjusted = False
        kelly_used = 0.0
        notes = []
        
        # Apply method-specific sizing
        if self.method == SizingMethod.KELLY:
            kelly_pct = self._calculate_kelly(win_rate, avg_win_loss_ratio)
            position_pct = kelly_pct * self.kelly_fraction * 100  # Convert to %
            kelly_used = self.kelly_fraction
            notes.append(f"Full Kelly: {kelly_pct:.1%}, Using: {position_pct:.1f}%")
        
        elif self.method == SizingMethod.VOLATILITY_TARGET:
            if current_volatility and current_volatility > 0:
                vol_ratio = self.target_volatility / current_volatility
                vol_ratio = min(vol_ratio, self.max_vol_multiplier)  # Cap scaling up
                vol_ratio = max(vol_ratio, 1 / self.max_vol_multiplier)  # Cap scaling down
                position_pct = self.base_position_pct * vol_ratio
                vol_adjusted = True
                notes.append(f"Vol scaling: {vol_ratio:.2f}x (target={self.target_volatility:.0%}, current={current_volatility:.0%})")
        
        elif self.method == SizingMethod.ATR_BASED:
            if atr and atr > 0 and price > 0:
                # Size such that 1 ATR move = 1% of equity
                risk_per_share = atr
                target_risk_dollars = equity * 0.01  # 1% of equity
                shares_from_atr = int(target_risk_dollars / risk_per_share)
                position_pct = (shares_from_atr * price / equity) * 100
                notes.append(f"ATR-based: {shares_from_atr} shares ({position_pct:.1f}%)")
        
        elif self.method == SizingMethod.RISK_PARITY:
            if current_volatility and current_volatility > 0:
                # Equal risk contribution
                vol_ratio = self.target_volatility / current_volatility
                position_pct = self.base_position_pct * vol_ratio
                
                # Adjust for correlation
                if correlation_to_portfolio != 0:
                    # Reduce if correlated with existing positions
                    corr_adj = 1 - abs(correlation_to_portfolio) * 0.5
                    position_pct *= corr_adj
                    notes.append(f"Correlation adjustment: {corr_adj:.2f}x")
                
                vol_adjusted = True
        
        # Apply volatility scaling (if not already done)
        if not vol_adjusted and current_volatility:
            vol_ratio = current_volatility / self.target_volatility
            if vol_ratio > self.vol_scale_factor:
                # Vol is elevated, scale down
                scale_down = self.target_volatility / current_volatility
                scale_down = max(scale_down, 1 / self.max_vol_multiplier)
                position_pct *= scale_down
                vol_adjusted = True
                notes.append(f"Vol spike scaling: {scale_down:.2f}x")
        
        # Apply limits
        original_pct = position_pct
        position_pct = max(position_pct, self.min_position_pct)
        position_pct = min(position_pct, self.max_position_pct)
        
        if position_pct != original_pct:
            notes.append(f"Capped from {original_pct:.1f}% to {position_pct:.1f}%")
        
        # Calculate shares
        notional = equity * (position_pct / 100)
        shares = int(notional / price) if price > 0 else 0
        actual_notional = shares * price
        actual_pct = (actual_notional / equity * 100) if equity > 0 else 0
        
        return PositionSizeResult(
            shares=shares,
            notional=actual_notional,
            risk_pct=actual_pct,
            kelly_fraction=kelly_used,
            vol_adjusted=vol_adjusted,
            notes="; ".join(notes)
        )
    
    def _calculate_kelly(
        self,
        win_rate: float,
        avg_win_loss_ratio: float
    ) -> float:
        """
        Calculate Kelly Criterion optimal bet size.
        
        Kelly formula: f* = (p * b - q) / b
        where:
            p = probability of winning
            q = probability of losing (1 - p)
            b = ratio of win to loss
            
        Returns:
            Optimal fraction of bankroll to bet
        """
        p = min(max(win_rate, 0.0), 1.0)  # Clamp to [0, 1]
        q = 1 - p
        b = max(avg_win_loss_ratio, 0.01)  # Prevent division by zero
        
        kelly = (p * b - q) / b
        
        # Kelly can be negative (don't trade) or > 1 (never happens with real stats)
        kelly = max(kelly, 0)
        kelly = min(kelly, 1)
        
        return kelly
    
    def calculate_kelly_from_trades(
        self,
        pnl_list: List[float]
    ) -> Tuple[float, float, float]:
        """
        Calculate Kelly parameters from historical trade P&L.
        
        Args:
            pnl_list: List of trade P&L values
            
        Returns:
            Tuple of (kelly_fraction, win_rate, win_loss_ratio)
        """
        if not pnl_list or len(pnl_list) < 10:
            return 0.0, 0.5, 1.0
        
        wins = [p for p in pnl_list if p > 0]
        losses = [p for p in pnl_list if p <= 0]
        
        win_rate = len(wins) / len(pnl_list)
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0.01
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0
        
        kelly = self._calculate_kelly(win_rate, win_loss_ratio)
        
        return kelly, win_rate, win_loss_ratio


class VolatilityScaler:
    """
    Simple volatility-based position scaling.
    
    When realized volatility exceeds target, scale down positions.
    When vol is low, can scale up (carefully).
    
    This is the #1 defense against regime changes blowing up your account.
    """
    
    def __init__(
        self,
        target_vol: float = 0.15,        # 15% target
        vol_lookback: int = 20,          # 20-day realized vol
        max_scale_up: float = 1.5,       # Max 1.5x leverage when vol is low
        min_scale_down: float = 0.2,     # Min 0.2x when vol spikes
        emergency_vol_threshold: float = 0.50  # 50% vol = emergency
    ):
        self.target_vol = target_vol
        self.vol_lookback = vol_lookback
        self.max_scale_up = max_scale_up
        self.min_scale_down = min_scale_down
        self.emergency_vol_threshold = emergency_vol_threshold
        
        self._recent_returns: List[float] = []
    
    def update(self, daily_return: float):
        """Update with new daily return"""
        self._recent_returns.append(daily_return)
        if len(self._recent_returns) > self.vol_lookback:
            self._recent_returns.pop(0)
    
    def get_scale_factor(self, current_vol: float = None) -> float:
        """
        Get position scaling factor.
        
        Returns:
            Float multiplier for position sizes (0.2 to 1.5)
        """
        # Calculate realized vol if not provided
        if current_vol is None:
            if len(self._recent_returns) < 5:
                return 1.0
            current_vol = np.std(self._recent_returns) * np.sqrt(252)
        
        # Emergency check
        if current_vol >= self.emergency_vol_threshold:
            logger.warning(f"EMERGENCY: Vol at {current_vol:.0%} - scaling to minimum")
            return self.min_scale_down
        
        # Calculate scale factor
        scale = self.target_vol / current_vol if current_vol > 0 else 1.0
        
        # Apply limits
        scale = min(scale, self.max_scale_up)
        scale = max(scale, self.min_scale_down)
        
        return scale
    
    def get_current_vol(self) -> float:
        """Get current realized volatility"""
        if len(self._recent_returns) < 5:
            return self.target_vol
        return np.std(self._recent_returns) * np.sqrt(252)


# ============== CONVENIENCE FUNCTIONS ==============

def calculate_position_size(
    equity: float,
    price: float,
    volatility: float = 0.20,
    max_pct: float = 10.0,
    target_vol: float = 0.15
) -> int:
    """
    Quick position size calculation with vol targeting.
    
    Args:
        equity: Portfolio value
        price: Instrument price
        volatility: Current volatility (annualized)
        max_pct: Maximum position as % of equity
        target_vol: Target portfolio volatility
        
    Returns:
        Number of shares
    """
    sizer = DynamicPositionSizer(
        method=SizingMethod.VOLATILITY_TARGET,
        target_volatility=target_vol,
        max_position_pct=max_pct
    )
    
    result = sizer.calculate_size(
        equity=equity,
        price=price,
        current_volatility=volatility
    )
    
    return result.shares


def get_kelly_size(
    equity: float,
    price: float,
    win_rate: float,
    win_loss_ratio: float,
    kelly_fraction: float = 0.25
) -> int:
    """
    Calculate Kelly-optimal position size.
    
    Args:
        equity: Portfolio value
        price: Instrument price
        win_rate: Historical win rate
        win_loss_ratio: Average win / average loss
        kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)
        
    Returns:
        Number of shares
    """
    sizer = DynamicPositionSizer(
        method=SizingMethod.KELLY,
        kelly_fraction=kelly_fraction
    )
    
    result = sizer.calculate_size(
        equity=equity,
        price=price,
        win_rate=win_rate,
        avg_win_loss_ratio=win_loss_ratio
    )
    
    return result.shares
