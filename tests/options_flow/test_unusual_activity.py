"""
Tests for Options Flow - Unusual Activity Detection
"""

import pytest
from datetime import datetime, timedelta
from options_flow.unusual_activity import (
    UnusualActivityDetector,
    DetectorConfig,
    OptionsContract,
    OptionsTrade,
    OptionType,
    TradeSide,
    OptionsActivityType,
    UnusualActivity,
)


class TestOptionsContract:
    """Tests for OptionsContract dataclass."""
    
    def test_create_call_contract(self):
        contract = OptionsContract(
            symbol="SPY240129C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime(2024, 1, 29),
            option_type=OptionType.CALL,
        )
        assert contract.underlying == "SPY"
        assert contract.strike == 500.0
        assert contract.option_type == OptionType.CALL
    
    def test_dte_calculation(self):
        # Contract expiring in 7 days
        future_date = datetime.now() + timedelta(days=7)
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=future_date,
            option_type=OptionType.CALL,
        )
        assert contract.dte == 7
    
    def test_is_weekly(self):
        # Weekly option (< 7 DTE)
        short_expiry = datetime.now() + timedelta(days=5)
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=short_expiry,
            option_type=OptionType.CALL,
        )
        assert contract.is_weekly is True
        
        # Monthly option (> 7 DTE)
        long_expiry = datetime.now() + timedelta(days=14)
        contract2 = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=long_expiry,
            option_type=OptionType.CALL,
        )
        assert contract2.is_weekly is False
    
    def test_moneyness(self):
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
        # Strike 100, Spot 100 = 1.0 moneyness (ATM)
        assert contract.moneyness(100.0) == 1.0
        # Strike 100, Spot 110 = 0.909 moneyness (ITM call)
        assert round(contract.moneyness(110.0), 3) == 0.909
    
    def test_is_otm_call(self):
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=110.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
        # Call strike 110, spot 100 = OTM
        assert contract.is_otm(100.0) is True
        # Call strike 110, spot 115 = ITM
        assert contract.is_otm(115.0) is False
    
    def test_is_otm_put(self):
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=90.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.PUT,
        )
        # Put strike 90, spot 100 = OTM
        assert contract.is_otm(100.0) is True
        # Put strike 90, spot 85 = ITM
        assert contract.is_otm(85.0) is False


class TestOptionsTrade:
    """Tests for OptionsTrade dataclass."""
    
    def test_create_trade(self):
        contract = OptionsContract(
            symbol="SPY240129C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime(2024, 1, 29),
            option_type=OptionType.CALL,
        )
        trade = OptionsTrade(
            contract=contract,
            timestamp=datetime.now(),
            price=5.50,
            size=100,
            premium=55000,  # 5.50 * 100 * 100
            side=TradeSide.BUY,
            exchange="CBOE",
            spot_price=498.0,
        )
        assert trade.size == 100
        assert trade.premium == 55000
        assert trade.side == TradeSide.BUY
    
    def test_notional_value(self):
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
        trade = OptionsTrade(
            contract=contract,
            timestamp=datetime.now(),
            price=2.00,
            size=50,
            premium=10000,
            side=TradeSide.BUY,
            exchange="TEST",
            spot_price=100.0,
        )
        # Notional = 50 contracts * 100 shares * $100 spot = $500,000
        assert trade.notional == 500000


class TestDetectorConfig:
    """Tests for DetectorConfig."""
    
    def test_default_config(self):
        config = DetectorConfig()
        assert config.min_premium == 25_000
        assert config.unusual_volume_multiplier == 3.0
        assert config.whale_premium_threshold == 1_000_000
    
    def test_custom_config(self):
        config = DetectorConfig(
            min_premium=50_000,
            whale_premium_threshold=500_000,
        )
        assert config.min_premium == 50_000
        assert config.whale_premium_threshold == 500_000


