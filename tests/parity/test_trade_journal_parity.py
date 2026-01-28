"""
Trade Journal Parity Tests
==========================
Verifies Trade Journal matches quant-platform behavior.
"""
import pytest
from datetime import datetime, date
from pathlib import Path
import tempfile


class TestTradeActionParity:
    """Test trade action enum."""

    def test_action_values(self):
        """Verify all action values exist."""
        from backend.execution import TradeAction

        assert TradeAction.BUY.value == "buy"
        assert TradeAction.SELL.value == "sell"
        assert TradeAction.CLOSE.value == "close"
        assert TradeAction.SCALE_IN.value == "scale_in"
        assert TradeAction.SCALE_OUT.value == "scale_out"


class TestTradeResultParity:
    """Test trade result enum."""

    def test_result_values(self):
        """Verify all result values exist."""
        from backend.execution import TradeResult

        assert TradeResult.WIN.value == "win"
        assert TradeResult.LOSS.value == "loss"
        assert TradeResult.BREAKEVEN.value == "breakeven"
        assert TradeResult.OPEN.value == "open"


class TestJournalEntryParity:
    """Test journal entry structure."""

    def test_entry_structure(self):
        """Verify entry has required fields."""
        from backend.execution import JournalEntry, TradeAction, TradeResult

        entry = JournalEntry(
            entry_id="test_001",
            timestamp=datetime.now(),
            symbol="ES",
            action=TradeAction.BUY,
            direction="LONG",
            signal_confidence=0.70,
            signal_source="test",
            decision="taken",
        )

        assert hasattr(entry, "entry_id")
        assert hasattr(entry, "timestamp")
        assert hasattr(entry, "symbol")
        assert hasattr(entry, "action")
        assert hasattr(entry, "signal_confidence")
        assert hasattr(entry, "entry_price")
        assert hasattr(entry, "exit_price")
        assert hasattr(entry, "pnl")
        assert hasattr(entry, "result")
        assert hasattr(entry, "features")

    def test_entry_serialization(self):
        """Verify entry serialization."""
        from backend.execution import JournalEntry, TradeAction, TradeResult

        entry = JournalEntry(
            entry_id="test_002",
            timestamp=datetime.now(),
            symbol="NQ",
            action=TradeAction.SELL,
            direction="SHORT",
            signal_confidence=0.65,
            signal_source="ml_model",
            decision="taken",
            pnl=500.0,
            result=TradeResult.WIN,
        )

        data = entry.to_dict()
        restored = JournalEntry.from_dict(data)

        assert restored.entry_id == entry.entry_id
        assert restored.symbol == entry.symbol
        assert restored.pnl == entry.pnl
        assert restored.result == entry.result


class TestDailySummaryParity:
    """Test daily summary structure."""

    def test_summary_structure(self):
        """Verify summary has required fields."""
        from backend.execution.trade_journal import DailySummary

        summary = DailySummary(date=date.today())

        assert hasattr(summary, "date")
        assert hasattr(summary, "total_trades")
        assert hasattr(summary, "winning_trades")
        assert hasattr(summary, "losing_trades")
        assert hasattr(summary, "gross_pnl")
        assert hasattr(summary, "net_pnl")
        assert hasattr(summary, "win_rate")
        assert hasattr(summary, "profit_factor")


