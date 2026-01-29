"""
Gamma Exposure (GEX) Calculator
===============================
Calculates dealer gamma exposure for market maker hedging flow prediction.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import logging
import math
from collections import defaultdict

logger = logging.getLogger(__name__)


# Black-Scholes helpers
def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def calculate_delta(
    spot: float,
    strike: float,
    tte: float,
    iv: float,
    is_call: bool,
    rate: float = 0.05,
) -> float:
    """Calculate option delta."""
    if tte <= 0 or iv <= 0:
        # At expiration
        if is_call:
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0
            
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv ** 2) * tte) / (iv * math.sqrt(tte))
    
    if is_call:
        return _norm_cdf(d1)
    else:
        return _norm_cdf(d1) - 1


def calculate_gamma(
    spot: float,
    strike: float,
    tte: float,
    iv: float,
    rate: float = 0.05,
) -> float:
    """Calculate option gamma."""
    if tte <= 0 or iv <= 0 or spot <= 0:
        return 0.0
        
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv ** 2) * tte) / (iv * math.sqrt(tte))
    return _norm_pdf(d1) / (spot * iv * math.sqrt(tte))


def calculate_vanna(
    spot: float,
    strike: float,
    tte: float,
    iv: float,
    rate: float = 0.05,
) -> float:
    """Calculate option vanna (dDelta/dVol)."""
    if tte <= 0 or iv <= 0 or spot <= 0:
        return 0.0
        
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv ** 2) * tte) / (iv * math.sqrt(tte))
    d2 = d1 - iv * math.sqrt(tte)
    
    return -_norm_pdf(d1) * d2 / iv


def calculate_charm(
    spot: float,
    strike: float,
    tte: float,
    iv: float,
    is_call: bool,
    rate: float = 0.05,
) -> float:
    """Calculate option charm (dDelta/dTime)."""
    if tte <= 0 or iv <= 0 or spot <= 0:
        return 0.0
        
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv ** 2) * tte) / (iv * math.sqrt(tte))
    d2 = d1 - iv * math.sqrt(tte)
    
    term1 = _norm_pdf(d1) * (2 * rate * tte - d2 * iv * math.sqrt(tte)) / (2 * tte * iv * math.sqrt(tte))
    
    if is_call:
        return -term1
    else:
        return -term1


@dataclass
class OptionPosition:
    """Single option position for GEX calculation."""
    symbol: str
    strike: float
    expiry: date
    is_call: bool
    open_interest: int
    iv: float = 0.0
    
    @property
    def tte(self) -> float:
        """Time to expiration in years."""
        days = (self.expiry - date.today()).days
        return max(0, days) / 365.0


@dataclass
class GEXLevel:
    """Gamma exposure at a specific price level."""
    price: float
    call_gex: float = 0.0
    put_gex: float = 0.0
    
    @property
    def total_gex(self) -> float:
        """Net gamma exposure (calls - puts for dealer)."""
        # Dealers are short calls (negative gamma) and short puts (positive gamma)
        # When customers buy calls, dealers sell calls and are short gamma
        # When customers buy puts, dealers sell puts and are also short gamma
        # Net GEX = Put GEX - Call GEX (from dealer perspective)
        return self.put_gex - self.call_gex
    
    @property
    def flip_contribution(self) -> float:
        """How much this level contributes to gamma flip."""
        return self.total_gex


@dataclass
class GEXProfile:
    """Complete gamma exposure profile for a symbol."""
    symbol: str
    spot_price: float
    levels: List[GEXLevel]
    total_call_gex: float
    total_put_gex: float
    net_gex: float
    gamma_flip_price: Optional[float]  # Price where GEX flips from + to -
    key_strikes: List[float]  # High gamma strikes
    calculated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def is_positive_gamma(self) -> bool:
        """True if dealers are long gamma (stabilizing)."""
        return self.net_gex > 0
    
    @property
    def regime(self) -> str:
        """Market regime based on gamma."""
        if self.net_gex > 0:
            return "positive_gamma"  # Dealers hedge into moves, dampening
        else:
            return "negative_gamma"  # Dealers hedge with moves, amplifying
    
    def gex_at_price(self, price: float) -> Optional[GEXLevel]:
        """Get GEX at specific price."""
        for level in self.levels:
            if abs(level.price - price) < 0.01:
                return level
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "spot_price": self.spot_price,
            "net_gex": self.net_gex,
            "total_call_gex": self.total_call_gex,
            "total_put_gex": self.total_put_gex,
            "regime": self.regime,
            "gamma_flip_price": self.gamma_flip_price,
            "key_strikes": self.key_strikes,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass 
class GEXConfig:
    """Configuration for GEX calculations."""
    price_range_pct: float = 0.15  # Calculate GEX ±15% from spot
    price_step_pct: float = 0.005  # 0.5% price steps
    min_oi: int = 100  # Minimum open interest to include
    max_dte: int = 45  # Maximum days to expiration
    risk_free_rate: float = 0.05
    contract_multiplier: int = 100


class GammaExposureCalculator:
    """
    Calculates aggregate dealer gamma exposure.
    
    GEX (Gamma Exposure) represents the amount dealers need to buy/sell
    to hedge their options positions as the underlying moves.
    
    Positive GEX = dealers long gamma = buy dips, sell rips (stabilizing)
    Negative GEX = dealers short gamma = sell dips, buy rips (destabilizing)
    """
    
    def __init__(self, config: Optional[GEXConfig] = None):
        self.config = config or GEXConfig()
        self._cache: Dict[str, GEXProfile] = {}
        
    def calculate_gex_profile(
        self,
        symbol: str,
        spot_price: float,
        positions: List[OptionPosition],
    ) -> GEXProfile:
        """
        Calculate complete GEX profile for symbol.
        
        Args:
            symbol: Underlying symbol
            spot_price: Current spot price
            positions: List of option positions (OI data)
            
        Returns:
            GEXProfile with levels and metrics
        """
        # Filter positions
        filtered = [
            p for p in positions
            if p.open_interest >= self.config.min_oi
            and 0 < p.tte * 365 <= self.config.max_dte
        ]
        
        if not filtered:
            return self._empty_profile(symbol, spot_price)
            
        # Calculate price range
        low = spot_price * (1 - self.config.price_range_pct)
        high = spot_price * (1 + self.config.price_range_pct)
        step = spot_price * self.config.price_step_pct
        
        # Generate price levels
        prices = []
        p = low
        while p <= high:
            prices.append(round(p, 2))
            p += step
            
        # Calculate GEX at each level
        levels = []
        for price in prices:
            call_gex = 0.0
            put_gex = 0.0
            
            for pos in filtered:
                gamma = calculate_gamma(
                    spot=price,
                    strike=pos.strike,
                    tte=pos.tte,
                    iv=pos.iv if pos.iv > 0 else 0.3,  # Default 30% IV
                    rate=self.config.risk_free_rate,
                )
                
                # GEX = Gamma * OI * Spot * 100
                # This represents $ of stock to trade per $1 move
                gex = gamma * pos.open_interest * price * self.config.contract_multiplier
                
                if pos.is_call:
                    call_gex += gex
                else:
                    put_gex += gex
                    
            levels.append(GEXLevel(price=price, call_gex=call_gex, put_gex=put_gex))
        
        # Calculate totals at spot
        spot_level = min(levels, key=lambda l: abs(l.price - spot_price))
        total_call = spot_level.call_gex
        total_put = spot_level.put_gex
        net_gex = spot_level.total_gex
        
        # Find gamma flip point
        gamma_flip = self._find_gamma_flip(levels)
        
        # Find key strikes (high gamma concentration)
        key_strikes = self._find_key_strikes(filtered, spot_price)
        
        profile = GEXProfile(
            symbol=symbol,
            spot_price=spot_price,
            levels=levels,
            total_call_gex=total_call,
            total_put_gex=total_put,
            net_gex=net_gex,
            gamma_flip_price=gamma_flip,
            key_strikes=key_strikes,
        )
        
        self._cache[symbol] = profile
        return profile
    
    def _empty_profile(self, symbol: str, spot_price: float) -> GEXProfile:
        """Return empty profile when no data."""
        return GEXProfile(
            symbol=symbol,
            spot_price=spot_price,
            levels=[],
            total_call_gex=0.0,
            total_put_gex=0.0,
            net_gex=0.0,
            gamma_flip_price=None,
            key_strikes=[],
        )
    
    def _find_gamma_flip(self, levels: List[GEXLevel]) -> Optional[float]:
        """Find price where GEX flips from positive to negative."""
        if len(levels) < 2:
            return None
            
        for i in range(len(levels) - 1):
            curr = levels[i].total_gex
            next_gex = levels[i + 1].total_gex
            
            # Sign change from + to -
            if curr > 0 and next_gex < 0:
                # Linear interpolation
                ratio = curr / (curr - next_gex)
                flip = levels[i].price + ratio * (levels[i + 1].price - levels[i].price)
                return round(flip, 2)
                
        return None
    
    def _find_key_strikes(
        self,
        positions: List[OptionPosition],
        spot_price: float,
        num_strikes: int = 5,
    ) -> List[float]:
        """Find strikes with highest gamma concentration."""
        strike_gex: Dict[float, float] = defaultdict(float)
        
        for pos in positions:
            gamma = calculate_gamma(
                spot=spot_price,
                strike=pos.strike,
                tte=pos.tte,
                iv=pos.iv if pos.iv > 0 else 0.3,
                rate=self.config.risk_free_rate,
            )
            gex = gamma * pos.open_interest * spot_price * self.config.contract_multiplier
            strike_gex[pos.strike] += abs(gex)
            
        # Sort by GEX magnitude
        sorted_strikes = sorted(strike_gex.items(), key=lambda x: x[1], reverse=True)
        return [s[0] for s in sorted_strikes[:num_strikes]]
    
    def get_hedging_flow_estimate(
        self,
        symbol: str,
        price_move: float,
    ) -> Dict[str, Any]:
        """
        Estimate dealer hedging flow for a price move.
        
        Args:
            symbol: Underlying symbol
            price_move: Expected price move in $
            
        Returns:
            Estimated shares dealers need to trade
        """
        profile = self._cache.get(symbol)
        if not profile:
            return {"symbol": symbol, "error": "No GEX profile cached"}
            
        # Shares to trade = GEX * price_move / spot
        # Positive GEX + up move = dealers sell
        # Negative GEX + up move = dealers buy
        
        shares = profile.net_gex * price_move / profile.spot_price
        direction = "sell" if shares > 0 else "buy"
        
        return {
            "symbol": symbol,
            "price_move": price_move,
            "estimated_shares": abs(int(shares)),
            "direction": direction,
            "net_gex": profile.net_gex,
            "regime": profile.regime,
            "impact": "stabilizing" if profile.is_positive_gamma else "amplifying",
        }
    
    def calculate_pin_risk(
        self,
        symbol: str,
        spot_price: float,
        positions: List[OptionPosition],
        expiry: date,
    ) -> Dict[str, Any]:
        """
        Calculate pin risk for specific expiration.
        
        High gamma at strikes near spot creates "pinning" where
        price tends to gravitate toward max pain / high gamma strikes.
        """
        # Filter for specific expiry
        expiry_positions = [p for p in positions if p.expiry == expiry]
        
        if not expiry_positions:
            return {"symbol": symbol, "expiry": expiry.isoformat(), "pin_strikes": []}
            
        # Calculate gamma at each strike
        strike_gamma: Dict[float, float] = defaultdict(float)
        
        for pos in expiry_positions:
            gamma = calculate_gamma(
                spot=spot_price,
                strike=pos.strike,
                tte=pos.tte,
                iv=pos.iv if pos.iv > 0 else 0.3,
            )
            strike_gamma[pos.strike] += gamma * pos.open_interest
            
        # Find strikes with highest gamma near spot (within 5%)
        near_strikes = {
            k: v for k, v in strike_gamma.items()
            if abs(k - spot_price) / spot_price < 0.05
        }
        
        if not near_strikes:
            return {"symbol": symbol, "expiry": expiry.isoformat(), "pin_strikes": []}
            
        # Sort by gamma
        sorted_strikes = sorted(near_strikes.items(), key=lambda x: x[1], reverse=True)
        pin_strikes = [{"strike": s[0], "gamma": s[1]} for s in sorted_strikes[:3]]
        
        return {
            "symbol": symbol,
            "expiry": expiry.isoformat(),
            "spot_price": spot_price,
            "pin_strikes": pin_strikes,
            "highest_gamma_strike": sorted_strikes[0][0] if sorted_strikes else None,
            "pin_probability": "high" if sorted_strikes[0][1] > 1000 else "moderate",
        }


class GEXVisualizer:
    """Helper class for GEX visualization data."""
    
    @staticmethod
    def get_chart_data(profile: GEXProfile) -> Dict[str, Any]:
        """Get data formatted for charting."""
        return {
            "symbol": profile.symbol,
            "spot_price": profile.spot_price,
            "prices": [l.price for l in profile.levels],
            "call_gex": [l.call_gex for l in profile.levels],
            "put_gex": [l.put_gex for l in profile.levels],
            "net_gex": [l.total_gex for l in profile.levels],
            "gamma_flip": profile.gamma_flip_price,
            "key_strikes": profile.key_strikes,
        }
    
    @staticmethod
    def get_support_resistance(
        profile: GEXProfile,
        num_levels: int = 3,
    ) -> Dict[str, List[float]]:
        """
        Get support/resistance levels from GEX.
        
        High positive GEX = support (dealers buy on dips)
        High negative GEX = resistance (dealers sell on rips)
        """
        below_spot = [l for l in profile.levels if l.price < profile.spot_price]
        above_spot = [l for l in profile.levels if l.price > profile.spot_price]
        
        # Support: positive GEX levels below spot
        support_levels = sorted(
            [l for l in below_spot if l.total_gex > 0],
            key=lambda l: l.total_gex,
            reverse=True,
        )[:num_levels]
        
        # Resistance: negative GEX levels above spot  
        resistance_levels = sorted(
            [l for l in above_spot if l.total_gex < 0],
            key=lambda l: l.total_gex,
        )[:num_levels]
        
        return {
            "support": [l.price for l in support_levels],
            "resistance": [l.price for l in resistance_levels],
        }


class VannaVolgaAnalyzer:
    """
    Analyzes Vanna and Volga effects on dealer hedging.
    
    Vanna: sensitivity of delta to volatility changes
    Volga (Vomma): sensitivity of vega to volatility changes
    """
    
    def __init__(self, config: Optional[GEXConfig] = None):
        self.config = config or GEXConfig()
        
    def calculate_vanna_exposure(
        self,
        symbol: str,
        spot_price: float,
        positions: List[OptionPosition],
    ) -> Dict[str, Any]:
        """Calculate aggregate vanna exposure."""
        total_vanna = 0.0
        call_vanna = 0.0
        put_vanna = 0.0
        
        for pos in positions:
            if pos.open_interest < self.config.min_oi:
                continue
                
            vanna = calculate_vanna(
                spot=spot_price,
                strike=pos.strike,
                tte=pos.tte,
                iv=pos.iv if pos.iv > 0 else 0.3,
                rate=self.config.risk_free_rate,
            )
            
            exposure = vanna * pos.open_interest * spot_price * self.config.contract_multiplier
            
            if pos.is_call:
                call_vanna += exposure
            else:
                put_vanna += exposure
                
            total_vanna += exposure
            
        return {
            "symbol": symbol,
            "spot_price": spot_price,
            "total_vanna": total_vanna,
            "call_vanna": call_vanna,
            "put_vanna": put_vanna,
            "vol_sensitivity": "high" if abs(total_vanna) > 1e6 else "moderate",
        }
    
    def estimate_vol_impact_flow(
        self,
        symbol: str,
        vanna_exposure: float,
        vol_change: float,
    ) -> Dict[str, Any]:
        """
        Estimate hedging flow from volatility change.
        
        Args:
            vanna_exposure: From calculate_vanna_exposure
            vol_change: Change in IV (e.g., 0.05 for 5% vol increase)
            
        Returns:
            Estimated shares to trade
        """
        # Delta change from vol change = Vanna * vol_change
        # Shares to hedge = delta_change * OI * multiplier
        
        shares = vanna_exposure * vol_change
        direction = "buy" if shares > 0 else "sell"
        
        return {
            "symbol": symbol,
            "vol_change": vol_change,
            "estimated_shares": abs(int(shares)),
            "direction": direction,
        }
