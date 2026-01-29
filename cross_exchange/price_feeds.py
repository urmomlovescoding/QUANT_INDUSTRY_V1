"""
Multi-Exchange Price Feed Aggregation
=====================================
Real-time price aggregation across multiple exchanges.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Set
from enum import Enum
from collections import defaultdict
import logging
import statistics

logger = logging.getLogger(__name__)


class Exchange(Enum):
    """Supported exchanges."""
    # CEX
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    FTX = "ftx"
    BYBIT = "bybit"
    OKX = "okx"
    HUOBI = "huobi"
    KUCOIN = "kucoin"
    GATEIO = "gateio"
    BITFINEX = "bitfinex"
    
    # DEX
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    SUSHISWAP = "sushiswap"
    CURVE = "curve"
    PANCAKESWAP = "pancakeswap"
    DYDX = "dydx"
    GMX = "gmx"
    
    # Traditional
    NYSE = "nyse"
    NASDAQ = "nasdaq"
    CME = "cme"


class AssetType(Enum):
    """Type of tradeable asset."""
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    OPTION = "option"


@dataclass
class PriceLevel:
    """Single price level."""
    price: float
    size: float
    exchange: Exchange
    
    @property
    def value(self) -> float:
        return self.price * self.size


@dataclass
class ExchangePrice:
    """Price data from single exchange."""
    exchange: Exchange
    symbol: str
    timestamp: datetime
    
    # Best bid/ask
    bid: float
    bid_size: float
    ask: float
    ask_size: float
    
    # Full depth (optional)
    bids: List[PriceLevel] = field(default_factory=list)
    asks: List[PriceLevel] = field(default_factory=list)
    
    # Trade info
    last_price: float = 0.0
    last_size: float = 0.0
    volume_24h: float = 0.0
    
    # Metadata
    asset_type: AssetType = AssetType.SPOT
    latency_ms: float = 0.0
    sequence: int = 0
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def spread_bps(self) -> float:
        if self.mid > 0:
            return (self.spread / self.mid) * 10000
        return 0.0
    
    @property
    def is_stale(self) -> bool:
        """Check if price is stale (>5 seconds old)."""
        return (datetime.now() - self.timestamp).total_seconds() > 5
    
    def depth_at_size(self, size: float, side: str) -> float:
        """Get average price to fill given size."""
        levels = self.bids if side == "bid" else self.asks
        
        if not levels:
            return self.bid if side == "bid" else self.ask
            
        remaining = size
        total_value = 0.0
        
        for level in levels:
            fill = min(remaining, level.size)
            total_value += fill * level.price
            remaining -= fill
            if remaining <= 0:
                break
                
        filled = size - remaining
        return total_value / filled if filled > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange.value,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread_bps": self.spread_bps,
            "volume_24h": self.volume_24h,
            "latency_ms": self.latency_ms,
        }


@dataclass
class AggregatedBook:
    """Aggregated order book across exchanges."""
    symbol: str
    timestamp: datetime
    
    # Best prices across all exchanges
    best_bid: float = 0.0
    best_bid_exchange: Optional[Exchange] = None
    best_bid_size: float = 0.0
    
    best_ask: float = 0.0
    best_ask_exchange: Optional[Exchange] = None
    best_ask_size: float = 0.0
    
    # All exchange prices
    prices: Dict[Exchange, ExchangePrice] = field(default_factory=dict)
    
    # Aggregated depth
    aggregated_bids: List[PriceLevel] = field(default_factory=list)
    aggregated_asks: List[PriceLevel] = field(default_factory=list)
    
    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid
    
    @property
    def spread_bps(self) -> float:
        if self.mid > 0:
            return (self.spread / self.mid) * 10000
        return 0.0
    
    @property
    def has_cross(self) -> bool:
        """Check if there's a crossed market (arb opportunity)."""
        return self.best_bid > self.best_ask and self.best_bid_exchange != self.best_ask_exchange
    
    @property
    def cross_spread_bps(self) -> float:
        """Cross spread in bps (positive = arb opportunity)."""
        if self.mid > 0:
            return (self.best_bid - self.best_ask) / self.mid * 10000
        return 0.0
    
    def get_exchange_spread(self, exchange: Exchange) -> Optional[float]:
        """Get spread for specific exchange."""
        if exchange in self.prices:
            return self.prices[exchange].spread_bps
        return None
    
    def get_price_dispersion(self) -> float:
        """Calculate price dispersion across exchanges (std of mids)."""
        mids = [p.mid for p in self.prices.values() if not p.is_stale]
        if len(mids) < 2:
            return 0.0
        return statistics.stdev(mids)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "best_bid": self.best_bid,
            "best_bid_exchange": self.best_bid_exchange.value if self.best_bid_exchange else None,
            "best_ask": self.best_ask,
            "best_ask_exchange": self.best_ask_exchange.value if self.best_ask_exchange else None,
            "spread_bps": self.spread_bps,
            "has_cross": self.has_cross,
            "cross_spread_bps": self.cross_spread_bps if self.has_cross else 0,
            "num_exchanges": len(self.prices),
            "exchanges": {e.value: p.to_dict() for e, p in self.prices.items()},
        }


