"""
Tests for Microstructure - Order Flow Features
"""

import pytest
import numpy as np
from datetime import datetime
from microstructure.order_flow_features import (
    OrderFlowFeatureEngine,
    OrderBookSnapshot,
    TradeEvent,
    PriceLevel,
    FeatureSet,
    AggressorSide,
    FeatureConfig,
    FeatureNormalizer,
)


class TestPriceLevel:
    """Tests for PriceLevel dataclass."""
    
    def test_create_level(self):
        level = PriceLevel(price=100.50, size=1000, num_orders=5)
        assert level.price == 100.50
        assert level.size == 1000
        assert level.num_orders == 5
    
    def test_notional(self):
        level = PriceLevel(price=50.0, size=200)
        assert level.notional == 10000.0  # 50 * 200


class TestOrderBookSnapshot:
    """Tests for OrderBookSnapshot."""
    
    @pytest.fixture
    def sample_book(self):
        return OrderBookSnapshot(
            symbol="AAPL",
            timestamp=datetime.now(),
            bids=[
                PriceLevel(185.50, 1000),
                PriceLevel(185.40, 2000),
                PriceLevel(185.30, 1500),
            ],
            asks=[
                PriceLevel(185.60, 800),
                PriceLevel(185.70, 1200),
                PriceLevel(185.80, 1000),
            ],
        )
    
    def test_best_bid_ask(self, sample_book):
        assert sample_book.best_bid.price == 185.50
        assert sample_book.best_ask.price == 185.60
    
    def test_mid_price(self, sample_book):
        expected_mid = (185.50 + 185.60) / 2
        assert sample_book.mid_price == expected_mid
    
    def test_spread(self, sample_book):
        assert abs(sample_book.spread - 0.10) < 0.001  # 185.60 - 185.50
    
    def test_spread_bps(self, sample_book):
        mid = sample_book.mid_price
        expected_bps = (0.10 / mid) * 10000
        assert abs(sample_book.spread_bps - expected_bps) < 0.1
    
    def test_total_bid_size(self, sample_book):
        # 1000 + 2000 + 1500 = 4500 (all levels)
        assert sample_book.total_bid_size(10) == 4500
        # First 2 levels
        assert sample_book.total_bid_size(2) == 3000
    
    def test_total_ask_size(self, sample_book):
        assert sample_book.total_ask_size(10) == 3000
    
    def test_imbalance_bid_heavy(self):
        """Test imbalance when bids > asks."""
        book = OrderBookSnapshot(
            symbol="TEST",
            timestamp=datetime.now(),
            bids=[PriceLevel(100.0, 5000)],
            asks=[PriceLevel(100.10, 1000)],
        )
        imb = book.imbalance(1)
        # (5000 - 1000) / (5000 + 1000) = 0.667
        assert imb > 0.6
    
    def test_imbalance_ask_heavy(self):
        """Test imbalance when asks > bids."""
        book = OrderBookSnapshot(
            symbol="TEST",
            timestamp=datetime.now(),
            bids=[PriceLevel(100.0, 1000)],
            asks=[PriceLevel(100.10, 5000)],
        )
        imb = book.imbalance(1)
        assert imb < -0.6


class TestTradeEvent:
    """Tests for TradeEvent."""
    
    def test_create_trade(self):
        trade = TradeEvent(
            symbol="AAPL",
            timestamp=datetime.now(),
            price=185.55,
            size=500,
            aggressor=AggressorSide.BUY,
        )
        assert trade.price == 185.55
        assert trade.size == 500
        assert trade.aggressor == AggressorSide.BUY
    
    def test_notional(self):
        trade = TradeEvent(
            symbol="TEST",
            timestamp=datetime.now(),
            price=100.0,
            size=100,
            aggressor=AggressorSide.BUY,
        )
        assert trade.notional == 10000.0
    
    def test_is_uptick(self):
        trade = TradeEvent(
            symbol="TEST",
            timestamp=datetime.now(),
            price=100.50,
            size=100,
            aggressor=AggressorSide.BUY,
            bid_at_trade=100.40,
            ask_at_trade=100.50,
        )
        assert trade.is_uptick is True


class TestOrderFlowFeatureEngine:
    """Tests for OrderFlowFeatureEngine."""
    
    @pytest.fixture
    def engine(self):
        return OrderFlowFeatureEngine()
    
    @pytest.fixture
    def sample_book(self):
        return OrderBookSnapshot(
            symbol="AAPL",
            timestamp=datetime.now(),
            bids=[
                PriceLevel(185.50, 1000),
                PriceLevel(185.40, 2000),
            ],
            asks=[
                PriceLevel(185.60, 800),
                PriceLevel(185.70, 1200),
            ],
        )
    
    def test_engine_initialization(self, engine):
        assert engine.config is not None
        assert len(engine._book_history) == 0
    
    def test_process_book_update(self, engine, sample_book):
        features = engine.process_book_update(sample_book)
        
        assert features is not None
        assert features.symbol == "AAPL"
        assert features.mid_price == pytest.approx(185.55, 0.01)
        assert features.spread_bps > 0
    
    def test_imbalance_features(self, engine, sample_book):
        features = engine.process_book_update(sample_book)
        
        # Bids: 3000, Asks: 2000 -> positive imbalance
        assert features.imbalance_5 > 0
    
    def test_feature_names(self):
        names = FeatureSet.feature_names()
        assert "spread_bps" in names
        assert "imbalance_5" in names
        assert "trade_imbalance" in names
        assert len(names) == 22  # 22 features
    
    def test_feature_to_array(self, engine, sample_book):
        features = engine.process_book_update(sample_book)
        arr = features.to_array()
        
        assert isinstance(arr, np.ndarray)
        assert len(arr) == 22


class TestFeatureNormalizer:
    """Tests for FeatureNormalizer."""
    
    def test_normalizer_initialization(self):
        normalizer = FeatureNormalizer(window_size=100)
        assert normalizer.window_size == 100
    
    def test_fit_transform(self):
        normalizer = FeatureNormalizer(window_size=100)
        engine = OrderFlowFeatureEngine()
        
        # Generate multiple features
        for i in range(20):
            book = OrderBookSnapshot(
                symbol="TEST",
                timestamp=datetime.now(),
                bids=[PriceLevel(100.0 + i * 0.01, 1000 + i * 10)],
                asks=[PriceLevel(100.10 + i * 0.01, 800 + i * 10)],
            )
            features = engine.process_book_update(book)
            normalized = normalizer.fit_transform(features)
            
            assert isinstance(normalized, np.ndarray)


class TestFeatureConfig:
    """Tests for FeatureConfig."""
    
    def test_default_config(self):
        config = FeatureConfig()
        assert config.trade_window_seconds == 60
        assert config.max_depth_levels == 10
    
    def test_custom_config(self):
        config = FeatureConfig(
            trade_window_seconds=120,
            max_depth_levels=20,
        )
        assert config.trade_window_seconds == 120
        assert config.max_depth_levels == 20
