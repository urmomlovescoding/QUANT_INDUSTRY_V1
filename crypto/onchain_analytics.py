"""
On-Chain Analytics Module
Whale tracking, DEX flows, smart money analysis.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import json

logger = logging.getLogger(__name__)


class Chain(Enum):
    """Supported blockchain networks."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    SOLANA = "solana"


class SignalType(Enum):
    """Types of on-chain signals."""
    WHALE_ACCUMULATION = "whale_accumulation"
    WHALE_DISTRIBUTION = "whale_distribution"
    EXCHANGE_INFLOW = "exchange_inflow"
    EXCHANGE_OUTFLOW = "exchange_outflow"
    DEX_VOLUME_SPIKE = "dex_volume_spike"
    SMART_MONEY_BUY = "smart_money_buy"
    SMART_MONEY_SELL = "smart_money_sell"
    NETWORK_ACTIVITY_SURGE = "network_activity_surge"


@dataclass
class WhaleWallet:
    """Whale wallet information."""
    address: str
    chain: Chain
    balance_usd: Decimal
    tokens: Dict[str, Decimal] = field(default_factory=dict)
    last_activity: Optional[datetime] = None
    label: Optional[str] = None  # Known entity name
    is_smart_money: bool = False


@dataclass
class OnChainSignal:
    """On-chain trading signal."""
    signal_type: SignalType
    chain: Chain
    token: str
    strength: float  # 0-1
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5


