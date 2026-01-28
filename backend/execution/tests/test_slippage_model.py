"""
Tests for Almgren-Chriss Slippage Model
========================================
Critical tests for market impact modeling.

These tests verify that:
1. Slippage increases with order size
2. Slippage decreases with volume (more liquid = less impact)
3. Slippage increases with volatility
4. Backtest adjustment correctly penalizes trades
5. Buy/sell asymmetry is handled correctly
"""

import pytest
import numpy as np
from datetime import datetime

# Import the slippage model
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from execution.execution_algorithms import (
    AlmgrenChrissSlippageModel,
    SlippageEstimate,
    estimate_slippage
)


class TestAlmgrenChrissSlippageModel:
    """Test suite for Almgren-Chriss slippage model."""
    
    @pytest.fixture
    def model(self):
        """Create a default model instance."""
        return AlmgrenChrissSlippageModel()
    
    @pytest.fixture
    def aggressive_model(self):
        """Create an aggressive (higher impact) model with elevated coefficients."""
        # Higher than default (0.142, 0.314) for aggressive execution
        return AlmgrenChrissSlippageModel(eta=0.25, gamma=0.50)
    
    # ==================== Basic Functionality ====================
    
    def test_zero_order_size_returns_zero_slippage(self, model):
        """Zero order size should have zero slippage."""
        estimate = model.calculate_slippage(
            order_size=0,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0
        )
        assert estimate.total_slippage_bps == 0
        assert estimate.total_slippage_dollars == 0
    
    def test_zero_volume_returns_zero_slippage(self, model):
        """Zero volume should handle gracefully."""
        estimate = model.calculate_slippage(
            order_size=1000,
            daily_volume=0,
            volatility=0.02,
            price=100.0
        )
        assert estimate.total_slippage_bps == 0
    
    def test_basic_slippage_calculation(self, model):
        """Basic slippage should be positive and reasonable."""
        estimate = model.calculate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0
        )
        
        assert estimate.total_slippage_bps > 0
        assert estimate.total_slippage_bps < 100  # Less than 1%
        assert estimate.total_slippage_dollars > 0
        assert estimate.permanent_impact >= 0
        assert estimate.temporary_impact >= 0
    
    # ==================== Monotonicity Tests ====================
    
    def test_slippage_increases_with_order_size(self, model):
        """Larger orders should have more slippage."""
        small_order = model.calculate_slippage(
            order_size=1_000,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0
        )
        
        large_order = model.calculate_slippage(
            order_size=100_000,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0
        )
        
        assert large_order.total_slippage_bps > small_order.total_slippage_bps
    
    def test_slippage_decreases_with_volume(self, model):
        """More liquid markets should have less slippage."""
        illiquid = model.calculate_slippage(
            order_size=10_000,
            daily_volume=100_000,  # Low volume
            volatility=0.02,
            price=100.0
        )
        
        liquid = model.calculate_slippage(
            order_size=10_000,
            daily_volume=10_000_000,  # High volume
            volatility=0.02,
            price=100.0
        )
        
        assert illiquid.total_slippage_bps > liquid.total_slippage_bps
    
    def test_slippage_increases_with_volatility(self, model):
        """Higher volatility should mean more slippage."""
        low_vol = model.calculate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            volatility=0.01,  # 1% daily vol
            price=100.0
        )
        
        high_vol = model.calculate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            volatility=0.05,  # 5% daily vol
            price=100.0
        )
        
        assert high_vol.total_slippage_bps > low_vol.total_slippage_bps
    
    # ==================== Realistic Values ====================
    
    def test_realistic_equity_slippage(self, model):
        """
        Test realistic slippage for a typical equity trade.
        10K shares of a $100 stock with 1M daily volume.
        
        Using empirically-calibrated Almgren-Chriss (eta=0.142, gamma=0.314):
        - Participation: 10K/1M = 1%
        - Daily vol: 2%
        - Expected slippage: ~5-15 bps
        """
        estimate = model.calculate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0
        )
        
        # With calibrated params, 1% participation should give ~5-20 bps
        assert 2 < estimate.total_slippage_bps < 50
        
        # Dollar slippage: 10K * $100 * ~10bps = ~$100-500
        assert 50 < estimate.total_slippage_dollars < 5_000
    
    def test_realistic_futures_slippage(self, model):
        """
        Test realistic slippage for ES futures.
        1 contract = ~$250K notional, high volume.
        """
        # ES futures: 1 contract ≈ 5000 * $50 = $250K notional
        # Daily volume: ~1.5M contracts
        estimate = model.calculate_slippage(
            order_size=10,  # 10 contracts
            daily_volume=1_500_000,
            volatility=0.015,  # ES typically 1-2% daily
            price=5000.0  # ES price
        )
        
        # Should be very small for highly liquid futures
        assert estimate.total_slippage_bps < 5
    
    def test_large_order_high_impact(self, model):
        """
        Large order relative to volume should have significant impact.
        Trading 10% of daily volume.
        
        With 10% participation and calibrated params:
        - Permanent: 0.314 * 0.02 * 0.10 = 0.000628 = 6.28 bps
        - Temporary: 0.142 * 0.02 * sqrt(0.10/0.154) = higher
        - Total: ~15-50 bps expected
        """
        estimate = model.calculate_slippage(
            order_size=100_000,
            daily_volume=1_000_000,  # 10% of volume
            volatility=0.02,
            price=100.0
        )
        
        # 10% of volume should have meaningful impact (10-100 bps)
        assert estimate.total_slippage_bps > 10
        assert estimate.participation_rate >= 0.10
    
    # ==================== Aggressive vs Passive ====================
    
    def test_aggressive_execution_more_slippage(self, model, aggressive_model):
        """Aggressive execution should cost more."""
        passive = model.calculate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0,
            execution_time_hours=4.0  # Slow
        )
        
        aggressive = aggressive_model.calculate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            volatility=0.02,
            price=100.0,
            execution_time_hours=0.5  # Fast
        )
        
        assert aggressive.total_slippage_bps > passive.total_slippage_bps
    
    # ==================== Fill Price Tests ====================
    
    def test_buy_fill_price_higher(self, model):
        """Buy orders should fill at higher prices."""
        fill_price, slippage = model.get_realistic_fills(
            order_price=100.0,
            order_size=10_000,
            side='buy',
            daily_volume=1_000_000,
            volatility=0.02
        )
        
        assert fill_price > 100.0
        assert slippage > 0
    
    def test_sell_fill_price_lower(self, model):
        """Sell orders should fill at lower prices."""
        fill_price, slippage = model.get_realistic_fills(
            order_price=100.0,
            order_size=10_000,
            side='sell',
            daily_volume=1_000_000,
            volatility=0.02
        )
        
        assert fill_price < 100.0
        assert slippage > 0
    
    def test_buy_sell_symmetric_slippage(self, model):
        """Buy and sell slippage dollars should be equal."""
        _, buy_slippage = model.get_realistic_fills(
            order_price=100.0,
            order_size=10_000,
            side='buy',
            daily_volume=1_000_000,
            volatility=0.02
        )
        
        _, sell_slippage = model.get_realistic_fills(
            order_price=100.0,
            order_size=10_000,
            side='sell',
            daily_volume=1_000_000,
            volatility=0.02
        )
        
        assert abs(buy_slippage - sell_slippage) < 0.01  # Nearly equal


