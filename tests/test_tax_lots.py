"""
Tests for Tax Lot Tracking System
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from accounting.tax_lot_tracker import (
    TaxLotTracker,
    TaxLot,
    CostBasisMethod,
    GainType
)


class TestTaxLotTracker:
    """Test tax lot tracking functionality"""
    
    def test_basic_purchase(self):
        """Test recording a basic purchase"""
        tracker = TaxLotTracker()
        
        lot = tracker.record_purchase(
            symbol="AAPL",
            quantity=100,
            price=150.00,
            date=datetime(2024, 1, 15)
        )
        
        assert lot.symbol == "AAPL"
        assert lot.quantity == Decimal("100")
        assert lot.cost_per_share == Decimal("150")
        assert lot.total_cost_basis == Decimal("15000")
    
    def test_fifo_sale(self):
        """Test FIFO cost basis method"""
        tracker = TaxLotTracker(default_method=CostBasisMethod.FIFO)
        
        # Buy 100 @ $100
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        # Buy 100 @ $150
        tracker.record_purchase("AAPL", 100, 150, datetime(2024, 6, 1))
        
        # Sell 50 @ $200
        closed = tracker.record_sale(
            symbol="AAPL",
            quantity=50,
            price=200,
            date=datetime(2024, 12, 1)
        )
        
        assert len(closed) == 1
        assert closed[0].cost_basis == Decimal("5000")  # 50 * $100 (FIFO)
        assert closed[0].proceeds == Decimal("10000")
        assert closed[0].gross_gain == Decimal("5000")
    
    def test_lifo_sale(self):
        """Test LIFO cost basis method"""
        tracker = TaxLotTracker(default_method=CostBasisMethod.LIFO)
        
        # Buy 100 @ $100
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        # Buy 100 @ $150
        tracker.record_purchase("AAPL", 100, 150, datetime(2024, 6, 1))
        
        # Sell 50 @ $200
        closed = tracker.record_sale(
            symbol="AAPL",
            quantity=50,
            price=200,
            date=datetime(2024, 12, 1)
        )
        
        assert len(closed) == 1
        assert closed[0].cost_basis == Decimal("7500")  # 50 * $150 (LIFO)
        assert closed[0].gross_gain == Decimal("2500")
    
    def test_hifo_sale(self):
        """Test HIFO (highest cost first) method"""
        tracker = TaxLotTracker(default_method=CostBasisMethod.HIFO)
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        tracker.record_purchase("AAPL", 100, 150, datetime(2024, 3, 1))
        tracker.record_purchase("AAPL", 100, 120, datetime(2024, 6, 1))
        
        # Sell 50 - should come from $150 lot (highest)
        closed = tracker.record_sale("AAPL", 50, 200, datetime(2024, 12, 1))
        
        assert closed[0].cost_basis == Decimal("7500")  # 50 * $150
    
    def test_specific_lot_sale(self):
        """Test specific lot identification"""
        tracker = TaxLotTracker()
        
        lot1 = tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        lot2 = tracker.record_purchase("AAPL", 100, 150, datetime(2024, 6, 1))
        
        # Sell from specific lot
        closed = tracker.record_sale(
            symbol="AAPL",
            quantity=50,
            price=200,
            date=datetime(2024, 12, 1),
            method=CostBasisMethod.SPECIFIC_ID,
            specific_lot_ids=[lot2.lot_id]
        )
        
        assert closed[0].lot_id == lot2.lot_id
        assert closed[0].cost_basis == Decimal("7500")  # From $150 lot
    
    def test_short_term_gain(self):
        """Test short-term gain classification"""
        tracker = TaxLotTracker()
        
        # Buy and sell within 1 year
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 6, 1))
        closed = tracker.record_sale("AAPL", 100, 150, datetime(2024, 12, 1))
        
        assert closed[0].gain_type == GainType.SHORT_TERM
    
    def test_long_term_gain(self):
        """Test long-term gain classification"""
        tracker = TaxLotTracker()
        
        # Buy and sell after more than 1 year
        tracker.record_purchase("AAPL", 100, 100, datetime(2023, 1, 1))
        closed = tracker.record_sale("AAPL", 100, 150, datetime(2024, 6, 1))
        
        assert closed[0].gain_type == GainType.LONG_TERM
    
    def test_wash_sale_detection(self):
        """Test wash sale detection and adjustment"""
        tracker = TaxLotTracker(wash_sale_window_days=30)
        
        # Buy
        tracker.record_purchase("AAPL", 100, 150, datetime(2024, 1, 1))
        
        # Sell at loss
        tracker.record_sale("AAPL", 100, 100, datetime(2024, 6, 1))
        
        # Repurchase within 30 days
        new_lot = tracker.record_purchase("AAPL", 100, 105, datetime(2024, 6, 15))
        
        # Wash sale should be detected
        assert new_lot.wash_sale_adjustment > 0
    
    def test_unrealized_gains(self):
        """Test unrealized gains calculation"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        tracker.record_purchase("MSFT", 50, 200, datetime(2024, 1, 1))
        
        gains = tracker.get_unrealized_gains({
            "AAPL": 150,
            "MSFT": 250
        })
        
        assert gains["total_unrealized"] == 7500  # (150-100)*100 + (250-200)*50
    
    def test_realized_gains_by_year(self):
        """Test realized gains reporting by tax year"""
        tracker = TaxLotTracker()
        
        # 2024 trades
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        tracker.record_sale("AAPL", 100, 150, datetime(2024, 6, 1))
        
        gains = tracker.get_realized_gains(year=2024)
        
        assert gains["total_realized"] == 5000
        assert gains["short_term_gains"] == 5000
    
    def test_tax_loss_harvesting(self):
        """Test tax loss harvesting opportunity detection"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 200, datetime(2024, 1, 1))  # Underwater
        tracker.record_purchase("MSFT", 50, 100, datetime(2024, 1, 1))   # Profitable
        
        opportunities = tracker.find_tax_loss_harvesting_opportunities(
            prices={"AAPL": 150, "MSFT": 150},
            min_loss=100
        )
        
        assert len(opportunities) == 1
        assert opportunities[0].symbol == "AAPL"
        assert opportunities[0].unrealized_loss < 0
    
    def test_form_8949_export(self):
        """Test IRS Form 8949 export"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        tracker.record_sale("AAPL", 100, 150, datetime(2024, 6, 1))
        
        form_data = tracker.export_form_8949(2024)
        
        assert form_data["tax_year"] == 2024
        assert len(form_data["part_i_short_term"]["transactions"]) == 1
        assert form_data["schedule_d_summary"]["net_gain_loss"] == "5000.00"
    
    def test_partial_lot_sale(self):
        """Test selling partial lot"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        
        # Sell only 30 shares
        closed = tracker.record_sale("AAPL", 30, 150, datetime(2024, 6, 1))
        
        assert closed[0].quantity == Decimal("30")
        assert closed[0].cost_basis == Decimal("3000")
        
        # 70 shares should remain
        summary = tracker.get_position_summary("AAPL")
        assert Decimal(summary["total_quantity"]) == Decimal("70")
    
    def test_save_and_load_state(self, tmp_path):
        """Test state persistence"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        tracker.record_purchase("MSFT", 50, 200, datetime(2024, 1, 1))
        tracker.record_sale("AAPL", 50, 150, datetime(2024, 6, 1))
        
        filepath = tmp_path / "tax_lots.json"
        tracker.save_state(str(filepath))
        
        # Load into new tracker
        loaded = TaxLotTracker.load_state(str(filepath))
        
        assert len(loaded.open_lots["AAPL"]) == 1
        assert len(loaded.open_lots["MSFT"]) == 1
        assert len(loaded.closed_lots) == 1
    
    def test_min_tax_optimization(self):
        """Test minimum tax lot selection"""
        tracker = TaxLotTracker()
        
        # Mix of short and long term lots
        tracker.record_purchase("AAPL", 100, 100, datetime(2022, 1, 1))  # Long term, gain
        tracker.record_purchase("AAPL", 100, 200, datetime(2024, 6, 1))  # Short term, loss
        
        # MIN_TAX should prefer selling the loss first
        closed = tracker.record_sale(
            "AAPL", 50, 150,
            datetime(2024, 12, 1),
            method=CostBasisMethod.MIN_TAX
        )
        
        # Should pick the $200 lot (short term loss)
        assert closed[0].cost_basis == Decimal("10000")  # 50 * $200


