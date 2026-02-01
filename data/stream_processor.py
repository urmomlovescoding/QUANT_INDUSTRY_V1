"""
Stream Processor - Real-Time Data Processing with Faust/Kafka

This module provides a production-ready stream processing framework
for real-time market data normalization and feature computation.

Key Features:
- Kafka/Faust streaming integration
- Adaptive normalization with exponential decay
- Windowed feature computation
- Late data handling
- Exactly-once semantics support

Architecture:
    Kafka Topic (raw_market_data)
        → Faust Stream Processor
        → Normalization Agent
        → Feature Computation Agent
        → Kafka Topic (processed_features)
        → Feature Store

Usage:
    # Start the stream processor
    python -m data.stream_processor worker -l info

    # Or programmatically
    from data.stream_processor import app, process_market_data
    app.main()
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, AsyncIterator
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import threading
from collections import deque

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import Faust, fall back to mock if not available
try:
    import faust
    from faust import App, Record, Stream, Topic
    from faust.types import StreamT
    FAUST_AVAILABLE = True
except ImportError:
    FAUST_AVAILABLE = False
    logger.warning("Faust not installed. Stream processing limited to in-memory mode.")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class MarketTick:
    """Raw market data tick."""
    symbol: str
    timestamp: datetime
    price: float
    volume: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    exchange: str = "unknown"
    trade_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'volume': self.volume,
            'bid': self.bid,
            'ask': self.ask,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'exchange': self.exchange,
            'trade_id': self.trade_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketTick':
        return cls(
            symbol=data['symbol'],
            timestamp=datetime.fromisoformat(data['timestamp']) if isinstance(data['timestamp'], str) else data['timestamp'],
            price=float(data['price']),
            volume=float(data['volume']),
            bid=float(data['bid']) if data.get('bid') else None,
            ask=float(data['ask']) if data.get('ask') else None,
            bid_size=float(data['bid_size']) if data.get('bid_size') else None,
            ask_size=float(data['ask_size']) if data.get('ask_size') else None,
            exchange=data.get('exchange', 'unknown'),
            trade_id=data.get('trade_id'),
        )


@dataclass
class NormalizedTick:
    """Normalized market data tick with computed features."""
    symbol: str
    timestamp: datetime
    price: float
    price_normalized: float
    volume: float
    volume_normalized: float
    spread: Optional[float] = None
    spread_normalized: Optional[float] = None
    features: Dict[str, float] = field(default_factory=dict)
    quality_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'price_normalized': self.price_normalized,
            'volume': self.volume,
            'volume_normalized': self.volume_normalized,
            'spread': self.spread,
            'spread_normalized': self.spread_normalized,
            'features': self.features,
            'quality_score': self.quality_score,
        }


@dataclass
class StreamConfig:
    """Configuration for stream processing."""
    kafka_broker: str = "localhost:9092"
    input_topic: str = "raw_market_data"
    output_topic: str = "processed_features"
    consumer_group: str = "quant_stream_processor"
    normalization_window: int = 1000
    decay_factor: float = 0.995
    feature_window: int = 100
    late_data_tolerance_seconds: int = 60
    batch_size: int = 100
    processing_guarantee: str = "exactly_once"


# =============================================================================
# Adaptive Normalizer
# =============================================================================

class AdaptiveNormalizer:
    """
    Real-time adaptive normalizer with exponential decay.

    Features:
    - Exponentially-weighted moving statistics
    - Adaptive bounds that adjust to market conditions
    - Outlier detection and handling
    - Per-symbol normalization

    The decay factor controls how quickly the normalizer adapts:
    - decay=0.99: Slow adaptation, stable in trending markets
    - decay=0.95: Fast adaptation, responsive to regime changes
    """

    def __init__(
        self,
        decay_factor: float = 0.995,
        min_samples: int = 10,
        outlier_std: float = 4.0,
    ):
        self.decay_factor = decay_factor
        self.min_samples = min_samples
        self.outlier_std = outlier_std

        # Per-symbol statistics
        self._stats: Dict[str, Dict[str, float]] = {}
        self._counts: Dict[str, int] = {}
        self._lock = threading.RLock()

    def _get_or_init_stats(self, symbol: str) -> Dict[str, float]:
        """Get or initialize statistics for a symbol."""
        if symbol not in self._stats:
            self._stats[symbol] = {
                'price_mean': 0.0,
                'price_var': 1.0,
                'volume_mean': 0.0,
                'volume_var': 1.0,
                'spread_mean': 0.0,
                'spread_var': 1.0,
            }
            self._counts[symbol] = 0
        return self._stats[symbol]

    def _update_ewma(
        self,
        current_mean: float,
        current_var: float,
        new_value: float,
    ) -> Tuple[float, float]:
        """Update exponentially-weighted moving average and variance."""
        # EWMA update
        new_mean = self.decay_factor * current_mean + (1 - self.decay_factor) * new_value

        # EWMA variance update (Welford-like)
        diff = new_value - current_mean
        new_var = self.decay_factor * (current_var + (1 - self.decay_factor) * diff * diff)

        # Ensure variance is positive
        new_var = max(new_var, 1e-10)

        return new_mean, new_var

    def normalize(self, tick: MarketTick) -> NormalizedTick:
        """
        Normalize a market tick using adaptive statistics.

        Args:
            tick: Raw market tick

        Returns:
            NormalizedTick with z-score normalized values
        """
        with self._lock:
            stats = self._get_or_init_stats(tick.symbol)
            self._counts[tick.symbol] += 1
            count = self._counts[tick.symbol]

            # Initialize with first value
            if count == 1:
                stats['price_mean'] = tick.price
                stats['volume_mean'] = tick.volume

            # Update price statistics
            stats['price_mean'], stats['price_var'] = self._update_ewma(
                stats['price_mean'], stats['price_var'], tick.price
            )

            # Update volume statistics
            stats['volume_mean'], stats['volume_var'] = self._update_ewma(
                stats['volume_mean'], stats['volume_var'], tick.volume
            )

            # Compute normalized values
            price_std = np.sqrt(stats['price_var'])
            volume_std = np.sqrt(stats['volume_var'])

            price_normalized = (tick.price - stats['price_mean']) / price_std if price_std > 0 else 0.0
            volume_normalized = (tick.volume - stats['volume_mean']) / volume_std if volume_std > 0 else 0.0

            # Handle spread if available
            spread = None
            spread_normalized = None
            if tick.bid and tick.ask:
                spread = tick.ask - tick.bid
                stats['spread_mean'], stats['spread_var'] = self._update_ewma(
                    stats['spread_mean'], stats['spread_var'], spread
                )
                spread_std = np.sqrt(stats['spread_var'])
                spread_normalized = (spread - stats['spread_mean']) / spread_std if spread_std > 0 else 0.0

            # Clip outliers
            price_normalized = np.clip(price_normalized, -self.outlier_std, self.outlier_std)
            volume_normalized = np.clip(volume_normalized, -self.outlier_std, self.outlier_std)
            if spread_normalized is not None:
                spread_normalized = np.clip(spread_normalized, -self.outlier_std, self.outlier_std)

            # Compute quality score
            quality_score = self._compute_quality_score(tick, count)

            return NormalizedTick(
                symbol=tick.symbol,
                timestamp=tick.timestamp,
                price=tick.price,
                price_normalized=float(price_normalized),
                volume=tick.volume,
                volume_normalized=float(volume_normalized),
                spread=spread,
                spread_normalized=float(spread_normalized) if spread_normalized is not None else None,
                quality_score=quality_score,
            )

    def _compute_quality_score(self, tick: MarketTick, count: int) -> float:
        """Compute data quality score (0-1)."""
        score = 1.0

        # Penalty for insufficient samples
        if count < self.min_samples:
            score *= count / self.min_samples

        # Penalty for missing optional fields
        if tick.bid is None or tick.ask is None:
            score *= 0.9

        # Penalty for unusual spread (if available)
        if tick.bid and tick.ask:
            spread_pct = (tick.ask - tick.bid) / tick.price
            if spread_pct > 0.01:  # > 1% spread
                score *= 0.8

        return score

    def get_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current statistics for a symbol."""
        if symbol not in self._stats:
            return None

        stats = self._stats[symbol]
        return {
            'symbol': symbol,
            'count': self._counts[symbol],
            'price_mean': stats['price_mean'],
            'price_std': np.sqrt(stats['price_var']),
            'volume_mean': stats['volume_mean'],
            'volume_std': np.sqrt(stats['volume_var']),
            'spread_mean': stats['spread_mean'],
            'spread_std': np.sqrt(stats['spread_var']),
        }

    def reset(self, symbol: Optional[str] = None) -> None:
        """Reset statistics for a symbol or all symbols."""
        with self._lock:
            if symbol:
                self._stats.pop(symbol, None)
                self._counts.pop(symbol, None)
            else:
                self._stats.clear()
                self._counts.clear()


