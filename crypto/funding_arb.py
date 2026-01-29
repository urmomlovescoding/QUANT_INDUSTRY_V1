"""
Funding Rate Arbitrage Module
Delta-neutral perpetual funding rate arbitrage.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class Exchange(Enum):
    """Supported perpetual exchanges."""
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    DYDX = "dydx"
    BITGET = "bitget"
    GMX = "gmx"


@dataclass
class FundingRate:
    """Funding rate data for a perpetual contract."""
    exchange: Exchange
    symbol: str
    rate: Decimal  # Funding rate (e.g., 0.0001 = 0.01%)
    predicted_rate: Optional[Decimal] = None
    next_funding_time: Optional[datetime] = None
    interval_hours: int = 8
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def annualized_rate(self) -> Decimal:
        """Calculate annualized funding rate."""
        periods_per_year = Decimal(365 * 24 / self.interval_hours)
        return self.rate * periods_per_year
    
    @property
    def is_positive(self) -> bool:
        """True if longs pay shorts."""
        return self.rate > 0


@dataclass
class ArbOpportunity:
    """Funding rate arbitrage opportunity."""
    long_exchange: Exchange
    short_exchange: Exchange
    symbol: str
    spread: Decimal  # Rate difference
    annualized_spread: Decimal
    long_rate: FundingRate
    short_rate: FundingRate
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_profitable(self) -> bool:
        """Check if spread is profitable after fees."""
        # Assume ~0.02% round-trip fees per side
        min_spread = Decimal("0.0004")  # 0.04%
        return abs(self.spread) > min_spread


class FundingRateArbitrage:
    """
    Funding rate arbitrage strategy.
    
    Strategy:
    - Monitor funding rates across exchanges
    - When spread > threshold:
      - Go long on exchange with negative funding (get paid)
      - Go short on exchange with positive funding (get paid)
    - Delta neutral: no directional exposure
    - Profit from funding payments
    
    Features:
    - Multi-exchange monitoring
    - Real-time funding rate tracking
    - Spread calculation and alerts
    - Position sizing with risk limits
    - Basis tracking (perp vs spot)
    """
    
    # API endpoints
    ENDPOINTS = {
        Exchange.BINANCE: "https://fapi.binance.com",
        Exchange.BYBIT: "https://api.bybit.com",
        Exchange.OKX: "https://www.okx.com",
        Exchange.DYDX: "https://api.dydx.exchange",
    }
    
    # Minimum spread to consider (annualized)
    MIN_SPREAD_THRESHOLD = Decimal("0.05")  # 5% annualized
    
    def __init__(
        self,
        api_keys: Optional[Dict[Exchange, Dict[str, str]]] = None,
        max_position_usd: Decimal = Decimal("100000"),
        max_leverage: Decimal = Decimal("3")
    ):
        self.api_keys = api_keys or {}
        self.max_position_usd = max_position_usd
        self.max_leverage = max_leverage
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._rates_cache: Dict[str, FundingRate] = {}
        self._opportunities: List[ArbOpportunity] = []
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def fetch_funding_rate(
        self,
        exchange: Exchange,
        symbol: str = "BTCUSDT"
    ) -> Optional[FundingRate]:
        """
        Fetch current funding rate from exchange.
        
        Args:
            exchange: Exchange to query
            symbol: Trading pair symbol
        
        Returns:
            FundingRate object or None
        """
        session = await self._get_session()
        
        try:
            if exchange == Exchange.BINANCE:
                url = f"{self.ENDPOINTS[exchange]}/fapi/v1/premiumIndex"
                params = {"symbol": symbol}
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    return FundingRate(
                        exchange=exchange,
                        symbol=symbol,
                        rate=Decimal(data['lastFundingRate']),
                        predicted_rate=Decimal(data.get('predictedFundingRate', data['lastFundingRate'])),
                        next_funding_time=datetime.fromtimestamp(int(data['nextFundingTime']) / 1000),
                        interval_hours=8
                    )
            
            elif exchange == Exchange.BYBIT:
                url = f"{self.ENDPOINTS[exchange]}/v5/market/tickers"
                params = {"category": "linear", "symbol": symbol}
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    if data['result']['list']:
                        ticker = data['result']['list'][0]
                        return FundingRate(
                            exchange=exchange,
                            symbol=symbol,
                            rate=Decimal(ticker['fundingRate']),
                            next_funding_time=datetime.fromtimestamp(int(ticker['nextFundingTime']) / 1000),
                            interval_hours=8
                        )
            
            elif exchange == Exchange.OKX:
                url = f"{self.ENDPOINTS[exchange]}/api/v5/public/funding-rate"
                params = {"instId": symbol.replace("USDT", "-USDT-SWAP")}
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    if data['data']:
                        rate_data = data['data'][0]
                        return FundingRate(
                            exchange=exchange,
                            symbol=symbol,
                            rate=Decimal(rate_data['fundingRate']),
                            next_funding_time=datetime.fromtimestamp(int(rate_data['nextFundingTime']) / 1000),
                            interval_hours=8
                        )
            
            # Add more exchanges as needed
            
        except Exception as e:
            logger.error(f"Error fetching funding rate from {exchange.value}: {e}")
        
        return None
    
    async def fetch_all_funding_rates(
        self,
        symbol: str = "BTCUSDT"
    ) -> Dict[Exchange, FundingRate]:
        """
        Fetch funding rates from all supported exchanges.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Dict mapping exchange to funding rate
        """
        tasks = [
            self.fetch_funding_rate(exchange, symbol)
            for exchange in Exchange
            if exchange in self.ENDPOINTS
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        rates = {}
        for exchange, result in zip(self.ENDPOINTS.keys(), results):
            if isinstance(result, FundingRate):
                rates[exchange] = result
                cache_key = f"{exchange.value}:{symbol}"
                self._rates_cache[cache_key] = result
        
        logger.info(f"Fetched {len(rates)} funding rates for {symbol}")
        return rates
    
    def find_arbitrage_opportunities(
        self,
        rates: Dict[Exchange, FundingRate]
    ) -> List[ArbOpportunity]:
        """
        Find arbitrage opportunities from funding rate spread.
        
        Args:
            rates: Dict of exchange to funding rate
        
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        exchanges = list(rates.keys())
        
        for i, ex1 in enumerate(exchanges):
            for ex2 in exchanges[i+1:]:
                rate1 = rates[ex1]
                rate2 = rates[ex2]
                
                spread = rate1.rate - rate2.rate
                
                if rate1.rate > rate2.rate:
                    # Short ex1, long ex2
                    opp = ArbOpportunity(
                        long_exchange=ex2,
                        short_exchange=ex1,
                        symbol=rate1.symbol,
                        spread=abs(spread),
                        annualized_spread=abs(spread) * Decimal(365 * 3),  # 3x daily
                        long_rate=rate2,
                        short_rate=rate1
                    )
                else:
                    # Short ex2, long ex1
                    opp = ArbOpportunity(
                        long_exchange=ex1,
                        short_exchange=ex2,
                        symbol=rate1.symbol,
                        spread=abs(spread),
                        annualized_spread=abs(spread) * Decimal(365 * 3),
                        long_rate=rate1,
                        short_rate=rate2
                    )
                
                if opp.annualized_spread >= self.MIN_SPREAD_THRESHOLD:
                    opportunities.append(opp)
        
        # Sort by spread (best first)
        opportunities.sort(key=lambda x: x.annualized_spread, reverse=True)
        self._opportunities = opportunities
        
        return opportunities
    
    async def scan_opportunities(
        self,
        symbols: List[str] = None
    ) -> List[ArbOpportunity]:
        """
        Scan all markets for arbitrage opportunities.
        
        Args:
            symbols: List of symbols to scan
        
        Returns:
            All found opportunities sorted by profitability
        """
        symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        
        all_opportunities = []
        
        for symbol in symbols:
            rates = await self.fetch_all_funding_rates(symbol)
            opps = self.find_arbitrage_opportunities(rates)
            all_opportunities.extend(opps)
        
        # Sort by annualized spread
        all_opportunities.sort(key=lambda x: x.annualized_spread, reverse=True)
        
        logger.info(f"Found {len(all_opportunities)} arb opportunities across {len(symbols)} symbols")
        return all_opportunities
    
    def calculate_position_size(
        self,
        opportunity: ArbOpportunity,
        account_balance: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate optimal position size for arbitrage.
        
        Args:
            opportunity: Arb opportunity
            account_balance: Available balance
        
        Returns:
            Position sizes for each leg
        """
        # Max position based on account balance and leverage
        max_notional = min(
            self.max_position_usd,
            account_balance * self.max_leverage
        )
        
        # Scale by spread attractiveness
        spread_factor = min(Decimal("1"), opportunity.annualized_spread / Decimal("0.20"))
        
        position_size = max_notional * spread_factor
        
        return {
            "long_size_usd": position_size,
            "short_size_usd": position_size,
            "long_exchange": opportunity.long_exchange.value,
            "short_exchange": opportunity.short_exchange.value,
            "expected_annual_return": float(opportunity.annualized_spread),
            "leverage_used": float(position_size / account_balance) if account_balance > 0 else 0
        }
    
    def calculate_basis(
        self,
        perp_price: Decimal,
        spot_price: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate basis between perpetual and spot.
        
        Args:
            perp_price: Perpetual contract price
            spot_price: Spot price
        
        Returns:
            Basis metrics
        """
        basis = perp_price - spot_price
        basis_pct = (basis / spot_price) * 100
        
        return {
            "basis_usd": float(basis),
            "basis_pct": float(basis_pct),
            "perp_premium": perp_price > spot_price,
            "annualized_basis": float(basis_pct * 365),  # Simple annualization
        }
    
    def get_current_rates_summary(self) -> Dict[str, Any]:
        """Get summary of current funding rates."""
        if not self._rates_cache:
            return {"error": "No rates cached. Call fetch_all_funding_rates first."}
        
        rates_list = []
        for key, rate in self._rates_cache.items():
            rates_list.append({
                "exchange": rate.exchange.value,
                "symbol": rate.symbol,
                "rate": float(rate.rate),
                "annualized": float(rate.annualized_rate),
                "direction": "longs pay" if rate.is_positive else "shorts pay"
            })
        
        return {
            "rates": sorted(rates_list, key=lambda x: x['rate']),
            "best_long": min(rates_list, key=lambda x: x['rate']),
            "best_short": max(rates_list, key=lambda x: x['rate']),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_opportunities_summary(self) -> Dict[str, Any]:
        """Get summary of current arbitrage opportunities."""
        if not self._opportunities:
            return {"opportunities": [], "message": "No opportunities found"}
        
        return {
            "opportunities": [
                {
                    "symbol": opp.symbol,
                    "long_exchange": opp.long_exchange.value,
                    "short_exchange": opp.short_exchange.value,
                    "spread": float(opp.spread),
                    "annualized_spread_pct": float(opp.annualized_spread * 100),
                    "is_profitable": opp.is_profitable
                }
                for opp in self._opportunities[:10]
            ],
            "total_opportunities": len(self._opportunities),
            "best_spread_pct": float(self._opportunities[0].annualized_spread * 100) if self._opportunities else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
