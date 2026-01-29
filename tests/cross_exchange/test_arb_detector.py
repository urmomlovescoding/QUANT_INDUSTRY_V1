"""
Tests for Cross-Exchange - Arbitrage Detection
"""

import pytest
from datetime import datetime, timedelta
from cross_exchange.price_feeds import (
    Exchange,
    ExchangePrice,
    AggregatedBook,
    MultiExchangeFeed,
    PriceLevel,
    FeedConfig,
)
from cross_exchange.arb_detector import (
    ArbDetector,
    ArbConfig,
    ArbOpportunity,
    ArbType,
    ArbStatus,
)


class TestExchange:
    """Tests for Exchange enum."""
    
    def test_cex_exchanges(self):
        assert Exchange.BINANCE.value == "binance"
        assert Exchange.COINBASE.value == "coinbase"
        assert Exchange.KRAKEN.value == "kraken"
    
    def test_dex_exchanges(self):
        assert Exchange.UNISWAP_V3.value == "uniswap_v3"
        assert Exchange.SUSHISWAP.value == "sushiswap"


class TestExchangePrice:
    """Tests for ExchangePrice dataclass."""
    
    def test_create_price(self):
        price = ExchangePrice(
            exchange=Exchange.BINANCE,
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            bid=50000.0,
            bid_size=10.0,
            ask=50010.0,
            ask_size=8.0,
        )
        assert price.exchange == Exchange.BINANCE
        assert price.bid == 50000.0
        assert price.ask == 50010.0
    
    def test_mid_price(self):
        price = ExchangePrice(
            exchange=Exchange.BINANCE,
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            bid=50000.0,
            bid_size=10.0,
            ask=50010.0,
            ask_size=8.0,
        )
        assert price.mid == 50005.0
    
    def test_spread(self):
        price = ExchangePrice(
            exchange=Exchange.BINANCE,
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            bid=50000.0,
            bid_size=10.0,
            ask=50010.0,
            ask_size=8.0,
        )
        assert price.spread == 10.0
    
    def test_spread_bps(self):
        price = ExchangePrice(
            exchange=Exchange.BINANCE,
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            bid=50000.0,
            bid_size=10.0,
            ask=50010.0,
            ask_size=8.0,
        )
        expected_bps = (10.0 / 50005.0) * 10000
        assert abs(price.spread_bps - expected_bps) < 0.1
    
    def test_is_stale(self):
        # Fresh price
        fresh = ExchangePrice(
            exchange=Exchange.BINANCE,
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            bid=50000.0,
            bid_size=10.0,
            ask=50010.0,
            ask_size=8.0,
        )
        assert fresh.is_stale is False
        
        # Old price
        stale = ExchangePrice(
            exchange=Exchange.BINANCE,
            symbol="BTC/USDT",
            timestamp=datetime.now() - timedelta(seconds=10),
            bid=50000.0,
            bid_size=10.0,
            ask=50010.0,
            ask_size=8.0,
        )
        assert stale.is_stale is True


class TestAggregatedBook:
    """Tests for AggregatedBook."""
    
    def test_create_book(self):
        book = AggregatedBook(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            best_bid=50000.0,
            best_bid_exchange=Exchange.BINANCE,
            best_bid_size=10.0,
            best_ask=49990.0,  # Cross!
            best_ask_exchange=Exchange.COINBASE,
            best_ask_size=8.0,
        )
        assert book.symbol == "BTC/USDT"
        assert book.best_bid_exchange == Exchange.BINANCE
    
    def test_has_cross(self):
        # Crossed market: bid > ask on different exchanges
        crossed = AggregatedBook(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            best_bid=50010.0,
            best_bid_exchange=Exchange.BINANCE,
            best_bid_size=10.0,
            best_ask=50000.0,
            best_ask_exchange=Exchange.COINBASE,
            best_ask_size=8.0,
        )
        assert crossed.has_cross is True
        
        # Normal market: bid < ask
        normal = AggregatedBook(
            symbol="BTC/USDT",
            timestamp=datetime.now(),
            best_bid=50000.0,
            best_bid_exchange=Exchange.BINANCE,
            best_bid_size=10.0,
            best_ask=50010.0,
            best_ask_exchange=Exchange.COINBASE,
            best_ask_size=8.0,
        )
        assert normal.has_cross is False


class TestArbConfig:
    """Tests for ArbConfig."""
    
    def test_default_config(self):
        config = ArbConfig()
        assert config.min_gross_profit_pct == 0.1
        assert config.min_net_profit_pct == 0.05
        assert config.default_taker_fee == 0.001
    
    def test_custom_config(self):
        config = ArbConfig(
            min_gross_profit_pct=0.2,
            min_profit_usd=50.0,
        )
        assert config.min_gross_profit_pct == 0.2
        assert config.min_profit_usd == 50.0


