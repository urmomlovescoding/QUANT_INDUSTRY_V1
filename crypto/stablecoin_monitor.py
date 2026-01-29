"""
Stablecoin Monitor Module
Track stablecoin pegs and detect depegging events.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class Stablecoin(Enum):
    """Tracked stablecoins."""
    USDT = "tether"
    USDC = "usd-coin"
    DAI = "dai"
    FRAX = "frax"
    TUSD = "true-usd"
    BUSD = "binance-usd"
    USDD = "usdd"
    LUSD = "liquity-usd"
    GUSD = "gemini-dollar"
    USDP = "paxos-standard"


class DepegSeverity(Enum):
    """Severity levels for depeg events."""
    NORMAL = "normal"      # < 0.1% deviation
    MINOR = "minor"        # 0.1% - 0.5%
    MODERATE = "moderate"  # 0.5% - 1%
    SEVERE = "severe"      # 1% - 3%
    CRITICAL = "critical"  # > 3%


@dataclass
class StablecoinPrice:
    """Stablecoin price data."""
    coin: Stablecoin
    price: Decimal
    deviation_pct: Decimal
    severity: DepegSeverity
    volume_24h: Decimal
    market_cap: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_depegged(self) -> bool:
        """Check if coin is significantly depegged (>0.5%)."""
        return abs(self.deviation_pct) > Decimal("0.5")


@dataclass
class DepegAlert:
    """Alert for depeg event."""
    coin: Stablecoin
    price: Decimal
    deviation_pct: Decimal
    severity: DepegSeverity
    direction: str  # "above" or "below"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class StablecoinMonitor:
    """
    Monitor stablecoin pegs and detect depegging events.
    
    Features:
    - Real-time price tracking for major stablecoins
    - Depeg detection with severity levels
    - Historical depeg pattern analysis
    - Alert generation for trading signals
    - Redemption flow monitoring
    
    Trading Signals:
    - Depeg below $0.99: Short opportunity or arbitrage
    - Depeg above $1.01: Long opportunity or arbitrage
    - Recovery signal: Mean reversion play
    """
    
    # API endpoints
    COINGECKO_API = "https://api.coingecko.com/api/v3"
    
    # Severity thresholds
    THRESHOLDS = {
        DepegSeverity.NORMAL: Decimal("0.001"),    # 0.1%
        DepegSeverity.MINOR: Decimal("0.005"),     # 0.5%
        DepegSeverity.MODERATE: Decimal("0.01"),   # 1%
        DepegSeverity.SEVERE: Decimal("0.03"),     # 3%
        DepegSeverity.CRITICAL: Decimal("0.05"),   # 5%
    }
    
    def __init__(self, alert_threshold: Decimal = Decimal("0.005")):
        self.alert_threshold = alert_threshold
        self._session: Optional[aiohttp.ClientSession] = None
        self._prices: Dict[Stablecoin, StablecoinPrice] = {}
        self._alerts: List[DepegAlert] = []
        self._price_history: Dict[Stablecoin, List[StablecoinPrice]] = {
            coin: [] for coin in Stablecoin
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_severity(self, deviation: Decimal) -> DepegSeverity:
        """Determine severity based on deviation."""
        abs_dev = abs(deviation)
        
        if abs_dev >= self.THRESHOLDS[DepegSeverity.CRITICAL]:
            return DepegSeverity.CRITICAL
        elif abs_dev >= self.THRESHOLDS[DepegSeverity.SEVERE]:
            return DepegSeverity.SEVERE
        elif abs_dev >= self.THRESHOLDS[DepegSeverity.MODERATE]:
            return DepegSeverity.MODERATE
        elif abs_dev >= self.THRESHOLDS[DepegSeverity.MINOR]:
            return DepegSeverity.MINOR
        else:
            return DepegSeverity.NORMAL
    
    async def fetch_prices(self) -> Dict[Stablecoin, StablecoinPrice]:
        """
        Fetch current prices for all stablecoins.
        
        Returns:
            Dict mapping stablecoin to price data
        """
        session = await self._get_session()
        
        coin_ids = ",".join(coin.value for coin in Stablecoin)
        url = f"{self.COINGECKO_API}/simple/price"
        params = {
            "ids": coin_ids,
            "vs_currencies": "usd",
            "include_24hr_vol": "true",
            "include_market_cap": "true"
        }
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
            
            prices = {}
            for coin in Stablecoin:
                if coin.value in data:
                    coin_data = data[coin.value]
                    price = Decimal(str(coin_data.get("usd", 1)))
                    deviation = (price - Decimal("1")) * 100  # Percentage
                    
                    prices[coin] = StablecoinPrice(
                        coin=coin,
                        price=price,
                        deviation_pct=deviation,
                        severity=self._get_severity(deviation / 100),
                        volume_24h=Decimal(str(coin_data.get("usd_24h_vol", 0))),
                        market_cap=Decimal(str(coin_data.get("usd_market_cap", 0)))
                    )
            
            # Update caches
            self._prices = prices
            for coin, price_data in prices.items():
                self._price_history[coin].append(price_data)
                # Keep last 1000 data points
                if len(self._price_history[coin]) > 1000:
                    self._price_history[coin] = self._price_history[coin][-1000:]
            
            logger.info(f"Fetched prices for {len(prices)} stablecoins")
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching stablecoin prices: {e}")
            return {}
    
    def detect_depegs(
        self,
        prices: Optional[Dict[Stablecoin, StablecoinPrice]] = None
    ) -> List[DepegAlert]:
        """
        Detect depegging events and generate alerts.
        
        Args:
            prices: Price data (uses cached if not provided)
        
        Returns:
            List of depeg alerts
        """
        prices = prices or self._prices
        new_alerts = []
        
        for coin, price_data in prices.items():
            if abs(price_data.deviation_pct) >= float(self.alert_threshold * 100):
                direction = "above" if price_data.deviation_pct > 0 else "below"
                
                # Check if we already have an active alert for this coin
                existing = next(
                    (a for a in self._alerts if a.coin == coin and not a.resolved),
                    None
                )
                
                if not existing:
                    alert = DepegAlert(
                        coin=coin,
                        price=price_data.price,
                        deviation_pct=price_data.deviation_pct,
                        severity=price_data.severity,
                        direction=direction
                    )
                    new_alerts.append(alert)
                    self._alerts.append(alert)
                    
                    logger.warning(
                        f"DEPEG ALERT: {coin.name} at ${price_data.price} "
                        f"({price_data.deviation_pct:+.3f}%) - {price_data.severity.value}"
                    )
        
        # Check for resolved depegs
        for alert in self._alerts:
            if not alert.resolved and alert.coin in prices:
                current_price = prices[alert.coin]
                if abs(current_price.deviation_pct) < float(self.alert_threshold * 100):
                    alert.resolved = True
                    alert.resolved_at = datetime.utcnow()
                    logger.info(f"DEPEG RESOLVED: {alert.coin.name} back to ${current_price.price}")
        
        return new_alerts
    
    def get_trading_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals from depeg events.
        
        Returns:
            List of trading signals
        """
        signals = []
        
        for coin, price_data in self._prices.items():
            if price_data.is_depegged:
                # Below peg - potential arbitrage or long for recovery
                if price_data.price < Decimal("0.995"):
                    signals.append({
                        "coin": coin.name,
                        "signal": "BUY_FOR_RECOVERY",
                        "price": float(price_data.price),
                        "deviation_pct": float(price_data.deviation_pct),
                        "severity": price_data.severity.value,
                        "reasoning": f"Trading below peg at ${price_data.price}. Mean reversion opportunity.",
                        "risk": "High if fundamental depeg (e.g., USDC March 2023)",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                # Above peg - potential short or arbitrage
                elif price_data.price > Decimal("1.005"):
                    signals.append({
                        "coin": coin.name,
                        "signal": "SELL_FOR_REVERSION",
                        "price": float(price_data.price),
                        "deviation_pct": float(price_data.deviation_pct),
                        "severity": price_data.severity.value,
                        "reasoning": f"Trading above peg at ${price_data.price}. Mean reversion opportunity.",
                        "risk": "Lower risk than below-peg trades",
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        return signals
    
    def get_historical_depegs(
        self,
        coin: Optional[Stablecoin] = None,
        days: int = 30
    ) -> List[DepegAlert]:
        """
        Get historical depeg events.
        
        Args:
            coin: Filter by specific coin
            days: Lookback period
        
        Returns:
            List of historical depeg alerts
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        alerts = [a for a in self._alerts if a.timestamp >= cutoff]
        
        if coin:
            alerts = [a for a in alerts if a.coin == coin]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current status summary of all stablecoins."""
        if not self._prices:
            return {"error": "No data. Call fetch_prices first."}
        
        depegged = [
            {
                "coin": coin.name,
                "price": float(data.price),
                "deviation_pct": float(data.deviation_pct),
                "severity": data.severity.value
            }
            for coin, data in self._prices.items()
            if data.is_depegged
        ]
        
        healthy = [
            {
                "coin": coin.name,
                "price": float(data.price),
                "deviation_pct": float(data.deviation_pct)
            }
            for coin, data in self._prices.items()
            if not data.is_depegged
        ]
        
        active_alerts = [a for a in self._alerts if not a.resolved]
        
        return {
            "total_tracked": len(self._prices),
            "healthy_count": len(healthy),
            "depegged_count": len(depegged),
            "depegged_coins": depegged,
            "healthy_coins": healthy,
            "active_alerts": len(active_alerts),
            "total_market_cap": sum(float(d.market_cap) for d in self._prices.values()),
            "total_24h_volume": sum(float(d.volume_24h) for d in self._prices.values()),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def monitor_loop(
        self,
        interval_seconds: int = 60,
        callback: Optional[callable] = None
    ):
        """
        Continuous monitoring loop.
        
        Args:
            interval_seconds: Polling interval
            callback: Function to call on depeg detection
        """
        logger.info(f"Starting stablecoin monitor (interval: {interval_seconds}s)")
        
        while True:
            try:
                prices = await self.fetch_prices()
                alerts = self.detect_depegs(prices)
                
                if alerts and callback:
                    for alert in alerts:
                        callback(alert)
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(interval_seconds)