@dataclass
class FeedConfig:
    """Configuration for price feeds."""
    # Staleness
    stale_threshold_seconds: float = 5.0
    
    # Depth
    max_depth_levels: int = 20
    
    # Filtering
    min_volume_24h: float = 0.0
    excluded_exchanges: Set[Exchange] = field(default_factory=set)
    
    # Aggregation
    price_precision: int = 8
    size_precision: int = 8


class PriceFeed:
    """
    Single exchange price feed handler.
    """
    
    def __init__(
        self,
        exchange: Exchange,
        symbols: List[str],
        config: Optional[FeedConfig] = None,
    ):
        self.exchange = exchange
        self.symbols = set(symbols)
        self.config = config or FeedConfig()
        
        self._prices: Dict[str, ExchangePrice] = {}
        self._callbacks: List[Callable[[ExchangePrice], None]] = []
        self._connected = False
        self._last_update: Dict[str, datetime] = {}
        
    def register_callback(self, callback: Callable[[ExchangePrice], None]):
        """Register callback for price updates."""
        self._callbacks.append(callback)
        
    def _notify(self, price: ExchangePrice):
        """Notify callbacks of price update."""
        for cb in self._callbacks:
            try:
                cb(price)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    async def connect(self):
        """Connect to exchange feed."""
        logger.info(f"Connecting to {self.exchange.value}...")
        self._connected = True
        
    async def disconnect(self):
        """Disconnect from exchange feed."""
        logger.info(f"Disconnecting from {self.exchange.value}")
        self._connected = False
        
    def update_price(self, price: ExchangePrice):
        """Update price for symbol."""
        self._prices[price.symbol] = price
        self._last_update[price.symbol] = datetime.now()
        self._notify(price)
        
    def get_price(self, symbol: str) -> Optional[ExchangePrice]:
        """Get current price for symbol."""
        return self._prices.get(symbol)
    
    def get_all_prices(self) -> Dict[str, ExchangePrice]:
        """Get all current prices."""
        return self._prices.copy()
    
    def is_stale(self, symbol: str) -> bool:
        """Check if price is stale."""
        if symbol not in self._last_update:
            return True
        elapsed = (datetime.now() - self._last_update[symbol]).total_seconds()
        return elapsed > self.config.stale_threshold_seconds


