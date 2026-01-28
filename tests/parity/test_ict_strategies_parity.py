"""
ICT Strategies Parity Tests
===========================
Verifies ICT strategies match quant-platform behavior.
"""
import pytest
from datetime import datetime


class TestICTConceptsParity:
    """Test ICT concepts match platform definitions."""

    def test_bias_enum_values(self):
        """Verify Bias enum values match platform."""
        from backend.strategies import Bias

        assert Bias.BULLISH.value == "bullish"
        assert Bias.BEARISH.value == "bearish"
        assert Bias.NEUTRAL.value == "neutral"

    def test_zone_type_enum_values(self):
        """Verify ZoneType enum values match platform."""
        from backend.strategies import ZoneType

        assert ZoneType.FVG.value == "fvg"
        assert ZoneType.ORDER_BLOCK.value == "order_block"
        assert ZoneType.BREAKER.value == "breaker"
        assert ZoneType.MITIGATION.value == "mitigation"
        assert ZoneType.LIQUIDITY.value == "liquidity"
        assert ZoneType.INDUCEMENT.value == "inducement"

    def test_all_zone_types_present(self):
        """Verify all required zone types exist."""
        from backend.strategies import ZoneType

        required_zones = ["fvg", "order_block", "breaker", "mitigation", "liquidity", "inducement"]
        actual_zones = [z.value for z in ZoneType]
        for zone in required_zones:
            assert zone in actual_zones, f"Missing zone type: {zone}"


class TestFairValueGapParity:
    """Test Fair Value Gap implementation."""

    def test_fvg_structure(self):
        """Verify FVG has required fields."""
        from backend.strategies import FairValueGap, Bias

        fvg = FairValueGap(
            timestamp=datetime.now(),
            high=100.5,
            low=99.5,
            bias=Bias.BULLISH,
        )

        assert hasattr(fvg, "timestamp")
        assert hasattr(fvg, "high")
        assert hasattr(fvg, "low")
        assert hasattr(fvg, "bias")
        assert hasattr(fvg, "filled")
        assert hasattr(fvg, "filled_pct")

    def test_fvg_midpoint_calculation(self):
        """Verify FVG midpoint calculation."""
        from backend.strategies import FairValueGap, Bias

        fvg = FairValueGap(
            timestamp=datetime.now(),
            high=100.0,
            low=98.0,
            bias=Bias.BULLISH,
        )

        assert fvg.midpoint == 99.0

    def test_fvg_size_calculation(self):
        """Verify FVG size calculation."""
        from backend.strategies import FairValueGap, Bias

        fvg = FairValueGap(
            timestamp=datetime.now(),
            high=100.0,
            low=98.0,
            bias=Bias.BULLISH,
        )

        assert fvg.size == 2.0

    def test_fvg_fill_detection_bullish(self):
        """Verify bullish FVG fill detection."""
        from backend.strategies import FairValueGap, Bias

        fvg = FairValueGap(
            timestamp=datetime.now(),
            high=100.0,
            low=98.0,
            bias=Bias.BULLISH,
        )

        # Price above gap - not filled
        assert fvg.check_fill(101.0) is False

        # Price in gap - partially filled
        assert fvg.check_fill(99.0) is False
        assert fvg.filled_pct > 0

        # Price below gap - fully filled
        assert fvg.check_fill(97.0) is True
        assert fvg.filled is True

    def test_fvg_serialization(self):
        """Verify FVG serialization."""
        from backend.strategies import FairValueGap, Bias

        fvg = FairValueGap(
            timestamp=datetime.now(),
            high=100.0,
            low=98.0,
            bias=Bias.BULLISH,
        )

        data = fvg.to_dict()
        assert "timestamp" in data
        assert "high" in data
        assert "low" in data
        assert "bias" in data
        assert data["bias"] == "bullish"


class TestOrderBlockParity:
    """Test Order Block implementation."""

    def test_order_block_structure(self):
        """Verify Order Block has required fields."""
        from backend.strategies import OrderBlock, Bias

        ob = OrderBlock(
            timestamp=datetime.now(),
            high=100.0,
            low=99.0,
            bias=Bias.BULLISH,
        )

        assert hasattr(ob, "timestamp")
        assert hasattr(ob, "high")
        assert hasattr(ob, "low")
        assert hasattr(ob, "bias")
        assert hasattr(ob, "is_valid")
        assert hasattr(ob, "tested_count")
        assert hasattr(ob, "broken")

    def test_order_block_test_detection(self):
        """Verify Order Block test detection."""
        from backend.strategies import OrderBlock, Bias

        ob = OrderBlock(
            timestamp=datetime.now(),
            high=100.0,
            low=99.0,
            bias=Bias.BULLISH,
        )

        # Test into the zone
        assert ob.check_test(100.5, 99.5) is True
        assert ob.tested_count == 1

        # Price below - breaks the OB
        ob.check_test(99.5, 98.0)
        assert ob.broken is True
        assert ob.is_valid is False


