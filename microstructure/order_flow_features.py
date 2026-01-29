"""
Order Flow Feature Engineering
==============================
Extracts ML features from order book and trade data.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger(__name__)


class AggressorSide(Enum):
    """Trade aggressor side."""
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


@dataclass
class PriceLevel:
    """Single price level in order book."""
    price: float
    size: int
    num_orders: int = 1
    
    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass
class OrderBookSnapshot:
    """Point-in-time order book snapshot."""
    symbol: str
    timestamp: datetime
    bids: List[PriceLevel]  # Descending by price
    asks: List[PriceLevel]  # Ascending by price
    
    @property
    def best_bid(self) -> Optional[PriceLevel]:
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[PriceLevel]:
        return self.asks[0] if self.asks else None
    
    @property
    def mid_price(self) -> float:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return 0.0
    
    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return 0.0
    
    @property
    def spread_bps(self) -> float:
        """Spread in basis points."""
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 10000
        return 0.0
    
    def total_bid_size(self, levels: int = 10) -> int:
        return sum(b.size for b in self.bids[:levels])
    
    def total_ask_size(self, levels: int = 10) -> int:
        return sum(a.size for a in self.asks[:levels])
    
    def imbalance(self, levels: int = 10) -> float:
        """Order book imbalance (-1 to 1)."""
        bid_size = self.total_bid_size(levels)
        ask_size = self.total_ask_size(levels)
        total = bid_size + ask_size
        if total == 0:
            return 0.0
        return (bid_size - ask_size) / total


@dataclass
class TradeEvent:
    """Single trade execution."""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    aggressor: AggressorSide
    
    # Optional context
    bid_at_trade: float = 0.0
    ask_at_trade: float = 0.0
    
    @property
    def notional(self) -> float:
        return self.price * self.size
    
    @property
    def is_uptick(self) -> bool:
        """Trade at or above mid."""
        if self.bid_at_trade and self.ask_at_trade:
            mid = (self.bid_at_trade + self.ask_at_trade) / 2
            return self.price >= mid
        return self.aggressor == AggressorSide.BUY


@dataclass
class FeatureSet:
    """Computed features for ML model."""
    timestamp: datetime
    symbol: str
    
    # Order book features
    spread_bps: float = 0.0
    mid_price: float = 0.0
    imbalance_1: float = 0.0  # Top 1 level
    imbalance_5: float = 0.0  # Top 5 levels
    imbalance_10: float = 0.0  # Top 10 levels
    bid_depth_5: int = 0
    ask_depth_5: int = 0
    bid_depth_10: int = 0
    ask_depth_10: int = 0
    
    # Weighted imbalances
    weighted_imbalance: float = 0.0  # Price-weighted
    volume_weighted_imbalance: float = 0.0
    
    # Book dynamics
    bid_change: float = 0.0  # Change in bid size
    ask_change: float = 0.0  # Change in ask size
    spread_change: float = 0.0
    mid_change: float = 0.0
    
    # Trade flow features
    buy_volume: int = 0
    sell_volume: int = 0
    net_volume: int = 0
    trade_imbalance: float = 0.0
    vwap: float = 0.0
    num_trades: int = 0
    avg_trade_size: float = 0.0
    large_trade_ratio: float = 0.0  # % of volume from large trades
    
    # Momentum features
    returns_1s: float = 0.0
    returns_5s: float = 0.0
    returns_30s: float = 0.0
    returns_1m: float = 0.0
    
    # Volatility features
    realized_vol_1m: float = 0.0
    realized_vol_5m: float = 0.0
    high_low_range: float = 0.0
    
    # Microstructure features
    kyle_lambda: float = 0.0  # Price impact coefficient
    order_arrival_rate: float = 0.0
    trade_arrival_rate: float = 0.0
    toxicity: float = 0.0  # VPIN-like measure
    
    # Derived signals
    buy_pressure: float = 0.0
    sell_pressure: float = 0.0
    pressure_diff: float = 0.0
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML model."""
        return np.array([
            self.spread_bps,
            self.imbalance_1,
            self.imbalance_5,
            self.imbalance_10,
            self.bid_depth_5,
            self.ask_depth_5,
            self.weighted_imbalance,
            self.bid_change,
            self.ask_change,
            self.spread_change,
            self.mid_change,
            self.trade_imbalance,
            self.net_volume,
            self.avg_trade_size,
            self.large_trade_ratio,
            self.returns_1s,
            self.returns_5s,
            self.returns_30s,
            self.realized_vol_1m,
            self.kyle_lambda,
            self.toxicity,
            self.pressure_diff,
        ])
    
    @staticmethod
    def feature_names() -> List[str]:
        """Get feature names for array."""
        return [
            "spread_bps",
            "imbalance_1",
            "imbalance_5",
            "imbalance_10",
            "bid_depth_5",
            "ask_depth_5",
            "weighted_imbalance",
            "bid_change",
            "ask_change",
            "spread_change",
            "mid_change",
            "trade_imbalance",
            "net_volume",
            "avg_trade_size",
            "large_trade_ratio",
            "returns_1s",
            "returns_5s",
            "returns_30s",
            "realized_vol_1m",
            "kyle_lambda",
            "toxicity",
            "pressure_diff",
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            **{name: getattr(self, name) for name in self.feature_names()},
        }