# =============================================================================
# Windowed Feature Computer
# =============================================================================

class WindowedFeatureComputer:
    """
    Compute streaming features over sliding windows.

    Features computed:
    - Returns (1-tick, 5-tick, 10-tick)
    - Volatility (rolling std)
    - VWAP
    - Momentum indicators
    - Volume profile
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._windows: Dict[str, deque] = {}
        self._lock = threading.RLock()

    def _get_window(self, symbol: str) -> deque:
        """Get or create window for symbol."""
        if symbol not in self._windows:
            self._windows[symbol] = deque(maxlen=self.window_size)
        return self._windows[symbol]

    def add_tick(self, tick: NormalizedTick) -> Dict[str, float]:
        """
        Add a tick and compute features.

        Args:
            tick: Normalized tick to add

        Returns:
            Dictionary of computed features
        """
        with self._lock:
            window = self._get_window(tick.symbol)
            window.append(tick)

            if len(window) < 2:
                return {}

            return self._compute_features(window)

    def _compute_features(self, window: deque) -> Dict[str, float]:
        """Compute features from window."""
        features = {}

        prices = np.array([t.price for t in window])
        volumes = np.array([t.volume for t in window])
        normalized_prices = np.array([t.price_normalized for t in window])

        n = len(prices)

        # Returns
        if n >= 2:
            features['return_1'] = np.log(prices[-1] / prices[-2])
        if n >= 5:
            features['return_5'] = np.log(prices[-1] / prices[-5])
        if n >= 10:
            features['return_10'] = np.log(prices[-1] / prices[-10])

        # Volatility (rolling std of returns)
        if n >= 10:
            returns = np.diff(np.log(prices[-11:]))
            features['volatility_10'] = float(np.std(returns))

        # VWAP
        if volumes.sum() > 0:
            features['vwap'] = float((prices * volumes).sum() / volumes.sum())
            features['vwap_deviation'] = float((prices[-1] - features['vwap']) / prices[-1])

        # Momentum (price acceleration)
        if n >= 5:
            recent_return = np.log(prices[-1] / prices[-3]) if n >= 3 else 0
            older_return = np.log(prices[-3] / prices[-5]) if n >= 5 else 0
            features['momentum'] = float(recent_return - older_return)

        # Volume profile
        if n >= 10:
            features['volume_ratio'] = float(volumes[-1] / np.mean(volumes[-10:]))
            features['volume_trend'] = float(np.mean(volumes[-5:]) / np.mean(volumes[-10:-5]) if np.mean(volumes[-10:-5]) > 0 else 1.0)

        # Normalized price features
        features['price_zscore'] = float(normalized_prices[-1])
        if n >= 10:
            features['price_zscore_ma'] = float(np.mean(normalized_prices[-10:]))

        # Spread features (if available)
        spreads = [t.spread for t in window if t.spread is not None]
        if spreads:
            features['spread_current'] = float(spreads[-1])
            features['spread_mean'] = float(np.mean(spreads[-min(10, len(spreads)):]))

        return features

    def get_window_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get statistics about a symbol's window."""
        if symbol not in self._windows:
            return None

        window = self._windows[symbol]
        return {
            'symbol': symbol,
            'size': len(window),
            'max_size': self.window_size,
            'oldest': window[0].timestamp.isoformat() if window else None,
            'newest': window[-1].timestamp.isoformat() if window else None,
        }