class TestBacktestAdjustment:
    """Test backtest slippage application."""
    
    @pytest.fixture
    def model(self):
        return AlmgrenChrissSlippageModel()
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade DataFrame."""
        import pandas as pd
        return pd.DataFrame({
            'timestamp': [datetime(2024, 1, i) for i in range(1, 6)],
            'symbol': ['AAPL'] * 5,
            'side': ['buy', 'sell', 'buy', 'sell', 'buy'],
            'size': [1000, 2000, 500, 1500, 3000],
            'price': [150.0, 152.0, 148.0, 155.0, 153.0],
            'volume': [50_000_000] * 5,  # AAPL has high volume
            'volatility': [0.015] * 5
        })
    
    def test_backtest_adds_slippage_columns(self, model, sample_trades):
        """Backtest adjustment should add slippage columns."""
        adjusted = model.apply_to_backtest(
            sample_trades,
            volume_col='volume',
            size_col='size',
            price_col='price',
            volatility_col='volatility',
            side_col='side'
        )
        
        assert 'slippage_bps' in adjusted.columns
        assert 'slippage_dollars' in adjusted.columns
        assert 'adjusted_price' in adjusted.columns
        assert 'pnl_impact' in adjusted.columns
    
    def test_backtest_buy_price_increased(self, model, sample_trades):
        """Buy trades should have higher adjusted prices."""
        adjusted = model.apply_to_backtest(
            sample_trades,
            volume_col='volume',
            size_col='size',
            price_col='price',
            volatility_col='volatility',
            side_col='side'
        )
        
        # Check buys have higher prices
        buys = adjusted[adjusted['side'] == 'buy']
        assert all(buys['adjusted_price'] >= buys['price'])
    
    def test_backtest_sell_price_decreased(self, model, sample_trades):
        """Sell trades should have lower adjusted prices."""
        adjusted = model.apply_to_backtest(
            sample_trades,
            volume_col='volume',
            size_col='size',
            price_col='price',
            volatility_col='volatility',
            side_col='side'
        )
        
        # Check sells have lower prices
        sells = adjusted[adjusted['side'] == 'sell']
        assert all(sells['adjusted_price'] <= sells['price'])
    
    def test_backtest_pnl_impact_negative(self, model, sample_trades):
        """P&L impact should always be negative (slippage is a cost)."""
        adjusted = model.apply_to_backtest(
            sample_trades,
            volume_col='volume',
            size_col='size',
            price_col='price',
            volatility_col='volatility',
            side_col='side'
        )
        
        assert all(adjusted['pnl_impact'] <= 0)


class TestEstimateSlippageFunction:
    """Test the convenience function."""
    
    def test_quick_estimate_returns_bps(self):
        """Quick estimate should return basis points."""
        bps = estimate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            price=100.0
        )
        
        assert isinstance(bps, float)
        assert bps > 0
        assert bps < 100  # Less than 1%
    
    def test_aggressive_flag_increases_slippage(self):
        """Aggressive execution should have more slippage."""
        passive = estimate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            price=100.0,
            aggressive=False
        )
        
        aggressive = estimate_slippage(
            order_size=10_000,
            daily_volume=1_000_000,
            price=100.0,
            aggressive=True
        )
        
        assert aggressive > passive


# ==================== Integration Tests ====================

class TestSlippageIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_prop_firm_scenario(self):
        """
        Test realistic prop firm trading scenario.
        $50K account, 6 max contracts ES futures.
        """
        model = AlmgrenChrissSlippageModel()
        
        # 6 ES contracts
        estimate = model.calculate_slippage(
            order_size=6,
            daily_volume=1_500_000,  # ES daily volume
            volatility=0.012,  # ES typical vol
            price=5000.0,  # ES price
            execution_time_hours=0.1  # Quick execution
        )
        
        # Even quick execution of 6 contracts should be tiny
        assert estimate.total_slippage_bps < 2
        
        # Dollar impact on 6 contracts * $50 * 5000 = $1.5M notional
        # At 1 bp, that's $150
        assert estimate.total_slippage_dollars < 500
    
    def test_day_trading_scenario(self):
        """
        Test high-frequency day trading with multiple trades.
        10 trades per day, 1000 shares each of a mid-cap stock.
        
        Per trade: 1K shares / 500K volume = 0.2% participation
        Expected per trade: ~3-10 bps on $50K notional = $15-50
        Total for 10 trades: $150-500
        """
        model = AlmgrenChrissSlippageModel()
        
        total_slippage = 0
        trades_per_day = 10
        shares_per_trade = 1000
        
        for _ in range(trades_per_day):
            estimate = model.calculate_slippage(
                order_size=shares_per_trade,
                daily_volume=500_000,  # Mid-cap stock
                volatility=0.025,      # 2.5% daily vol
                price=50.0
            )
            total_slippage += estimate.total_slippage_dollars
        
        # 10 trades * ~$15-50 slippage = ~$150-500 daily drag
        assert 50 < total_slippage < 2000
        
        # This is a significant cost for a small account!
        print(f"Daily slippage drag: ${total_slippage:.2f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