class TestTaxLotEdgeCases:
    """Test edge cases in tax lot tracking"""
    
    def test_zero_quantity_removal(self):
        """Test that empty lots are removed"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        tracker.record_sale("AAPL", 100, 150, datetime(2024, 6, 1))
        
        assert len(tracker.open_lots["AAPL"]) == 0
    
    def test_insufficient_shares_error(self):
        """Test error on selling more than owned"""
        tracker = TaxLotTracker()
        
        tracker.record_purchase("AAPL", 100, 100, datetime(2024, 1, 1))
        
        with pytest.raises(ValueError, match="Insufficient shares"):
            tracker.record_sale("AAPL", 200, 150, datetime(2024, 6, 1))
    
    def test_no_position_error(self):
        """Test error on selling non-existent position"""
        tracker = TaxLotTracker()
        
        with pytest.raises(ValueError, match="No open lots"):
            tracker.record_sale("AAPL", 100, 150, datetime(2024, 6, 1))
    
    def test_dividend_reinvestment(self):
        """Test dividend reinvestment lot creation"""
        tracker = TaxLotTracker()
        
        lot = tracker.record_purchase(
            symbol="AAPL",
            quantity=5.5,
            price=150,
            date=datetime(2024, 3, 15),
            acquisition_type="dividend_reinvest"
        )
        
        assert lot.acquisition_type == "dividend_reinvest"
        assert lot.quantity == Decimal("5.5")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