# =============================================================================
# Stream Processor (In-Memory Implementation)
# =============================================================================

class InMemoryStreamProcessor:
    """
    In-memory stream processor for when Kafka/Faust is not available.

    Provides the same interface as the Faust-based processor but
    uses in-memory queues for development and testing.
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self.normalizer = AdaptiveNormalizer(decay_factor=self.config.decay_factor)
        self.feature_computer = WindowedFeatureComputer(window_size=self.config.feature_window)

        self._input_queue: asyncio.Queue = asyncio.Queue()
        self._output_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_tick_callbacks: List[callable] = []
        self._on_features_callbacks: List[callable] = []

        # Statistics
        self._stats = {
            'ticks_processed': 0,
            'features_computed': 0,
            'errors': 0,
            'late_data_dropped': 0,
        }

        logger.info("InMemoryStreamProcessor initialized")

    async def start(self) -> None:
        """Start the stream processor."""
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Stream processor started")

    async def stop(self) -> None:
        """Stop the stream processor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stream processor stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                # Wait for input with timeout
                try:
                    tick_data = await asyncio.wait_for(
                        self._input_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Process tick
                result = await self._process_tick(tick_data)

                if result:
                    await self._output_queue.put(result)

                    # Notify callbacks
                    for callback in self._on_features_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(result)
                            else:
                                callback(result)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

            except Exception as e:
                logger.error(f"Processing error: {e}")
                self._stats['errors'] += 1

    async def _process_tick(self, tick_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single tick."""
        try:
            # Parse tick
            tick = MarketTick.from_dict(tick_data)

            # Check for late data
            now = datetime.now(timezone.utc)
            data_age = (now - tick.timestamp).total_seconds()
            if data_age > self.config.late_data_tolerance_seconds:
                self._stats['late_data_dropped'] += 1
                logger.warning(f"Dropped late data for {tick.symbol}: {data_age}s old")
                return None

            # Normalize
            normalized = self.normalizer.normalize(tick)
            self._stats['ticks_processed'] += 1

            # Notify tick callbacks
            for callback in self._on_tick_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(normalized)
                    else:
                        callback(normalized)
                except Exception as e:
                    logger.error(f"Tick callback error: {e}")

            # Compute features
            features = self.feature_computer.add_tick(normalized)
            normalized.features = features
            self._stats['features_computed'] += 1

            return normalized.to_dict()

        except Exception as e:
            logger.error(f"Tick processing error: {e}")
            self._stats['errors'] += 1
            return None

    async def ingest(self, tick_data: Dict[str, Any]) -> None:
        """Ingest a tick into the processor."""
        await self._input_queue.put(tick_data)

    async def ingest_batch(self, ticks: List[Dict[str, Any]]) -> None:
        """Ingest a batch of ticks."""
        for tick in ticks:
            await self._input_queue.put(tick)

    async def get_output(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Get processed output."""
        try:
            return await asyncio.wait_for(self._output_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def on_tick(self, callback: callable) -> None:
        """Register callback for normalized ticks."""
        self._on_tick_callbacks.append(callback)

    def on_features(self, callback: callable) -> None:
        """Register callback for computed features."""
        self._on_features_callbacks.append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            **self._stats,
            'input_queue_size': self._input_queue.qsize(),
            'output_queue_size': self._output_queue.qsize(),
            'running': self._running,
        }


# =============================================================================
# Faust-Based Stream Processor
# =============================================================================

if FAUST_AVAILABLE:
    # Faust record types
    class MarketTickRecord(faust.Record, serializer='json'):
        symbol: str
        timestamp: str
        price: float
        volume: float
        bid: Optional[float] = None
        ask: Optional[float] = None
        bid_size: Optional[float] = None
        ask_size: Optional[float] = None
        exchange: str = "unknown"
        trade_id: Optional[str] = None

    class NormalizedTickRecord(faust.Record, serializer='json'):
        symbol: str
        timestamp: str
        price: float
        price_normalized: float
        volume: float
        volume_normalized: float
        spread: Optional[float] = None
        spread_normalized: Optional[float] = None
        features: Dict[str, float] = {}
        quality_score: float = 1.0

    # Faust app configuration
    app = faust.App(
        'quant_stream_processor',
        broker=os.environ.get('KAFKA_BROKER', 'kafka://localhost:9092'),
        value_serializer='json',
        processing_guarantee='exactly_once',
    )

    # Topics
    raw_market_data_topic = app.topic(
        'raw_market_data',
        value_type=MarketTickRecord,
    )

    processed_features_topic = app.topic(
        'processed_features',
        value_type=NormalizedTickRecord,
    )

    # Shared state
    normalizer = AdaptiveNormalizer(decay_factor=0.995)
    feature_computer = WindowedFeatureComputer(window_size=100)

    @app.agent(raw_market_data_topic)
    async def process_market_data(stream: StreamT[MarketTickRecord]) -> AsyncIterator[NormalizedTickRecord]:
        """
        Main stream processing agent.

        Receives raw market data, normalizes it, computes features,
        and outputs to the processed features topic.
        """
        async for record in stream:
            try:
                # Convert to MarketTick
                tick = MarketTick(
                    symbol=record.symbol,
                    timestamp=datetime.fromisoformat(record.timestamp),
                    price=record.price,
                    volume=record.volume,
                    bid=record.bid,
                    ask=record.ask,
                    bid_size=record.bid_size,
                    ask_size=record.ask_size,
                    exchange=record.exchange,
                    trade_id=record.trade_id,
                )

                # Normalize
                normalized = normalizer.normalize(tick)

                # Compute features
                features = feature_computer.add_tick(normalized)
                normalized.features = features

                # Yield normalized record
                yield NormalizedTickRecord(
                    symbol=normalized.symbol,
                    timestamp=normalized.timestamp.isoformat(),
                    price=normalized.price,
                    price_normalized=normalized.price_normalized,
                    volume=normalized.volume,
                    volume_normalized=normalized.volume_normalized,
                    spread=normalized.spread,
                    spread_normalized=normalized.spread_normalized,
                    features=normalized.features,
                    quality_score=normalized.quality_score,
                )

            except Exception as e:
                logger.error(f"Stream processing error: {e}")

    @app.timer(interval=60.0)
    async def log_stats() -> None:
        """Periodically log processing statistics."""
        stats = {
            'symbols_tracked': len(normalizer._stats),
            'total_windows': len(feature_computer._windows),
        }
        logger.info(f"Stream processor stats: {stats}")

else:
    # Fallback when Faust is not available
    app = None
    process_market_data = None


# =============================================================================
# Factory Function
# =============================================================================

def create_stream_processor(
    config: Optional[StreamConfig] = None,
    use_kafka: bool = False,
) -> InMemoryStreamProcessor:
    """
    Create a stream processor instance.

    Args:
        config: Stream configuration
        use_kafka: Whether to use Kafka/Faust (requires installation)

    Returns:
        Stream processor instance
    """
    if use_kafka and FAUST_AVAILABLE:
        logger.info("Using Faust-based stream processor")
        # Return the Faust app - caller should use app.main() to start
        return app
    else:
        logger.info("Using in-memory stream processor")
        return InMemoryStreamProcessor(config)


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == '__main__':
    if FAUST_AVAILABLE and app:
        # Run Faust worker
        app.main()
    else:
        # Run in-memory processor for testing
        async def main():
            processor = InMemoryStreamProcessor()
            await processor.start()

            # Example: process some test data
            test_tick = {
                'symbol': 'AAPL',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'price': 150.0,
                'volume': 1000.0,
            }

            await processor.ingest(test_tick)
            result = await processor.get_output(timeout=5.0)
            print(f"Processed: {result}")

            await processor.stop()

        asyncio.run(main())
