"""
QUANT INDUSTRY - GEX (Gamma Exposure) Analyzer
Dealer gamma positioning and market impact analysis
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StrikeGEX:
    strike: float
    call_gamma: float
    put_gamma: float
    call_oi: int
    put_oi: int
    call_gex: float
    put_gex: float
    net_gex: float

    def to_dict(self) -> Dict:
        return {
            "strike": self.strike,
            "call_gamma": round(self.call_gamma, 6),
            "put_gamma": round(self.put_gamma, 6),
            "call_oi": self.call_oi,
            "put_oi": self.put_oi,
            "call_gex": round(self.call_gex, 2),
            "put_gex": round(self.put_gex, 2),
            "net_gex": round(self.net_gex, 2),
        }


@dataclass
class GEXData:
    symbol: str
    underlying_price: float
    timestamp: datetime
    strikes: List[StrikeGEX]

    # Aggregated metrics
    total_call_gex: float
    total_put_gex: float
    total_net_gex: float

    # Key levels
    max_gamma_strike: float
    zero_gamma_level: float
    call_wall: float
    put_wall: float

    # Market interpretation
    dealer_positioning: str  # "LONG_GAMMA", "SHORT_GAMMA", "NEUTRAL"
    expected_volatility: str  # "LOW", "NORMAL", "HIGH"
    bias: str  # "BULLISH", "BEARISH", "NEUTRAL"

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "underlying_price": self.underlying_price,
            "timestamp": self.timestamp.isoformat(),
            "strikes": [s.to_dict() for s in self.strikes],
            "total_call_gex": round(self.total_call_gex, 2),
            "total_put_gex": round(self.total_put_gex, 2),
            "total_net_gex": round(self.total_net_gex, 2),
            "max_gamma_strike": self.max_gamma_strike,
            "zero_gamma_level": self.zero_gamma_level,
            "call_wall": self.call_wall,
            "put_wall": self.put_wall,
            "dealer_positioning": self.dealer_positioning,
            "expected_volatility": self.expected_volatility,
            "bias": self.bias,
        }


class GEXAnalyzer:
    """
    Gamma Exposure (GEX) analyzer for market structure analysis

    GEX = Gamma * Open Interest * Contract Multiplier * Spot Price

    Positive GEX = Dealers are long gamma (dampening volatility)
    Negative GEX = Dealers are short gamma (amplifying volatility)
    """

    def __init__(self):
        self.contract_multiplier = 100  # Standard equity options
        logger.info("GEXAnalyzer initialized")

    def analyze(self, symbol: str, options_chain) -> GEXData:
        """
        Analyze gamma exposure from options chain

        Args:
            symbol: Underlying symbol
            options_chain: OptionsChain object with calls and puts
        """
        underlying_price = options_chain.underlying_price

        # Group by strike
        strike_data = {}

        # Process calls (dealers typically short calls = long delta, short gamma)
        for call in options_chain.calls:
            strike = call.strike
            if strike not in strike_data:
                strike_data[strike] = {
                    "call_gamma": 0, "put_gamma": 0,
                    "call_oi": 0, "put_oi": 0
                }

            strike_data[strike]["call_gamma"] = call.greeks.gamma if call.greeks else 0
            strike_data[strike]["call_oi"] = call.open_interest

        # Process puts (dealers typically short puts = short delta, short gamma)
        for put in options_chain.puts:
            strike = put.strike
            if strike not in strike_data:
                strike_data[strike] = {
                    "call_gamma": 0, "put_gamma": 0,
                    "call_oi": 0, "put_oi": 0
                }

            strike_data[strike]["put_gamma"] = put.greeks.gamma if put.greeks else 0
            strike_data[strike]["put_oi"] = put.open_interest

        # Calculate GEX for each strike
        strikes = []
        total_call_gex = 0
        total_put_gex = 0

        for strike, data in sorted(strike_data.items()):
            # GEX calculation
            # Calls: Dealers are typically short calls, so they're short gamma
            # Puts: Dealers are typically short puts, so they're short gamma
            # However, for puts, dealer gamma exposure is opposite (short gamma = negative effect on spot)

            call_gex = data["call_gamma"] * data["call_oi"] * self.contract_multiplier * underlying_price
            # For puts, gamma is negative for dealers (they lose when spot moves)
            put_gex = -data["put_gamma"] * data["put_oi"] * self.contract_multiplier * underlying_price

            net_gex = call_gex + put_gex

            strike_gex = StrikeGEX(
                strike=strike,
                call_gamma=data["call_gamma"],
                put_gamma=data["put_gamma"],
                call_oi=data["call_oi"],
                put_oi=data["put_oi"],
                call_gex=call_gex / 1_000_000,  # Convert to millions
                put_gex=put_gex / 1_000_000,
                net_gex=net_gex / 1_000_000,
            )

            strikes.append(strike_gex)
            total_call_gex += call_gex
            total_put_gex += put_gex

        total_net_gex = total_call_gex + total_put_gex

        # Find key levels
        max_gamma_strike = self._find_max_gamma_strike(strikes)
        zero_gamma_level = self._find_zero_gamma_level(strikes, underlying_price)
        call_wall = self._find_call_wall(strikes)
        put_wall = self._find_put_wall(strikes)

        # Interpret positioning
        dealer_positioning = self._determine_dealer_positioning(total_net_gex)
        expected_volatility = self._determine_expected_volatility(total_net_gex, underlying_price)
        bias = self._determine_bias(zero_gamma_level, underlying_price, total_net_gex)

        return GEXData(
            symbol=symbol,
            underlying_price=underlying_price,
            timestamp=datetime.now(),
            strikes=strikes,
            total_call_gex=total_call_gex / 1_000_000,
            total_put_gex=total_put_gex / 1_000_000,
            total_net_gex=total_net_gex / 1_000_000,
            max_gamma_strike=max_gamma_strike,
            zero_gamma_level=zero_gamma_level,
            call_wall=call_wall,
            put_wall=put_wall,
            dealer_positioning=dealer_positioning,
            expected_volatility=expected_volatility,
            bias=bias,
        )

    def _find_max_gamma_strike(self, strikes: List[StrikeGEX]) -> float:
        """Find strike with maximum absolute gamma"""
        if not strikes:
            return 0

        max_strike = max(strikes, key=lambda s: abs(s.net_gex))
        return max_strike.strike

    def _find_zero_gamma_level(self, strikes: List[StrikeGEX], current_price: float) -> float:
        """Find price level where net gamma crosses zero"""
        if not strikes or len(strikes) < 2:
            return current_price

        # Find strikes around zero crossing
        for i in range(len(strikes) - 1):
            if strikes[i].net_gex * strikes[i + 1].net_gex < 0:
                # Linear interpolation
                x1, y1 = strikes[i].strike, strikes[i].net_gex
                x2, y2 = strikes[i + 1].strike, strikes[i + 1].net_gex

                if y2 - y1 != 0:
                    zero_level = x1 - y1 * (x2 - x1) / (y2 - y1)
                    return zero_level

        return current_price

    def _find_call_wall(self, strikes: List[StrikeGEX]) -> float:
        """Find the strike with highest call OI (resistance)"""
        if not strikes:
            return 0

        max_call_oi_strike = max(strikes, key=lambda s: s.call_oi)
        return max_call_oi_strike.strike

    def _find_put_wall(self, strikes: List[StrikeGEX]) -> float:
        """Find the strike with highest put OI (support)"""
        if not strikes:
            return 0

        max_put_oi_strike = max(strikes, key=lambda s: s.put_oi)
        return max_put_oi_strike.strike

    def _determine_dealer_positioning(self, total_net_gex: float) -> str:
        """Determine dealer gamma positioning"""
        # GEX in millions
        gex_millions = total_net_gex / 1_000_000

        if gex_millions > 50:
            return "LONG_GAMMA"
        elif gex_millions < -50:
            return "SHORT_GAMMA"
        else:
            return "NEUTRAL"

    def _determine_expected_volatility(self, total_net_gex: float, price: float) -> str:
        """Determine expected volatility based on GEX"""
        # Normalize GEX by price
        normalized_gex = total_net_gex / price if price > 0 else 0

        if normalized_gex > 1_000_000:  # Strong positive = low vol
            return "LOW"
        elif normalized_gex < -1_000_000:  # Strong negative = high vol
            return "HIGH"
        else:
            return "NORMAL"

    def _determine_bias(self, zero_gamma: float, price: float, net_gex: float) -> str:
        """Determine market bias from GEX positioning"""
        if price > zero_gamma and net_gex > 0:
            return "BULLISH"  # Price above zero gamma, dealers long gamma
        elif price < zero_gamma and net_gex < 0:
            return "BEARISH"  # Price below zero gamma, dealers short gamma
        else:
            return "NEUTRAL"

    def get_support_resistance(self, gex_data: GEXData) -> Dict:
        """Get support/resistance levels from GEX"""
        price = gex_data.underlying_price

        # Sort strikes by net GEX
        sorted_strikes = sorted(gex_data.strikes, key=lambda s: s.net_gex, reverse=True)

        # Resistance: strikes above price with high positive GEX
        resistance_levels = [
            s.strike for s in sorted_strikes
            if s.strike > price and s.net_gex > 0
        ][:3]

        # Support: strikes below price with high positive GEX (or high put OI)
        support_levels = [
            s.strike for s in gex_data.strikes
            if s.strike < price
        ]
        support_levels = sorted(support_levels, key=lambda s: next(
            (x.put_oi for x in gex_data.strikes if x.strike == s), 0
        ), reverse=True)[:3]

        return {
            "resistance": resistance_levels,
            "support": support_levels,
            "call_wall": gex_data.call_wall,
            "put_wall": gex_data.put_wall,
            "zero_gamma": gex_data.zero_gamma_level,
            "max_gamma": gex_data.max_gamma_strike,
        }

    def get_market_impact_forecast(self, gex_data: GEXData) -> Dict:
        """Forecast market impact based on GEX"""
        price = gex_data.underlying_price
        net_gex = gex_data.total_net_gex

        # Calculate expected move range
        # Higher gamma = lower expected move
        # Lower/negative gamma = higher expected move

        base_move = 1.0  # 1% base move

        if net_gex > 100:  # Strong positive GEX
            move_multiplier = 0.5
            interpretation = "Dealers are long gamma. Expect dampened moves and mean reversion."
        elif net_gex > 0:
            move_multiplier = 0.75
            interpretation = "Dealers are slightly long gamma. Some dampening expected."
        elif net_gex > -100:
            move_multiplier = 1.0
            interpretation = "Neutral gamma environment. Normal volatility expected."
        else:  # Strong negative GEX
            move_multiplier = 1.5
            interpretation = "Dealers are short gamma. Expect amplified moves and potential acceleration."

        expected_range = base_move * move_multiplier

        return {
            "current_price": price,
            "expected_move_pct": round(expected_range, 2),
            "expected_high": round(price * (1 + expected_range / 100), 2),
            "expected_low": round(price * (1 - expected_range / 100), 2),
            "gamma_environment": gex_data.dealer_positioning,
            "interpretation": interpretation,
            "key_levels": {
                "upside_target": gex_data.call_wall,
                "downside_support": gex_data.put_wall,
                "pivot": gex_data.zero_gamma_level,
            },
        }


# Singleton instance
_gex_analyzer: Optional[GEXAnalyzer] = None

def get_gex_analyzer() -> GEXAnalyzer:
    global _gex_analyzer
    if _gex_analyzer is None:
        _gex_analyzer = GEXAnalyzer()
    return _gex_analyzer