class TestTradeJournalParity:
    """Test Trade Journal implementation."""

    def test_journal_initialization(self):
        """Verify journal initializes correctly."""
        from backend.execution import TradeJournal

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            assert journal.entries == []
            assert journal.session_start is None

    def test_record_decision_taken(self):
        """Verify recording taken decision."""
        from backend.execution import TradeJournal, TradeAction

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            entry = journal.record_decision(
                symbol="ES",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.70,
                signal_source="test",
                decision="taken",
            )

            assert entry.entry_id.startswith("j_")
            assert entry.decision == "taken"
            assert len(journal.entries) == 1

    def test_record_decision_rejected(self):
        """Verify recording rejected decision."""
        from backend.execution import TradeJournal, TradeAction

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            entry = journal.record_decision(
                symbol="ES",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.40,
                signal_source="test",
                decision="rejected",
                rejection_reason="Low confidence",
            )

            assert entry.decision == "rejected"
            assert entry.rejection_reason == "Low confidence"

    def test_record_execution(self):
        """Verify recording execution details."""
        from backend.execution import TradeJournal, TradeAction

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            entry = journal.record_decision(
                symbol="ES",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.70,
                signal_source="test",
                decision="taken",
                entry_price=5000.0,
            )

            updated = journal.record_execution(
                entry_id=entry.entry_id,
                fill_price=5000.25,
                contracts=2,
                execution_time_ms=15.0,
            )

            assert updated.fill_price == 5000.25
            assert updated.contracts == 2
            assert updated.slippage == 0.25

    def test_record_exit(self):
        """Verify recording trade exit."""
        from backend.execution import TradeJournal, TradeAction, TradeResult

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            entry = journal.record_decision(
                symbol="ES",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.70,
                signal_source="test",
                decision="taken",
                entry_price=5000.0,
            )

            updated = journal.record_exit(
                entry_id=entry.entry_id,
                exit_price=5010.0,
                pnl=500.0,
                result=TradeResult.WIN,
            )

            assert updated.exit_price == 5010.0
            assert updated.pnl == 500.0
            assert updated.result == TradeResult.WIN

    def test_session_management(self):
        """Verify session start/end."""
        from backend.execution import TradeJournal, TradeAction, TradeResult

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            journal.start_session()
            assert journal.session_start is not None

            # Record some trades
            entry = journal.record_decision(
                symbol="ES",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.70,
                signal_source="test",
                decision="taken",
            )
            journal.record_exit(entry.entry_id, 5010.0, 500.0, TradeResult.WIN)

            summary = journal.end_session()

            assert summary.total_trades == 1
            assert summary.winning_trades == 1
            assert summary.gross_pnl == 500.0
            assert journal.session_start is None

    def test_get_recent_entries(self):
        """Verify recent entries retrieval."""
        from backend.execution import TradeJournal, TradeAction

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            # Record multiple entries
            for i in range(5):
                journal.record_decision(
                    symbol=f"SYM{i}",
                    action=TradeAction.BUY,
                    direction="LONG",
                    signal_confidence=0.70,
                    signal_source="test",
                    decision="taken",
                )

            recent = journal.get_recent_entries(limit=3)
            assert len(recent) == 3

    def test_rejection_analysis(self):
        """Verify rejection analysis."""
        from backend.execution import TradeJournal, TradeAction

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            # Record rejections
            for reason in ["Low confidence", "Low R:R", "Low confidence"]:
                journal.record_decision(
                    symbol="ES",
                    action=TradeAction.BUY,
                    direction="LONG",
                    signal_confidence=0.40,
                    signal_source="test",
                    decision="rejected",
                    rejection_reason=reason,
                )

            analysis = journal.get_rejection_analysis()

            assert analysis["total_rejected"] == 3
            assert analysis["most_common_reason"] == "Low confidence"
            assert analysis["rejection_reasons"]["Low confidence"] == 2

    def test_stats(self):
        """Verify stats calculation."""
        from backend.execution import TradeJournal, TradeAction, TradeResult

        with tempfile.TemporaryDirectory() as tmpdir:
            journal = TradeJournal(state_dir=Path(tmpdir))

            # Record trades
            entry1 = journal.record_decision(
                symbol="ES",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.70,
                signal_source="test",
                decision="taken",
            )
            journal.record_exit(entry1.entry_id, 5010.0, 500.0, TradeResult.WIN)

            entry2 = journal.record_decision(
                symbol="ES",
                action=TradeAction.SELL,
                direction="SHORT",
                signal_confidence=0.65,
                signal_source="test",
                decision="taken",
            )
            journal.record_exit(entry2.entry_id, 5005.0, -200.0, TradeResult.LOSS)

            stats = journal.get_stats()

            assert stats["total_entries"] == 2
            assert stats["trades_taken"] == 2
            assert stats["completed_trades"] == 2
            assert stats["total_pnl"] == 300.0
            assert stats["win_rate"] == 0.5