class TestUnusualActivityDetector:
    """Tests for UnusualActivityDetector."""
    
    @pytest.fixture
    def detector(self):
        return UnusualActivityDetector()
    
    @pytest.fixture
    def sample_contract(self):
        return OptionsContract(
            symbol="SPY240129C500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
    
    def test_detector_initialization(self, detector):
        assert detector.config is not None
        assert len(detector._trade_buffer) == 0
    
    def test_whale_detection(self, detector, sample_contract):
        """Test whale alert detection."""
        # Create whale-sized trade (>$1M premium)
        trade = OptionsTrade(
            contract=sample_contract,
            timestamp=datetime.now(),
            price=50.0,
            size=500,
            premium=2_500_000,  # $2.5M
            side=TradeSide.BUY,
            exchange="CBOE",
            spot_price=498.0,
        )
        
        whale = detector._detect_whale(trade)
        assert whale is not None
        assert whale.activity_type == OptionsActivityType.WHALE_ALERT
        assert whale.score >= 50
    
    def test_no_whale_for_small_trade(self, detector, sample_contract):
        """Test that small trades don't trigger whale alert."""
        trade = OptionsTrade(
            contract=sample_contract,
            timestamp=datetime.now(),
            price=2.0,
            size=10,
            premium=2_000,  # $2K - way below threshold
            side=TradeSide.BUY,
            exchange="CBOE",
            spot_price=498.0,
        )
        
        whale = detector._detect_whale(trade)
        assert whale is None
    
    def test_unusual_volume_detection(self, detector, sample_contract):
        """Test unusual volume detection."""
        trade = OptionsTrade(
            contract=sample_contract,
            timestamp=datetime.now(),
            price=5.0,
            size=100,
            premium=50_000,
            side=TradeSide.BUY,
            exchange="CBOE",
            spot_price=498.0,
            open_interest=100,  # OI = 100
            volume_prior=250,  # Volume already 250
        )
        
        # Volume (250 + 100 = 350) / OI (100) = 3.5x -> unusual
        unusual = detector._detect_unusual_volume(trade)
        assert unusual is not None
        assert unusual.activity_type == OptionsActivityType.UNUSUAL_VOLUME
    
    def test_callback_registration(self, detector):
        """Test callback registration and notification."""
        received = []
        
        def callback(activity: UnusualActivity):
            received.append(activity)
        
        detector.register_callback(callback)
        assert len(detector._callbacks) == 1
    
    def test_calculate_score(self, detector, sample_contract):
        """Test score calculation."""
        trade = OptionsTrade(
            contract=sample_contract,
            timestamp=datetime.now(),
            price=10.0,
            size=200,
            premium=200_000,
            side=TradeSide.BUY,
            exchange="CBOE",
            condition="AA",  # Above ask
            spot_price=498.0,
        )
        
        score = detector._calculate_score(trade, volume_ratio=2.0)
        assert 0 <= score <= 100


class TestUnusualActivity:
    """Tests for UnusualActivity dataclass."""
    
    def test_bullish_call_buy(self):
        """Call buy = bullish."""
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
        trade = OptionsTrade(
            contract=contract,
            timestamp=datetime.now(),
            price=5.0,
            size=100,
            premium=50_000,
            side=TradeSide.BUY,
            exchange="TEST",
        )
        activity = UnusualActivity(
            activity_type=OptionsActivityType.UNUSUAL_VOLUME,
            trade=trade,
            score=75.0,
            description="Test",
        )
        assert activity.is_bullish is True
        assert activity.is_bearish is False
    
    def test_bearish_call_sell(self):
        """Call sell = bearish."""
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
        trade = OptionsTrade(
            contract=contract,
            timestamp=datetime.now(),
            price=5.0,
            size=100,
            premium=50_000,
            side=TradeSide.SELL,
            exchange="TEST",
        )
        activity = UnusualActivity(
            activity_type=OptionsActivityType.UNUSUAL_VOLUME,
            trade=trade,
            score=75.0,
            description="Test",
        )
        assert activity.is_bullish is False
        assert activity.is_bearish is True
    
    def test_to_dict(self):
        """Test serialization."""
        contract = OptionsContract(
            symbol="TEST",
            underlying="TEST",
            strike=100.0,
            expiry=datetime.now() + timedelta(days=7),
            option_type=OptionType.CALL,
        )
        trade = OptionsTrade(
            contract=contract,
            timestamp=datetime.now(),
            price=5.0,
            size=100,
            premium=50_000,
            side=TradeSide.BUY,
            exchange="TEST",
        )
        activity = UnusualActivity(
            activity_type=OptionsActivityType.WHALE_ALERT,
            trade=trade,
            score=85.0,
            description="Whale alert",
        )
        
        data = activity.to_dict()
        assert data["activity_type"] == "whale_alert"
        assert data["symbol"] == "TEST"
        assert data["score"] == 85.0
        assert data["is_bullish"] is True
