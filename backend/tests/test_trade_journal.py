"""
Trade Journal Tests
===================
Tests for the TradeJournal implementation.
"""

import os
import pytest
import tempfile
from datetime import datetime
import uuid


class TestTradeJournal:
    """Tests for TradeJournal functionality."""

    @pytest.fixture
    def journal(self):
        """Create a fresh TradeJournal with temp database."""
        from services.trade_journal import TradeJournal

        # Use temp file for testing
        temp_db = tempfile.mktemp(suffix=".db")
        journal = TradeJournal(db_path=temp_db)

        yield journal

        # Close connection first
        journal.close()

        # Cleanup - ignore errors on Windows due to file locking
        try:
            if os.path.exists(temp_db):
                os.remove(temp_db)
        except PermissionError:
            pass  # Windows file locking - file will be cleaned up later

    @pytest.fixture
    def sample_trade(self):
        """Create a sample TradeRecord."""
        from contracts.journal import TradeRecord

        return TradeRecord(
            trade_id=str(uuid.uuid4()),
            symbol="SPY",
            side="buy",
            quantity=100,
            entry_price=450.00,
            entry_time=datetime.now(),
            entry_order_id="order_123"
        )

    def test_record_trade(self, journal, sample_trade):
        """Test recording a new trade."""
        trade_id = journal.record_trade(sample_trade)
        assert trade_id == sample_trade.trade_id

        # Verify trade is stored
        retrieved = journal.get_trade(trade_id)
        assert retrieved is not None
        assert retrieved.symbol == "SPY"
        assert retrieved.quantity == 100

    def test_update_trade_with_exit(self, journal, sample_trade):
        """Test updating a trade with exit info."""
        journal.record_trade(sample_trade)

        # Update with exit
        updated = journal.update_trade(
            trade_id=sample_trade.trade_id,
            exit_price=455.00,
            exit_time=datetime.now(),
            exit_order_id="order_456"
        )

        assert updated.exit_price == 455.00
        assert updated.realized_pnl == 500.00  # (455-450) * 100

    def test_get_open_trades(self, journal, sample_trade):
        """Test getting open trades."""
        journal.record_trade(sample_trade)

        open_trades = journal.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0].trade_id == sample_trade.trade_id

    def test_get_trades_with_filter(self, journal, sample_trade):
        """Test filtering trades by symbol."""
        journal.record_trade(sample_trade)

        # Filter by symbol
        trades = journal.get_trades(symbol="SPY")
        assert len(trades) == 1

        trades = journal.get_trades(symbol="QQQ")
        assert len(trades) == 0

    def test_strategy_performance_tracking(self, journal):
        """Test that strategy performance is tracked."""
        from contracts.journal import TradeRecord

        # Record multiple trades for a strategy
        for i, pnl_mult in enumerate([1, -1, 1, 1]):
            trade = TradeRecord(
                trade_id=str(uuid.uuid4()),
                symbol="SPY",
                side="buy",
                quantity=100,
                entry_price=450.00,
                entry_time=datetime.now(),
                entry_order_id=f"entry_{i}",
                strategy_id="test_strategy"
            )
            journal.record_trade(trade)
            journal.update_trade(
                trade_id=trade.trade_id,
                exit_price=450.00 + (pnl_mult * 2),
                exit_time=datetime.now(),
                exit_order_id=f"exit_{i}"
            )

        # Check performance
        perf = journal.get_strategy_performance("test_strategy")
        assert perf.trade_count == 4
        assert perf.win_count == 3
        assert perf.loss_count == 1
        assert perf.win_rate == 0.75

    def test_journal_entry_logging(self, journal):
        """Test logging journal entries."""
        from contracts.journal import JournalEntry

        entry = JournalEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            entry_type="system",
            category="startup",
            message="System started",
            data={"version": "1.0"}
        )

        entry_id = journal.log_entry(entry)
        assert entry_id == entry.entry_id

        # Retrieve entries
        entries = journal.get_entries(entry_type="system", limit=10)
        assert len(entries) >= 1

    def test_export_trades(self, journal, sample_trade):
        """Test exporting trades to CSV."""
        journal.record_trade(sample_trade)
        journal.update_trade(
            trade_id=sample_trade.trade_id,
            exit_price=455.00,
            exit_time=datetime.now(),
            exit_order_id="exit_123"
        )

        from datetime import date, timedelta

        csv_data = journal.export_trades(
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
            format="csv"
        )

        assert b"SPY" in csv_data
        assert b"trade_id" in csv_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