@dataclass
class FeatureConfig:
    """Configuration for feature computation."""
    # Lookback windows
    trade_window_seconds: int = 60
    book_window_seconds: int = 60
    
    # Depth levels
    max_depth_levels: int = 10
    
    # Thresholds
    large_trade_percentile: float = 0.9
    
    # Decay factors for exponential weighting
    book_decay: float = 0.95
    trade_decay: float = 0.9


class OrderFlowFeatureEngine:
    """
    Computes ML features from order book and trade data.
    
    Features include:
    - Order book imbalances at various depths
    - Trade flow metrics (buy/sell volume, VWAP)
    - Microstructure measures (spread, Kyle's lambda, toxicity)
    - Price momentum and volatility
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        
        # Rolling buffers
        self._book_history: Dict[str, deque] = {}
        self._trade_history: Dict[str, deque] = {}
        self._price_history: Dict[str, deque] = {}
        
        # Cached computations
        self._last_features: Dict[str, FeatureSet] = {}
        
    def _get_or_create_buffer(
        self,
        symbol: str,
        buffer_dict: Dict,
        maxlen: int = 1000,
    ) -> deque:
        """Get or create a rolling buffer for symbol."""
        if symbol not in buffer_dict:
            buffer_dict[symbol] = deque(maxlen=maxlen)
        return buffer_dict[symbol]
    
    def process_book_update(
        self,
        snapshot: OrderBookSnapshot,
    ) -> FeatureSet:
        """
        Process order book update and compute features.
        
        Args:
            snapshot: Current order book snapshot
            
        Returns:
            Computed feature set
        """
        symbol = snapshot.symbol
        
        # Store in history
        book_buffer = self._get_or_create_buffer(symbol, self._book_history)
        book_buffer.append(snapshot)
        
        # Store price
        price_buffer = self._get_or_create_buffer(symbol, self._price_history)
        price_buffer.append((snapshot.timestamp, snapshot.mid_price))
        
        # Compute features
        features = self._compute_features(symbol, snapshot)
        self._last_features[symbol] = features
        
        return features
    
    def process_trade(
        self,
        trade: TradeEvent,
        current_book: Optional[OrderBookSnapshot] = None,
    ) -> Optional[FeatureSet]:
        """
        Process trade event and update features.
        
        Args:
            trade: Trade event
            current_book: Current order book (optional)
            
        Returns:
            Updated feature set if book is available
        """
        symbol = trade.symbol
        
        # Store trade
        trade_buffer = self._get_or_create_buffer(symbol, self._trade_history)
        trade_buffer.append(trade)
        
        # Update features if we have a book
        if current_book:
            return self.process_book_update(current_book)
            
        return self._last_features.get(symbol)
    
    def _compute_features(
        self,
        symbol: str,
        snapshot: OrderBookSnapshot,
    ) -> FeatureSet:
        """Compute all features from current state."""
        features = FeatureSet(
            timestamp=snapshot.timestamp,
            symbol=symbol,
        )
        
        # Basic book features
        features.spread_bps = snapshot.spread_bps
        features.mid_price = snapshot.mid_price
        features.imbalance_1 = snapshot.imbalance(1)
        features.imbalance_5 = snapshot.imbalance(5)
        features.imbalance_10 = snapshot.imbalance(10)
        features.bid_depth_5 = snapshot.total_bid_size(5)
        features.ask_depth_5 = snapshot.total_ask_size(5)
        features.bid_depth_10 = snapshot.total_bid_size(10)
        features.ask_depth_10 = snapshot.total_ask_size(10)
        
        # Weighted imbalance (levels closer to mid weighted more)
        features.weighted_imbalance = self._compute_weighted_imbalance(snapshot)
        
        # Book dynamics
        prev_snapshot = self._get_previous_book(symbol)
        if prev_snapshot:
            features.bid_change = (
                snapshot.total_bid_size(5) - prev_snapshot.total_bid_size(5)
            ) / max(1, prev_snapshot.total_bid_size(5))
            features.ask_change = (
                snapshot.total_ask_size(5) - prev_snapshot.total_ask_size(5)
            ) / max(1, prev_snapshot.total_ask_size(5))
            features.spread_change = snapshot.spread - prev_snapshot.spread
            features.mid_change = snapshot.mid_price - prev_snapshot.mid_price
        
        # Trade flow features
        self._compute_trade_features(features, symbol, snapshot.timestamp)
        
        # Momentum features
        self._compute_momentum_features(features, symbol, snapshot.timestamp)
        
        # Volatility features
        self._compute_volatility_features(features, symbol, snapshot.timestamp)
        
        # Microstructure features
        self._compute_microstructure_features(features, symbol, snapshot.timestamp)
        
        # Pressure signals
        features.buy_pressure = (
            features.imbalance_5 * 0.5 + features.trade_imbalance * 0.5
        )
        features.sell_pressure = -features.buy_pressure
        features.pressure_diff = features.buy_pressure - features.sell_pressure
        
        return features
    
    def _compute_weighted_imbalance(
        self,
        snapshot: OrderBookSnapshot,
    ) -> float:
        """Compute price-distance weighted imbalance."""
        if not snapshot.best_bid or not snapshot.best_ask:
            return 0.0
            
        mid = snapshot.mid_price
        weighted_bid = 0.0
        weighted_ask = 0.0
        
        for i, bid in enumerate(snapshot.bids[:self.config.max_depth_levels]):
            distance = mid - bid.price
            weight = 1.0 / (1 + distance * 100)  # Closer = higher weight
            weighted_bid += bid.size * weight
            
        for i, ask in enumerate(snapshot.asks[:self.config.max_depth_levels]):
            distance = ask.price - mid
            weight = 1.0 / (1 + distance * 100)
            weighted_ask += ask.size * weight
            
        total = weighted_bid + weighted_ask
        if total == 0:
            return 0.0
            
        return (weighted_bid - weighted_ask) / total
    
    def _get_previous_book(
        self,
        symbol: str,
        offset: int = 1,
    ) -> Optional[OrderBookSnapshot]:
        """Get previous book snapshot."""
        buffer = self._book_history.get(symbol, deque())
        if len(buffer) > offset:
            return buffer[-(offset + 1)]
        return None
    
    def _compute_trade_features(
        self,
        features: FeatureSet,
        symbol: str,
        current_time: datetime,
    ):
        """Compute trade-related features."""
        cutoff = current_time - timedelta(seconds=self.config.trade_window_seconds)
        trades = [
            t for t in self._trade_history.get(symbol, [])
            if t.timestamp > cutoff
        ]
        
        if not trades:
            return
            
        buy_volume = sum(t.size for t in trades if t.aggressor == AggressorSide.BUY)
        sell_volume = sum(t.size for t in trades if t.aggressor == AggressorSide.SELL)
        total_volume = buy_volume + sell_volume
        
        features.buy_volume = buy_volume
        features.sell_volume = sell_volume
        features.net_volume = buy_volume - sell_volume
        
        if total_volume > 0:
            features.trade_imbalance = (buy_volume - sell_volume) / total_volume
            
        # VWAP
        total_notional = sum(t.notional for t in trades)
        if total_volume > 0:
            features.vwap = total_notional / total_volume
            
        features.num_trades = len(trades)
        features.avg_trade_size = total_volume / len(trades) if trades else 0
        
        # Large trade ratio
        if trades:
            sizes = [t.size for t in trades]
            threshold = np.percentile(sizes, self.config.large_trade_percentile * 100)
            large_volume = sum(t.size for t in trades if t.size >= threshold)
            features.large_trade_ratio = large_volume / max(1, total_volume)
    
    def _compute_momentum_features(
        self,
        features: FeatureSet,
        symbol: str,
        current_time: datetime,
    ):
        """Compute price momentum features."""
        prices = list(self._price_history.get(symbol, []))
        
        if len(prices) < 2:
            return
            
        current_price = prices[-1][1]
        
        def get_return(seconds_ago: int) -> float:
            cutoff = current_time - timedelta(seconds=seconds_ago)
            past_prices = [(t, p) for t, p in prices if t <= cutoff]
            if past_prices:
                past_price = past_prices[-1][1]
                if past_price > 0:
                    return (current_price - past_price) / past_price
            return 0.0
        
        features.returns_1s = get_return(1)
        features.returns_5s = get_return(5)
        features.returns_30s = get_return(30)
        features.returns_1m = get_return(60)
    
    def _compute_volatility_features(
        self,
        features: FeatureSet,
        symbol: str,
        current_time: datetime,
    ):
        """Compute volatility features."""
        prices = list(self._price_history.get(symbol, []))
        
        if len(prices) < 10:
            return
            
        def get_realized_vol(seconds: int) -> float:
            cutoff = current_time - timedelta(seconds=seconds)
            window_prices = [p for t, p in prices if t > cutoff]
            
            if len(window_prices) < 2:
                return 0.0
                
            returns = np.diff(window_prices) / window_prices[:-1]
            return float(np.std(returns)) if len(returns) > 0 else 0.0
        
        features.realized_vol_1m = get_realized_vol(60)
        features.realized_vol_5m = get_realized_vol(300)
        
        # High-low range
        cutoff = current_time - timedelta(seconds=60)
        window_prices = [p for t, p in prices if t > cutoff]
        if window_prices:
            high = max(window_prices)
            low = min(window_prices)
            mid = (high + low) / 2
            if mid > 0:
                features.high_low_range = (high - low) / mid
    
    def _compute_microstructure_features(
        self,
        features: FeatureSet,
        symbol: str,
        current_time: datetime,
    ):
        """Compute microstructure features."""
        trades = list(self._trade_history.get(symbol, []))
        
        if len(trades) < 5:
            return
            
        # Kyle's Lambda (price impact)
        # Simplified: regress price change on signed volume
        cutoff = current_time - timedelta(seconds=60)
        recent_trades = [t for t in trades if t.timestamp > cutoff]
        
        if len(recent_trades) >= 5:
            signed_volumes = []
            price_changes = []
            
            for i in range(1, len(recent_trades)):
                prev = recent_trades[i - 1]
                curr = recent_trades[i]
                
                sign = 1 if curr.aggressor == AggressorSide.BUY else -1
                signed_volumes.append(sign * curr.size)
                price_changes.append(curr.price - prev.price)
                
            if signed_volumes and price_changes:
                sv_array = np.array(signed_volumes)
                pc_array = np.array(price_changes)
                
                # Simple regression coefficient
                cov = np.cov(sv_array, pc_array)
                if cov.shape == (2, 2) and cov[0, 0] > 0:
                    features.kyle_lambda = cov[0, 1] / cov[0, 0]
        
        # Trade arrival rate (trades per second)
        if recent_trades:
            duration = (recent_trades[-1].timestamp - recent_trades[0].timestamp).total_seconds()
            if duration > 0:
                features.trade_arrival_rate = len(recent_trades) / duration
        
        # Toxicity (VPIN-like)
        # Higher when order flow is consistently one-sided
        if features.trade_imbalance != 0:
            features.toxicity = abs(features.trade_imbalance) * features.trade_arrival_rate
    
    def get_feature_importance_hints(self) -> Dict[str, str]:
        """Get hints about feature importance for interpretability."""
        return {
            "imbalance_5": "Order book imbalance predicts short-term price direction",
            "weighted_imbalance": "Price-weighted imbalance, more responsive to near-mid activity",
            "trade_imbalance": "Net buy/sell flow, indicates immediate pressure",
            "bid_change": "Increasing bids suggest accumulation",
            "ask_change": "Increasing asks suggest distribution",
            "kyle_lambda": "Higher values indicate larger price impact per trade (less liquid)",
            "toxicity": "Higher values suggest informed trading present",
            "returns_5s": "Recent momentum, useful for mean-reversion",
            "pressure_diff": "Combined book + flow pressure signal",
        }


class FeatureNormalizer:
    """
    Normalizes features for ML models using rolling statistics.
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._history: Dict[str, deque] = {}
        self._stats: Dict[str, Dict[str, float]] = {}
        
    def fit_transform(self, features: FeatureSet) -> np.ndarray:
        """Fit on feature and return normalized values."""
        arr = features.to_array()
        symbol = features.symbol
        
        # Update history
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=self.window_size)
            
        self._history[symbol].append(arr)
        
        # Compute rolling stats
        if len(self._history[symbol]) < 10:
            # Not enough history, return raw
            return arr
            
        history_arr = np.array(self._history[symbol])
        means = np.mean(history_arr, axis=0)
        stds = np.std(history_arr, axis=0)
        stds[stds == 0] = 1  # Avoid division by zero
        
        self._stats[symbol] = {"means": means, "stds": stds}
        
        # Z-score normalization
        return (arr - means) / stds
    
    def transform(self, features: FeatureSet) -> np.ndarray:
        """Transform using existing statistics."""
        arr = features.to_array()
        symbol = features.symbol
        
        if symbol not in self._stats:
            return arr
            
        means = self._stats[symbol]["means"]
        stds = self._stats[symbol]["stds"]
        
        return (arr - means) / stds
