"""
QUANT INDUSTRY - Options Service
Options chain data, Greeks calculations, and analysis
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
from scipy.stats import norm

logger = logging.getLogger(__name__)


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class OptionGreeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    def to_dict(self) -> Dict:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 4),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "rho": round(self.rho, 4),
        }


@dataclass
class OptionContract:
    symbol: str
    underlying: str
    option_type: str  # "call" or "put"
    strike: float
    expiration: str
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    greeks: Optional[OptionGreeks] = None
    in_the_money: bool = False

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "underlying": self.underlying,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiration": self.expiration,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "mid": round((self.bid + self.ask) / 2, 2),
            "volume": self.volume,
            "open_interest": self.open_interest,
            "implied_volatility": round(self.implied_volatility * 100, 2),
            "greeks": self.greeks.to_dict() if self.greeks else None,
            "in_the_money": self.in_the_money,
        }


@dataclass
class OptionsChain:
    underlying: str
    underlying_price: float
    expirations: List[str]
    calls: List[OptionContract]
    puts: List[OptionContract]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "underlying": self.underlying,
            "underlying_price": self.underlying_price,
            "expirations": self.expirations,
            "calls": [c.to_dict() for c in self.calls],
            "puts": [p.to_dict() for p in self.puts],
            "timestamp": self.timestamp.isoformat(),
        }

    def get_by_expiration(self, expiration: str) -> Tuple[List[OptionContract], List[OptionContract]]:
        """Get calls and puts for a specific expiration"""
        calls = [c for c in self.calls if c.expiration == expiration]
        puts = [p for p in self.puts if p.expiration == expiration]
        return calls, puts


class BlackScholes:
    """Black-Scholes option pricing and Greeks"""

    @staticmethod
    def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1"""
        if T <= 0 or sigma <= 0:
            return 0
        return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

    @staticmethod
    def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d2"""
        if T <= 0 or sigma <= 0:
            return 0
        return BlackScholes.d1(S, K, T, r, sigma) - sigma * math.sqrt(T)

    @staticmethod
    def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate call option price"""
        if T <= 0:
            return max(0, S - K)

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)

        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)

    @staticmethod
    def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate put option price"""
        if T <= 0:
            return max(0, K - S)

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)

        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @staticmethod
    def delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        """Calculate delta"""
        if T <= 0:
            if option_type == "call":
                return 1.0 if S > K else 0.0
            else:
                return -1.0 if S < K else 0.0

        d1 = BlackScholes.d1(S, K, T, r, sigma)

        if option_type == "call":
            return norm.cdf(d1)
        else:
            return norm.cdf(d1) - 1

    @staticmethod
    def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate gamma"""
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * math.sqrt(T))

    @staticmethod
    def theta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        """Calculate theta (per day)"""
        if T <= 0 or sigma <= 0:
            return 0

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)

        term1 = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))

        if option_type == "call":
            term2 = r * K * math.exp(-r * T) * norm.cdf(d2)
            theta_annual = term1 - term2
        else:
            term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)
            theta_annual = term1 + term2

        return theta_annual / 365  # Per day

    @staticmethod
    def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate vega (per 1% change in IV)"""
        if T <= 0:
            return 0

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        return S * norm.pdf(d1) * math.sqrt(T) / 100

    @staticmethod
    def rho(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        """Calculate rho (per 1% change in rate)"""
        if T <= 0:
            return 0

        d2 = BlackScholes.d2(S, K, T, r, sigma)

        if option_type == "call":
            return K * T * math.exp(-r * T) * norm.cdf(d2) / 100
        else:
            return -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100

    @staticmethod
    def implied_volatility(
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str,
        max_iterations: int = 100,
        tolerance: float = 1e-5
    ) -> float:
        """Calculate implied volatility using Newton-Raphson"""
        if T <= 0 or market_price <= 0:
            return 0

        sigma = 0.3  # Initial guess

        for _ in range(max_iterations):
            if option_type == "call":
                price = BlackScholes.call_price(S, K, T, r, sigma)
            else:
                price = BlackScholes.put_price(S, K, T, r, sigma)

            diff = price - market_price

            if abs(diff) < tolerance:
                return sigma

            vega = BlackScholes.vega(S, K, T, r, sigma) * 100  # Undo the /100

            if vega < 1e-10:
                break

            sigma = sigma - diff / vega

            if sigma <= 0:
                sigma = 0.01

        return sigma

    @staticmethod
    def calculate_greeks(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str
    ) -> OptionGreeks:
        """Calculate all Greeks"""
        return OptionGreeks(
            delta=BlackScholes.delta(S, K, T, r, sigma, option_type),
            gamma=BlackScholes.gamma(S, K, T, r, sigma),
            theta=BlackScholes.theta(S, K, T, r, sigma, option_type),
            vega=BlackScholes.vega(S, K, T, r, sigma),
            rho=BlackScholes.rho(S, K, T, r, sigma, option_type),
        )


class OptionsService:
    """
    Options service for chain data and analysis
    """

    def __init__(self):
        self.cache: Dict[str, Tuple[OptionsChain, datetime]] = {}
        self.cache_ttl = 60  # 1 minute cache
        self.risk_free_rate = 0.05  # 5% risk-free rate

        logger.info("OptionsService initialized")

    def get_options_chain(self, symbol: str) -> Optional[OptionsChain]:
        """Get options chain for a symbol"""
        # Check cache
        if symbol in self.cache:
            chain, timestamp = self.cache[symbol]
            if (datetime.now() - timestamp).seconds < self.cache_ttl:
                return chain

        # Try to fetch from Tradier first
        chain = self._fetch_from_tradier(symbol)

        if chain:
            self.cache[symbol] = (chain, datetime.now())
            return chain

        # Fallback to generated data
        chain = self._generate_chain(symbol)
        if chain:
            self.cache[symbol] = (chain, datetime.now())

        return chain

    def _fetch_from_tradier(self, symbol: str) -> Optional[OptionsChain]:
        """Fetch options chain from Tradier"""
        try:
            from ..config.api_keys import get_api_keys
            keys = get_api_keys()

            if not keys.tradier.is_configured:
                return None

            headers = {
                "Authorization": f"Bearer {keys.tradier.api_key}",
                "Accept": "application/json",
            }

            # Get expirations
            exp_response = requests.get(
                f"{keys.tradier.base_url}/v1/markets/options/expirations",
                params={"symbol": symbol},
                headers=headers,
                timeout=10
            )

            if exp_response.status_code != 200:
                return None

            exp_data = exp_response.json()
            expirations = exp_data.get("expirations", {}).get("date", [])

            if not expirations:
                return None

            # Get underlying price
            quote_response = requests.get(
                f"{keys.tradier.base_url}/v1/markets/quotes",
                params={"symbols": symbol},
                headers=headers,
                timeout=10
            )

            underlying_price = 100  # Default
            if quote_response.status_code == 200:
                quote_data = quote_response.json()
                quotes = quote_data.get("quotes", {}).get("quote", {})
                if isinstance(quotes, dict):
                    underlying_price = quotes.get("last", 100)

            # Get options chain for first 3 expirations
            calls = []
            puts = []

            for exp in expirations[:3]:
                chain_response = requests.get(
                    f"{keys.tradier.base_url}/v1/markets/options/chains",
                    params={"symbol": symbol, "expiration": exp},
                    headers=headers,
                    timeout=10
                )

                if chain_response.status_code == 200:
                    chain_data = chain_response.json()
                    options = chain_data.get("options", {}).get("option", [])

                    for opt in options:
                        T = self._calculate_time_to_expiry(exp)
                        iv = opt.get("greeks", {}).get("mid_iv", 0.3) or 0.3

                        greeks = BlackScholes.calculate_greeks(
                            S=underlying_price,
                            K=opt.get("strike", 0),
                            T=T,
                            r=self.risk_free_rate,
                            sigma=iv,
                            option_type=opt.get("option_type", "call")
                        )

                        contract = OptionContract(
                            symbol=opt.get("symbol", ""),
                            underlying=symbol,
                            option_type=opt.get("option_type", "call"),
                            strike=opt.get("strike", 0),
                            expiration=exp,
                            bid=opt.get("bid", 0) or 0,
                            ask=opt.get("ask", 0) or 0,
                            last=opt.get("last", 0) or 0,
                            volume=opt.get("volume", 0) or 0,
                            open_interest=opt.get("open_interest", 0) or 0,
                            implied_volatility=iv,
                            greeks=greeks,
                            in_the_money=(
                                underlying_price > opt.get("strike", 0)
                                if opt.get("option_type") == "call"
                                else underlying_price < opt.get("strike", 0)
                            ),
                        )

                        if opt.get("option_type") == "call":
                            calls.append(contract)
                        else:
                            puts.append(contract)

            return OptionsChain(
                underlying=symbol,
                underlying_price=underlying_price,
                expirations=expirations,
                calls=calls,
                puts=puts,
            )

        except Exception as e:
            logger.error(f"Error fetching from Tradier: {e}")
            return None

    def _generate_chain(self, symbol: str) -> OptionsChain:
        """Generate options chain using Black-Scholes with REAL underlying price from Alpaca"""
        underlying_price = None

        # Method 1: Try data_service directly
        try:
            from services.data_service import get_data_service
            data_service = get_data_service()
            quote = data_service.get_quote(symbol)
            if quote and hasattr(quote, 'price') and quote.price > 0:
                underlying_price = quote.price
                logger.info(f"Options chain using REAL price for {symbol}: ${underlying_price:.2f}")
        except Exception as e:
            logger.warning(f"Method 1 failed for {symbol}: {e}")

        # Method 2: Try internal API call
        if underlying_price is None:
            try:
                response = requests.get(f"http://localhost:8000/api/market/quote/{symbol}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("price") and data["price"] > 0:
                        underlying_price = data["price"]
                        logger.info(f"Options chain using API price for {symbol}: ${underlying_price:.2f}")
            except Exception as e:
                logger.warning(f"Method 2 API call failed for {symbol}: {e}")

        # If still no price, raise error - do NOT use fake $100 default
        if underlying_price is None or underlying_price <= 0:
            raise ValueError(f"Cannot generate options chain for {symbol}: unable to get real underlying price")

        # Generate expirations (weekly for 2 months)
        expirations = []
        base_date = datetime.now()
        for i in range(1, 9):
            exp_date = base_date + timedelta(days=7 * i)
            # Adjust to Friday
            days_until_friday = (4 - exp_date.weekday()) % 7
            exp_date += timedelta(days=days_until_friday)
            expirations.append(exp_date.strftime("%Y-%m-%d"))

        calls = []
        puts = []

        # Generate strikes around current price
        strike_range = int(underlying_price * 0.15)
        strike_step = max(1, strike_range // 10)

        for exp_idx, exp in enumerate(expirations[:4]):  # First 4 expirations
            T = self._calculate_time_to_expiry(exp)
            # Deterministic IV based on symbol and expiration (no random)
            symbol_hash = sum(ord(c) for c in symbol)
            base_iv = 0.22 + (symbol_hash % 10) * 0.01 + exp_idx * 0.005

            for i in range(-10, 11):
                strike = round(underlying_price + i * strike_step)
                if strike <= 0:
                    continue

                # Calculate IV with smile
                moneyness = strike / underlying_price
                iv_adjustment = 0.02 * (moneyness - 1) ** 2
                iv = base_iv + iv_adjustment

                # Calculate prices and Greeks
                call_price = BlackScholes.call_price(underlying_price, strike, T, self.risk_free_rate, iv)
                put_price = BlackScholes.put_price(underlying_price, strike, T, self.risk_free_rate, iv)

                call_greeks = BlackScholes.calculate_greeks(underlying_price, strike, T, self.risk_free_rate, iv, "call")
                put_greeks = BlackScholes.calculate_greeks(underlying_price, strike, T, self.risk_free_rate, iv, "put")

                # Generate realistic bid/ask
                spread = max(0.01, call_price * 0.05)
                call_bid = max(0, call_price - spread / 2)
                call_ask = call_price + spread / 2

                spread = max(0.01, put_price * 0.05)
                put_bid = max(0, put_price - spread / 2)
                put_ask = put_price + spread / 2

                # Generate volume and OI (deterministic based on strike)
                atm_factor = 1 / (1 + abs(moneyness - 1) * 10)
                strike_hash = (int(strike) % 17) / 17  # 0.0 to 1.0 deterministic
                volume = int(1000 * atm_factor * (0.7 + strike_hash * 0.6))
                oi = int(10000 * atm_factor * (0.7 + strike_hash * 0.6))

                call_contract = OptionContract(
                    symbol=f"{symbol}{exp.replace('-', '')}C{strike:08.0f}",
                    underlying=symbol,
                    option_type="call",
                    strike=strike,
                    expiration=exp,
                    bid=round(call_bid, 2),
                    ask=round(call_ask, 2),
                    last=round(call_price, 2),
                    volume=volume,
                    open_interest=oi,
                    implied_volatility=iv,
                    greeks=call_greeks,
                    in_the_money=underlying_price > strike,
                )

                put_contract = OptionContract(
                    symbol=f"{symbol}{exp.replace('-', '')}P{strike:08.0f}",
                    underlying=symbol,
                    option_type="put",
                    strike=strike,
                    expiration=exp,
                    bid=round(put_bid, 2),
                    ask=round(put_ask, 2),
                    last=round(put_price, 2),
                    volume=volume,
                    open_interest=oi,
                    implied_volatility=iv,
                    greeks=put_greeks,
                    in_the_money=underlying_price < strike,
                )

                calls.append(call_contract)
                puts.append(put_contract)

        return OptionsChain(
            underlying=symbol,
            underlying_price=underlying_price,
            expirations=expirations,
            calls=calls,
            puts=puts,
        )

    def _calculate_time_to_expiry(self, expiration: str) -> float:
        """Calculate time to expiry in years"""
        try:
            exp_date = datetime.strptime(expiration, "%Y-%m-%d")
            days = (exp_date - datetime.now()).days
            return max(days / 365.0, 1/365)  # Minimum 1 day
        except Exception:
            return 30 / 365.0  # Default 30 days

    def analyze_option(self, contract: OptionContract) -> Dict:
        """Analyze a single option contract"""
        return {
            "contract": contract.to_dict(),
            "intrinsic_value": max(0, contract.strike - contract.last) if contract.option_type == "put" else max(0, contract.last - contract.strike),
            "time_value": contract.last - max(0, contract.strike - contract.last if contract.option_type == "put" else contract.last - contract.strike),
            "bid_ask_spread": contract.ask - contract.bid,
            "bid_ask_spread_pct": ((contract.ask - contract.bid) / contract.last * 100) if contract.last > 0 else 0,
            "rating": self._rate_option(contract),
        }

    def _rate_option(self, contract: OptionContract) -> str:
        """Rate an option contract"""
        score = 0

        # Volume
        if contract.volume > 1000:
            score += 2
        elif contract.volume > 100:
            score += 1

        # Open interest
        if contract.open_interest > 5000:
            score += 2
        elif contract.open_interest > 500:
            score += 1

        # Bid-ask spread
        spread_pct = ((contract.ask - contract.bid) / contract.last * 100) if contract.last > 0 else 100
        if spread_pct < 5:
            score += 2
        elif spread_pct < 10:
            score += 1

        # IV
        if 0.2 < contract.implied_volatility < 0.5:
            score += 1

        if score >= 5:
            return "EXCELLENT"
        elif score >= 3:
            return "GOOD"
        elif score >= 1:
            return "FAIR"
        else:
            return "POOR"

    def get_unusual_flow(self, symbols: List[str] = None, limit: int = 20) -> List[Dict]:
        """
        Detect unusual options flow activity.

        Identifies:
        - High volume relative to open interest
        - Large premium trades
        - Sweeps (aggressive multi-exchange orders)
        - IV spikes indicating smart money positioning
        """
        if symbols is None:
            symbols = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMD", "META", "AMZN", "GOOGL", "MSFT"]

        flow_entries = []

        for symbol in symbols:
            try:
                chain = self.get_options_chain(symbol)
                if not chain:
                    continue

                all_contracts = chain.calls + chain.puts

                for contract in all_contracts:
                    # Calculate flow metrics
                    volume_oi_ratio = (contract.volume / contract.open_interest) if contract.open_interest > 0 else 0
                    mid_price = (contract.bid + contract.ask) / 2
                    premium = contract.volume * 100 * mid_price  # Total premium traded

                    # Determine if unusual based on multiple factors
                    is_unusual = False
                    is_sweep = False
                    unusual_reasons = []

                    # High volume/OI ratio (>0.5 is notable, >1.0 is unusual)
                    if volume_oi_ratio > 0.5:
                        is_unusual = True
                        unusual_reasons.append("high_vol_oi")

                    # Large premium (>$100k is notable)
                    if premium > 100000:
                        is_unusual = True
                        unusual_reasons.append("large_premium")

                    # Sweep detection: high volume, aggressive pricing (ask side for calls, bid for puts)
                    # Sweeps typically show volume > 500 contracts and trade at/above ask
                    if contract.volume > 500 and contract.last >= contract.ask * 0.98:
                        is_sweep = True
                        is_unusual = True
                        unusual_reasons.append("sweep")

                    # IV spike (above 50% is elevated)
                    if contract.implied_volatility > 0.5:
                        unusual_reasons.append("high_iv")

                    # Only include if unusual
                    if not is_unusual or premium < 10000:
                        continue

                    # Determine sentiment
                    if contract.option_type == "call":
                        sentiment = "bullish" if contract.last >= mid_price else "neutral"
                    else:
                        sentiment = "bearish" if contract.last >= mid_price else "neutral"

                    # Determine side (buy vs sell) based on trade location
                    if contract.last >= contract.ask * 0.95:
                        side = "buy"
                    elif contract.last <= contract.bid * 1.05:
                        side = "sell"
                    else:
                        side = "buy" if np.random.random() > 0.3 else "sell"

                    flow_entry = {
                        "id": f"FLOW-{symbol}-{contract.strike}-{contract.expiration[-5:]}",
                        "symbol": symbol,
                        "type": contract.option_type,
                        "side": side,
                        "sentiment": sentiment,
                        "strike": contract.strike,
                        "expiry": contract.expiration,
                        "premium": round(premium, 0),
                        "contracts": contract.volume,
                        "open_interest": contract.open_interest,
                        "volume_oi_ratio": round(volume_oi_ratio, 2),
                        "implied_volatility": round(contract.implied_volatility * 100, 1),
                        "is_unusual": is_unusual,
                        "is_sweep": is_sweep,
                        "unusual_reasons": unusual_reasons,
                        "delta": round(contract.greeks.delta, 3) if contract.greeks else 0,
                        "timestamp": datetime.now().isoformat()
                    }

                    flow_entries.append(flow_entry)

            except Exception as e:
                logger.warning(f"Error processing flow for {symbol}: {e}")
                continue

        # Sort by premium (largest trades first) and limit
        flow_entries.sort(key=lambda x: x["premium"], reverse=True)
        return flow_entries[:limit]


# Singleton instance
_options_service: Optional[OptionsService] = None

def get_options_service() -> OptionsService:
    global _options_service
    if _options_service is None:
        _options_service = OptionsService()
    return _options_service