class TestArbOpportunity:
    """Tests for ArbOpportunity."""
    
    def test_create_opportunity(self):
        opp = ArbOpportunity(
            id="ARB-00000001",
            arb_type=ArbType.SPATIAL,
            symbol="BTC/USDT",
            detected_at=datetime.now(),
            buy_exchange=Exchange.COINBASE,
            buy_price=50000.0,
            buy_size=1.0,
            sell_exchange=Exchange.BINANCE,
            sell_price=50100.0,
            sell_size=1.0,
            gross_profit_pct=0.2,
            net_profit_pct=0.1,
            profit_usd=50.0,
            max_size=1.0,
        )
        assert opp.arb_type == ArbType.SPATIAL
        assert opp.gross_profit_pct == 0.2
    
    def test_spread_bps(self):
        opp = ArbOpportunity(
            id="ARB-00000001",
            arb_type=ArbType.SPATIAL,
            symbol="BTC/USDT",
            detected_at=datetime.now(),
            buy_exchange=Exchange.COINBASE,
            buy_price=50000.0,
            buy_size=1.0,
            sell_exchange=Exchange.BINANCE,
            sell_price=50100.0,
            sell_size=1.0,
            gross_profit_pct=0.2,
            net_profit_pct=0.1,
            profit_usd=50.0,
            max_size=1.0,
        )
        # (50100 - 50000) / 50050 * 10000 ≈ 20 bps
        assert opp.spread_bps > 19 and opp.spread_bps < 21
    
    def test_is_valid(self):
        # Valid opportunity
        valid = ArbOpportunity(
            id="ARB-00000001",
            arb_type=ArbType.SPATIAL,
            symbol="BTC/USDT",
            detected_at=datetime.now(),
            buy_exchange=Exchange.COINBASE,
            buy_price=50000.0,
            buy_size=1.0,
            sell_exchange=Exchange.BINANCE,
            sell_price=50100.0,
            sell_size=1.0,
            gross_profit_pct=0.2,
            net_profit_pct=0.1,
            profit_usd=50.0,
            max_size=1.0,
            expires_at=datetime.now() + timedelta(seconds=10),
        )
        assert valid.is_valid is True
        
        # Expired
        expired = ArbOpportunity(
            id="ARB-00000002",
            arb_type=ArbType.SPATIAL,
            symbol="BTC/USDT",
            detected_at=datetime.now() - timedelta(seconds=20),
            buy_exchange=Exchange.COINBASE,
            buy_price=50000.0,
            buy_size=1.0,
            sell_exchange=Exchange.BINANCE,
            sell_price=50100.0,
            sell_size=1.0,
            gross_profit_pct=0.2,
            net_profit_pct=0.1,
            profit_usd=50.0,
            max_size=1.0,
            expires_at=datetime.now() - timedelta(seconds=5),
        )
        assert expired.is_valid is False
    
    def test_risk_adjusted_profit(self):
        opp = ArbOpportunity(
            id="ARB-00000001",
            arb_type=ArbType.SPATIAL,
            symbol="BTC/USDT",
            detected_at=datetime.now(),
            buy_exchange=Exchange.COINBASE,
            buy_price=50000.0,
            buy_size=1.0,
            sell_exchange=Exchange.BINANCE,
            sell_price=50100.0,
            sell_size=1.0,
            gross_profit_pct=0.2,
            net_profit_pct=0.1,
            profit_usd=50.0,
            max_size=1.0,
            execution_risk=0.1,
            liquidity_risk=0.2,
            timing_risk=0.1,
        )
        # Risk factor = 1 - (0.1 + 0.2 + 0.1) / 3 = 0.867
        # Risk adjusted = 0.1 * 0.867 ≈ 0.087
        assert opp.risk_adjusted_profit > 0.08


class TestMultiExchangeFeed:
    """Tests for MultiExchangeFeed."""
    
    def test_feed_initialization(self):
        feed = MultiExchangeFeed()
        assert feed.config is not None
        assert len(feed._feeds) == 0
    
    def test_get_crossed_markets_empty(self):
        feed = MultiExchangeFeed()
        crossed = feed.get_crossed_markets()
        assert crossed == []


class TestArbDetector:
    """Tests for ArbDetector."""
    
    def test_detector_initialization(self):
        feed = MultiExchangeFeed()
        detector = ArbDetector(feed)
        
        assert detector.feed is feed
        assert detector.config is not None
    
    def test_detector_with_custom_config(self):
        feed = MultiExchangeFeed()
        config = ArbConfig(min_gross_profit_pct=0.5)
        detector = ArbDetector(feed, config)
        
        assert detector.config.min_gross_profit_pct == 0.5
    
    def test_get_active_opportunities_empty(self):
        feed = MultiExchangeFeed()
        detector = ArbDetector(feed)
        
        opps = detector.get_active_opportunities()
        assert opps == []