class TestLiquidityLevelParity:
    """Test Liquidity Level implementation."""

    def test_liquidity_level_structure(self):
        """Verify Liquidity Level has required fields."""
        from backend.strategies.ict_strategies import LiquidityLevel

        level = LiquidityLevel(
            timestamp=datetime.now(),
            price=100.0,
            level_type="equal_highs",
        )

        assert hasattr(level, "timestamp")
        assert hasattr(level, "price")
        assert hasattr(level, "level_type")
        assert hasattr(level, "strength")
        assert hasattr(level, "swept")

    def test_liquidity_sweep_detection(self):
        """Verify liquidity sweep detection."""
        from backend.strategies.ict_strategies import LiquidityLevel

        level = LiquidityLevel(
            timestamp=datetime.now(),
            price=100.0,
            level_type="equal_highs",
        )

        # Price doesn't reach level
        assert level.check_sweep(99.5, 98.0, datetime.now()) is False

        # Price sweeps the level
        assert level.check_sweep(100.5, 99.0, datetime.now()) is True
        assert level.swept is True
        assert level.swept_at is not None


class TestICTAnalyzerParity:
    """Test ICT Analyzer implementation."""

    def test_analyzer_initialization(self):
        """Verify analyzer initializes correctly."""
        from backend.strategies import ICTAnalyzer

        analyzer = ICTAnalyzer()

        assert hasattr(analyzer, "fvgs")
        assert hasattr(analyzer, "order_blocks")
        assert hasattr(analyzer, "liquidity_levels")
        assert hasattr(analyzer, "htf_bias")
        assert hasattr(analyzer, "ltf_bias")

    def test_kill_zone_times(self):
        """Verify kill zone times match platform."""
        from backend.strategies import ICTAnalyzer
        from datetime import time

        analyzer = ICTAnalyzer()

        # Check kill zones are defined
        assert "asian" in analyzer.KILL_ZONES
        assert "london" in analyzer.KILL_ZONES
        assert "ny_open" in analyzer.KILL_ZONES
        assert "ny_close" in analyzer.KILL_ZONES

        # Check NY open times (7AM - 10AM)
        start, end = analyzer.KILL_ZONES["ny_open"]
        assert start == time(7, 0)
        assert end == time(10, 0)

    def test_analyze_candles_output(self):
        """Verify analyze_candles returns expected structure."""
        from backend.strategies import ICTAnalyzer

        analyzer = ICTAnalyzer()

        # Create test data
        closes = [100 + i * 0.1 for i in range(60)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        opens = [c - 0.1 for c in closes]
        timestamps = [datetime.now()] * len(closes)

        result = analyzer.analyze_candles(opens, highs, lows, closes, timestamps)

        assert "htf_bias" in result
        assert "ltf_bias" in result
        assert "fvg_count" in result
        assert "order_block_count" in result

    def test_get_kill_zone(self):
        """Verify kill zone detection."""
        from backend.strategies import ICTAnalyzer
        from datetime import time

        analyzer = ICTAnalyzer()

        # NY open is 7-10 AM
        assert analyzer.get_kill_zone(time(8, 30)) == "ny_open"

        # Outside kill zones
        assert analyzer.get_kill_zone(time(14, 0)) is None


class TestICTSetupParity:
    """Test ICT Setup structure."""

    def test_setup_structure(self):
        """Verify ICT Setup has required fields."""
        from backend.strategies.ict_strategies import ICTSetup, Bias

        setup = ICTSetup(
            setup_id="test_001",
            timestamp=datetime.now(),
            symbol="ES",
            bias=Bias.BULLISH,
        )

        assert hasattr(setup, "setup_id")
        assert hasattr(setup, "entry_price")
        assert hasattr(setup, "stop_loss")
        assert hasattr(setup, "take_profit")
        assert hasattr(setup, "risk_reward")
        assert hasattr(setup, "confidence")

    def test_risk_reward_calculation(self):
        """Verify risk/reward calculation."""
        from backend.strategies.ict_strategies import ICTSetup, Bias

        setup = ICTSetup(
            setup_id="test_001",
            timestamp=datetime.now(),
            symbol="ES",
            bias=Bias.BULLISH,
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
        )

        rr = setup.calculate_risk_reward()
        assert rr == 3.0  # (106-100) / (100-98) = 6/2 = 3


class TestICTHelperFunctionsParity:
    """Test ICT helper functions."""

    def test_market_structure_shift_detection(self):
        """Verify MSS detection."""
        from backend.strategies.ict_strategies import detect_market_structure_shift, Bias

        # Create trending up data
        closes = [100 + i for i in range(15)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]

        shift, new_bias = detect_market_structure_shift(highs, lows, closes)
        assert shift is True
        assert new_bias == Bias.BULLISH

    def test_optimal_trade_entry_zones(self):
        """Verify OTE zone calculation."""
        from backend.strategies.ict_strategies import calculate_optimal_trade_entry, Bias

        result = calculate_optimal_trade_entry(
            swing_high=100.0,
            swing_low=90.0,
            bias=Bias.BULLISH,
        )

        # 62% retracement = 100 - (10 * 0.62) = 93.8
        # 79% retracement = 100 - (10 * 0.79) = 92.1
        assert "ote_high" in result
        assert "ote_low" in result
        assert "sweet_spot" in result
        assert result["ote_high"] == pytest.approx(93.8, rel=0.01)
        assert result["ote_low"] == pytest.approx(92.1, rel=0.01)