class OnChainAnalytics:
    """
    On-chain analytics for crypto alpha generation.
    
    Features:
    - Whale wallet tracking (>$10M holdings)
    - DEX flow analysis (Uniswap, Sushi, etc.)
    - Smart money tracking
    - Exchange inflow/outflow monitoring
    - Network metrics (active addresses, tx volume)
    """
    
    # Whale threshold in USD
    WHALE_THRESHOLD = Decimal("10000000")  # $10M
    
    # API endpoints for different data providers
    API_ENDPOINTS = {
        "etherscan": "https://api.etherscan.io/api",
        "dune": "https://api.dune.com/api/v1",
        "nansen": "https://api.nansen.ai/v1",
        "glassnode": "https://api.glassnode.com/v1",
        "debank": "https://openapi.debank.com/v1",
        "dexscreener": "https://api.dexscreener.com/latest",
        "defillama": "https://api.llama.fi",
    }
    
    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        cache_ttl: int = 300  # 5 minutes
    ):
        self.api_keys = api_keys or {}
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Known whale/smart money addresses
        self._known_addresses: Dict[str, WhaleWallet] = {}
        
        # Signal history
        self._signals: List[OnChainSignal] = []
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_timestamps:
            return False
        age = (datetime.utcnow() - self._cache_timestamps[key]).total_seconds()
        return age < self.cache_ttl
    
    async def _fetch_json(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Fetch JSON from URL with caching."""
        cache_key = f"{url}:{json.dumps(params or {})}"
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        session = await self._get_session()
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                
                self._cache[cache_key] = data
                self._cache_timestamps[cache_key] = datetime.utcnow()
                
                return data
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise
    
    async def get_whale_wallets(
        self,
        chain: Chain = Chain.ETHEREUM,
        min_balance: Optional[Decimal] = None,
        limit: int = 100
    ) -> List[WhaleWallet]:
        """
        Get whale wallets with large holdings.
        
        Args:
            chain: Blockchain to analyze
            min_balance: Minimum balance in USD (default: $10M)
            limit: Maximum wallets to return
        
        Returns:
            List of whale wallets
        """
        min_balance = min_balance or self.WHALE_THRESHOLD
        
        # In production, fetch from Nansen, Arkham, or similar
        # For now, use DeFiLlama for protocol whales
        try:
            url = f"{self.API_ENDPOINTS['defillama']}/protocols"
            data = await self._fetch_json(url)
            
            whales = []
            # Process top protocol treasuries as "whales"
            for protocol in data[:limit]:
                if Decimal(str(protocol.get('tvl', 0))) >= min_balance:
                    whale = WhaleWallet(
                        address=protocol.get('address', 'unknown'),
                        chain=chain,
                        balance_usd=Decimal(str(protocol.get('tvl', 0))),
                        label=protocol.get('name'),
                        is_smart_money=True
                    )
                    whales.append(whale)
            
            return whales
            
        except Exception as e:
            logger.error(f"Error fetching whale wallets: {e}")
            return []
    
    async def get_dex_flows(
        self,
        chain: Chain = Chain.ETHEREUM,
        token: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get DEX trading flows.
        
        Args:
            chain: Blockchain to analyze
            token: Specific token address (optional)
            hours: Lookback period
        
        Returns:
            DEX flow data with volume, buys/sells
        """
        try:
            # Use DexScreener for DEX data
            if token:
                url = f"{self.API_ENDPOINTS['dexscreener']}/dex/tokens/{token}"
            else:
                url = f"{self.API_ENDPOINTS['dexscreener']}/dex/search?q=ETH"
            
            data = await self._fetch_json(url)
            
            pairs = data.get('pairs', [])
            
            total_volume = Decimal("0")
            buy_volume = Decimal("0")
            sell_volume = Decimal("0")
            
            for pair in pairs[:20]:  # Top 20 pairs
                vol = Decimal(str(pair.get('volume', {}).get('h24', 0)))
                total_volume += vol
                
                # Estimate buy/sell from price change
                price_change = float(pair.get('priceChange', {}).get('h24', 0))
                if price_change > 0:
                    buy_volume += vol * Decimal("0.6")
                    sell_volume += vol * Decimal("0.4")
                else:
                    buy_volume += vol * Decimal("0.4")
                    sell_volume += vol * Decimal("0.6")
            
            return {
                "chain": chain.value,
                "period_hours": hours,
                "total_volume_usd": float(total_volume),
                "buy_volume_usd": float(buy_volume),
                "sell_volume_usd": float(sell_volume),
                "buy_sell_ratio": float(buy_volume / sell_volume) if sell_volume > 0 else 1.0,
                "top_pairs": len(pairs),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching DEX flows: {e}")
            return {}
    
    async def get_exchange_flows(
        self,
        token: str = "ETH",
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get exchange inflow/outflow data.
        
        Large inflows → potential selling pressure
        Large outflows → accumulation signal
        
        Args:
            token: Token symbol
            hours: Lookback period
        
        Returns:
            Exchange flow metrics
        """
        # In production, use Glassnode or CryptoQuant API
        # For now, simulate with reasonable estimates
        try:
            # Placeholder - integrate with Glassnode/CryptoQuant
            return {
                "token": token,
                "period_hours": hours,
                "exchange_inflow": 0,
                "exchange_outflow": 0,
                "net_flow": 0,
                "flow_signal": "neutral",
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Integrate Glassnode API for real data"
            }
        except Exception as e:
            logger.error(f"Error fetching exchange flows: {e}")
            return {}
    
    async def get_network_metrics(
        self,
        chain: Chain = Chain.ETHEREUM
    ) -> Dict[str, Any]:
        """
        Get network activity metrics.
        
        Args:
            chain: Blockchain to analyze
        
        Returns:
            Network metrics (active addresses, tx count, etc.)
        """
        try:
            # Use DeFiLlama for chain TVL as proxy
            url = f"{self.API_ENDPOINTS['defillama']}/v2/chains"
            data = await self._fetch_json(url)
            
            chain_data = next(
                (c for c in data if c.get('name', '').lower() == chain.value),
                None
            )
            
            if chain_data:
                return {
                    "chain": chain.value,
                    "tvl": chain_data.get('tvl', 0),
                    "tvl_change_24h": chain_data.get('change_1d', 0),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            return {"chain": chain.value, "error": "Chain not found"}
            
        except Exception as e:
            logger.error(f"Error fetching network metrics: {e}")
            return {}
    
    async def generate_signals(
        self,
        chain: Chain = Chain.ETHEREUM
    ) -> List[OnChainSignal]:
        """
        Generate trading signals from on-chain data.
        
        Analyzes multiple data sources and generates actionable signals.
        
        Returns:
            List of on-chain signals
        """
        signals = []
        
        try:
            # Gather data
            dex_flows = await self.get_dex_flows(chain)
            network = await self.get_network_metrics(chain)
            
            # Signal: DEX volume spike
            if dex_flows.get('total_volume_usd', 0) > 1000000000:  # $1B+
                signals.append(OnChainSignal(
                    signal_type=SignalType.DEX_VOLUME_SPIKE,
                    chain=chain,
                    token="ETH",
                    strength=0.7,
                    timestamp=datetime.utcnow(),
                    details={"volume_usd": dex_flows['total_volume_usd']},
                    confidence=0.6
                ))
            
            # Signal: Buy pressure
            buy_sell_ratio = dex_flows.get('buy_sell_ratio', 1.0)
            if buy_sell_ratio > 1.5:
                signals.append(OnChainSignal(
                    signal_type=SignalType.WHALE_ACCUMULATION,
                    chain=chain,
                    token="ETH",
                    strength=min(1.0, (buy_sell_ratio - 1) / 2),
                    timestamp=datetime.utcnow(),
                    details={"buy_sell_ratio": buy_sell_ratio},
                    confidence=0.5
                ))
            elif buy_sell_ratio < 0.67:
                signals.append(OnChainSignal(
                    signal_type=SignalType.WHALE_DISTRIBUTION,
                    chain=chain,
                    token="ETH",
                    strength=min(1.0, (1 - buy_sell_ratio) / 0.5),
                    timestamp=datetime.utcnow(),
                    details={"buy_sell_ratio": buy_sell_ratio},
                    confidence=0.5
                ))
            
            # Signal: TVL growth
            tvl_change = network.get('tvl_change_24h', 0)
            if tvl_change > 5:  # 5%+ TVL growth
                signals.append(OnChainSignal(
                    signal_type=SignalType.NETWORK_ACTIVITY_SURGE,
                    chain=chain,
                    token="ETH",
                    strength=min(1.0, tvl_change / 20),
                    timestamp=datetime.utcnow(),
                    details={"tvl_change_24h": tvl_change},
                    confidence=0.6
                ))
            
            # Store signals
            self._signals.extend(signals)
            
            logger.info(f"Generated {len(signals)} on-chain signals for {chain.value}")
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []
    
    def get_recent_signals(
        self,
        hours: int = 24,
        min_strength: float = 0.5
    ) -> List[OnChainSignal]:
        """Get recent signals above strength threshold."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            s for s in self._signals
            if s.timestamp >= cutoff and s.strength >= min_strength
        ]
    
    async def get_smart_money_moves(
        self,
        chain: Chain = Chain.ETHEREUM,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Track smart money wallet movements.
        
        Returns:
            List of significant smart money transactions
        """
        # In production, use Nansen or Arkham Intelligence
        # For now, return placeholder
        return [
            {
                "type": "smart_money_tracking",
                "chain": chain.value,
                "note": "Integrate Nansen/Arkham API for smart money data",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    
    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary of current on-chain signals."""
        recent = self.get_recent_signals(hours=24)
        
        bullish = [s for s in recent if s.signal_type in (
            SignalType.WHALE_ACCUMULATION,
            SignalType.EXCHANGE_OUTFLOW,
            SignalType.SMART_MONEY_BUY
        )]
        
        bearish = [s for s in recent if s.signal_type in (
            SignalType.WHALE_DISTRIBUTION,
            SignalType.EXCHANGE_INFLOW,
            SignalType.SMART_MONEY_SELL
        )]
        
        return {
            "total_signals_24h": len(recent),
            "bullish_signals": len(bullish),
            "bearish_signals": len(bearish),
            "avg_strength": sum(s.strength for s in recent) / len(recent) if recent else 0,
            "bias": "bullish" if len(bullish) > len(bearish) else "bearish" if len(bearish) > len(bullish) else "neutral",
            "timestamp": datetime.utcnow().isoformat()
        }