class MultiExchangeFeed:
    """
    Aggregates price feeds from multiple exchanges.
    
    Features:
    - Real-time best bid/ask across exchanges
    - Aggregated depth
    - Cross-market detection
    - Latency tracking
    """
    
    def __init__(self, config: Optional[FeedConfig] = None):
        self.config = config or FeedConfig()
        self._feeds: Dict[Exchange, PriceFeed] = {}
        self._aggregated: Dict[str, AggregatedBook] = {}
        self._callbacks: List[Callable[[AggregatedBook], None]] = []
        
    def add_feed(self, feed: PriceFeed):
        """Add exchange feed."""
        self._feeds[feed.exchange] = feed
        feed.register_callback(self._on_price_update)
        
    def register_callback(self, callback: Callable[[AggregatedBook], None]):
        """Register callback for aggregated book updates."""
        self._callbacks.append(callback)
        
    def _notify(self, book: AggregatedBook):
        """Notify callbacks of book update."""
        for cb in self._callbacks:
            try:
                cb(book)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _on_price_update(self, price: ExchangePrice):
        """Handle price update from individual feed."""
        symbol = price.symbol
        
        # Get or create aggregated book
        if symbol not in self._aggregated:
            self._aggregated[symbol] = AggregatedBook(
                symbol=symbol,
                timestamp=datetime.now(),
            )
            
        book = self._aggregated[symbol]
        book.timestamp = datetime.now()
        book.prices[price.exchange] = price
        
        # Recalculate best bid/ask
        self._update_best_prices(book)
        
        # Aggregate depth
        self._aggregate_depth(book)
        
        # Notify
        self._notify(book)
    
    def _update_best_prices(self, book: AggregatedBook):
        """Update best bid/ask across exchanges."""
        best_bid = 0.0
        best_bid_exchange = None
        best_bid_size = 0.0
        
        best_ask = float('inf')
        best_ask_exchange = None
        best_ask_size = 0.0
        
        for exchange, price in book.prices.items():
            if price.is_stale:
                continue
                
            if exchange in self.config.excluded_exchanges:
                continue
                
            if self.config.min_volume_24h > 0 and price.volume_24h < self.config.min_volume_24h:
                continue
                
            if price.bid > best_bid:
                best_bid = price.bid
                best_bid_exchange = exchange
                best_bid_size = price.bid_size
                
            if price.ask < best_ask:
                best_ask = price.ask
                best_ask_exchange = exchange
                best_ask_size = price.ask_size
                
        book.best_bid = best_bid
        book.best_bid_exchange = best_bid_exchange
        book.best_bid_size = best_bid_size
        book.best_ask = best_ask if best_ask != float('inf') else 0
        book.best_ask_exchange = best_ask_exchange
        book.best_ask_size = best_ask_size
    
    def _aggregate_depth(self, book: AggregatedBook):
        """Aggregate order book depth across exchanges."""
        all_bids: List[PriceLevel] = []
        all_asks: List[PriceLevel] = []
        
        for exchange, price in book.prices.items():
            if price.is_stale:
                continue
                
            for level in price.bids[:self.config.max_depth_levels]:
                all_bids.append(level)
                
            for level in price.asks[:self.config.max_depth_levels]:
                all_asks.append(level)
                
        # Sort and truncate
        all_bids.sort(key=lambda x: x.price, reverse=True)
        all_asks.sort(key=lambda x: x.price)
        
        book.aggregated_bids = all_bids[:self.config.max_depth_levels]
        book.aggregated_asks = all_asks[:self.config.max_depth_levels]
    
    async def connect_all(self):
        """Connect all feeds."""
        await asyncio.gather(*[
            feed.connect() for feed in self._feeds.values()
        ])
        
    async def disconnect_all(self):
        """Disconnect all feeds."""
        await asyncio.gather(*[
            feed.disconnect() for feed in self._feeds.values()
        ])
    
    def get_aggregated_book(self, symbol: str) -> Optional[AggregatedBook]:
        """Get aggregated book for symbol."""
        return self._aggregated.get(symbol)
    
    def get_all_books(self) -> Dict[str, AggregatedBook]:
        """Get all aggregated books."""
        return self._aggregated.copy()
    
    def get_crossed_markets(self) -> List[AggregatedBook]:
        """Get all markets with cross (arb opportunities)."""
        return [
            book for book in self._aggregated.values()
            if book.has_cross
        ]
    
    def get_price_matrix(self, symbol: str) -> Dict[str, Dict[str, float]]:
        """Get price matrix for symbol across exchanges."""
        book = self._aggregated.get(symbol)
        if not book:
            return {}
            
        matrix = {}
        for exchange, price in book.prices.items():
            matrix[exchange.value] = {
                "bid": price.bid,
                "ask": price.ask,
                "mid": price.mid,
                "spread_bps": price.spread_bps,
            }
            
        return matrix
    
    def get_exchange_rankings(self, symbol: str) -> List[Dict[str, Any]]:
        """Rank exchanges by price for a symbol."""
        book = self._aggregated.get(symbol)
        if not book:
            return []
            
        rankings = []
        for exchange, price in book.prices.items():
            if price.is_stale:
                continue
                
            rankings.append({
                "exchange": exchange.value,
                "bid": price.bid,
                "ask": price.ask,
                "mid": price.mid,
                "spread_bps": price.spread_bps,
                "volume_24h": price.volume_24h,
                "latency_ms": price.latency_ms,
            })
            
        # Sort by mid price
        rankings.sort(key=lambda x: x["mid"], reverse=True)
        return rankings


class PriceNormalizer:
    """
    Normalizes prices across exchanges with different conventions.
    """
    
    def __init__(self):
        # Symbol mappings between exchanges
        self._symbol_maps: Dict[Exchange, Dict[str, str]] = {}
        
        # Price adjustments (for different quote currencies, etc.)
        self._price_adjustments: Dict[str, Callable[[float], float]] = {}
        
    def add_symbol_mapping(
        self,
        exchange: Exchange,
        internal_symbol: str,
        exchange_symbol: str,
    ):
        """Map internal symbol to exchange-specific symbol."""
        if exchange not in self._symbol_maps:
            self._symbol_maps[exchange] = {}
        self._symbol_maps[exchange][internal_symbol] = exchange_symbol
        
    def get_exchange_symbol(
        self,
        exchange: Exchange,
        internal_symbol: str,
    ) -> str:
        """Get exchange-specific symbol."""
        return self._symbol_maps.get(exchange, {}).get(internal_symbol, internal_symbol)
    
    def normalize_symbol(self, exchange: Exchange, exchange_symbol: str) -> str:
        """Convert exchange symbol to internal format."""
        # Reverse lookup
        mapping = self._symbol_maps.get(exchange, {})
        for internal, external in mapping.items():
            if external == exchange_symbol:
                return internal
        return exchange_symbol
    
    @staticmethod
    def standardize_pair(symbol: str) -> Tuple[str, str]:
        """Standardize trading pair format."""
        # Handle various formats: BTC/USDT, BTCUSDT, BTC-USDT
        symbol = symbol.upper()
        
        for sep in ["/", "-", "_"]:
            if sep in symbol:
                parts = symbol.split(sep)
                if len(parts) == 2:
                    return parts[0], parts[1]
                    
        # No separator - try to parse
        common_quotes = ["USDT", "USDC", "USD", "BTC", "ETH", "BNB"]
        for quote in common_quotes:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return base, quote
                
        return symbol, ""


from typing import Tuple
