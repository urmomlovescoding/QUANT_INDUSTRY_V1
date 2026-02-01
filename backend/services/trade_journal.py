"""
Trade Journal Service
=====================
Implementation of the JournalContract for trade journaling and attribution.

Every trade MUST be journaled for:
1. Strategy attribution
2. Performance analysis
3. Feedback loop learning
4. Audit trail
"""

import csv
import io
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from contracts.journal import (
    JournalContract,
    TradeRecord,
    JournalEntry,
    StrategyPerformance,
    TradeOutcome
)

logger = logging.getLogger(__name__)


class TradeJournal(JournalContract):
    """
    SQLite-backed trade journal implementation.

    Features:
    - Persistent trade storage
    - Strategy performance tracking
    - P&L calculations
    - Export capabilities
    - Feedback loop integration
    """

    def __init__(self, db_path: str = "trade_journal.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

        # Callbacks for trade events
        self._trade_callbacks: List[callable] = []

        # Track connection for cleanup
        self._conn: Optional[sqlite3.Connection] = None

        logger.info(f"TradeJournal initialized: {db_path}")

    def close(self) -> None:
        """Close the database connection for cleanup."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    entry_order_id TEXT,
                    exit_price REAL,
                    exit_time TEXT,
                    exit_order_id TEXT,
                    realized_pnl REAL DEFAULT 0,
                    realized_pnl_pct REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    slippage REAL DEFAULT 0,
                    commission REAL DEFAULT 0,
                    strategy_id TEXT,
                    signal_id TEXT,
                    signal_confidence REAL DEFAULT 0,
                    initial_stop_loss REAL,
                    initial_take_profit REAL,
                    max_adverse_excursion REAL DEFAULT 0,
                    max_favorable_excursion REAL DEFAULT 0,
                    tags TEXT,
                    notes TEXT,
                    outcome TEXT DEFAULT 'open',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS journal_entries (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS strategy_performance (
                    strategy_id TEXT PRIMARY KEY,
                    trade_count INTEGER DEFAULT 0,
                    win_count INTEGER DEFAULT 0,
                    loss_count INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    avg_pnl REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0,
                    avg_win REAL DEFAULT 0,
                    avg_loss REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    last_updated TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
                CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
                CREATE INDEX IF NOT EXISTS idx_trades_outcome ON trades(outcome);
                CREATE INDEX IF NOT EXISTS idx_entries_type ON journal_entries(entry_type);
                CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON journal_entries(timestamp);
            """)

    def register_trade_callback(self, callback: callable) -> None:
        """Register callback for trade events."""
        self._trade_callbacks.append(callback)

    def _notify_trade_event(self, event_type: str, trade: TradeRecord) -> None:
        """Notify callbacks of trade event."""
        for callback in self._trade_callbacks:
            try:
                callback(event_type, trade)
            except Exception as e:
                logger.error(f"Trade callback error: {e}")

    def record_trade(self, trade: TradeRecord) -> str:
        """
        Record a new trade entry.

        Returns trade_id.
        """
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO trades (
                    trade_id, symbol, side, quantity, entry_price, entry_time,
                    entry_order_id, strategy_id, signal_id, signal_confidence,
                    initial_stop_loss, initial_take_profit, tags, notes, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id,
                trade.symbol,
                trade.side,
                trade.quantity,
                trade.entry_price,
                trade.entry_time.isoformat(),
                trade.entry_order_id,
                trade.strategy_id,
                trade.signal_id,
                trade.signal_confidence,
                trade.initial_stop_loss,
                trade.initial_take_profit,
                json.dumps(trade.tags),
                trade.notes,
                trade.outcome.value
            ))

        # Log journal entry
        self.log_entry(JournalEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            entry_type="trade",
            category="entry",
            message=f"Opened {trade.side} {trade.quantity} {trade.symbol} @ {trade.entry_price}",
            data={"trade_id": trade.trade_id, "strategy_id": trade.strategy_id}
        ))

        self._notify_trade_event("opened", trade)
        logger.info(f"Trade recorded: {trade.trade_id} {trade.side} {trade.symbol}")

        return trade.trade_id

    def update_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: datetime,
        exit_order_id: str
    ) -> TradeRecord:
        """
        Update trade with exit info.

        Calculates final P&L and updates strategy performance.
        """
        # Get existing trade
        trade = self.get_trade(trade_id)
        if not trade:
            raise ValueError(f"Trade not found: {trade_id}")

        # Calculate P&L
        if trade.side.lower() == "buy":
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            pnl = (trade.entry_price - exit_price) * trade.quantity

        pnl_pct = (pnl / (trade.entry_price * trade.quantity)) * 100

        # Determine outcome
        if pnl > 0:
            outcome = TradeOutcome.WIN
        elif pnl < 0:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN

        # Update trade
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE trades SET
                    exit_price = ?,
                    exit_time = ?,
                    exit_order_id = ?,
                    realized_pnl = ?,
                    realized_pnl_pct = ?,
                    outcome = ?,
                    updated_at = ?
                WHERE trade_id = ?
            """, (
                exit_price,
                exit_time.isoformat(),
                exit_order_id,
                pnl,
                pnl_pct,
                outcome.value,
                datetime.now().isoformat(),
                trade_id
            ))

        # Update trade object
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.exit_order_id = exit_order_id
        trade.realized_pnl = pnl
        trade.realized_pnl_pct = pnl_pct

        # Update strategy performance
        if trade.strategy_id:
            self._update_strategy_performance(trade.strategy_id)

        # Log journal entry
        self.log_entry(JournalEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            entry_type="trade",
            category="exit",
            message=f"Closed {trade.side} {trade.quantity} {trade.symbol} @ {exit_price} PnL: ${pnl:.2f}",
            data={"trade_id": trade_id, "pnl": pnl, "outcome": outcome.value}
        ))

        self._notify_trade_event("closed", trade)
        logger.info(f"Trade closed: {trade_id} PnL=${pnl:.2f} ({outcome.value})")

        # Trigger feedback loop
        self._trigger_feedback_loop(trade)

        return trade

    def _trigger_feedback_loop(self, trade: TradeRecord) -> None:
        """Trigger feedback loop with trade result."""
        try:
            from brain.feedback_loop import get_feedback_loop, TradeResult, TradeOutcome as FBOutcome

            # Map outcome
            if trade.outcome == TradeOutcome.WIN:
                fb_outcome = FBOutcome.WIN
            elif trade.outcome == TradeOutcome.LOSS:
                fb_outcome = FBOutcome.LOSS
            else:
                fb_outcome = FBOutcome.BREAKEVEN

            result = TradeResult(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                direction="LONG" if trade.side.lower() == "buy" else "SHORT",
                entry_price=trade.entry_price,
                exit_price=trade.exit_price or trade.entry_price,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time or datetime.now(),
                quantity=trade.quantity,
                pnl=trade.realized_pnl,
                pnl_pct=trade.realized_pnl_pct,
                outcome=fb_outcome,
                strategy=trade.strategy_id or "unknown",
                signal_confidence=trade.signal_confidence,
                regime_at_entry="unknown"
            )

            loop = get_feedback_loop()
            loop.record_trade(result)

        except Exception as e:
            logger.warning(f"Feedback loop trigger failed: {e}")

    def _update_strategy_performance(self, strategy_id: str) -> None:
        """Update strategy performance metrics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all closed trades for strategy
            trades = conn.execute("""
                SELECT realized_pnl, outcome FROM trades
                WHERE strategy_id = ? AND outcome != 'open'
            """, (strategy_id,)).fetchall()

            if not trades:
                return

            wins = [t['realized_pnl'] for t in trades if t['outcome'] == 'win']
            losses = [abs(t['realized_pnl']) for t in trades if t['outcome'] == 'loss']

            total_pnl = sum(t['realized_pnl'] for t in trades)
            trade_count = len(trades)
            win_count = len(wins)
            loss_count = len(losses)

            win_rate = win_count / trade_count if trade_count > 0 else 0
            avg_pnl = total_pnl / trade_count if trade_count > 0 else 0
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            profit_factor = sum(wins) / sum(losses) if losses else 0

            conn.execute("""
                INSERT OR REPLACE INTO strategy_performance
                (strategy_id, trade_count, win_count, loss_count, total_pnl,
                 avg_pnl, win_rate, profit_factor, avg_win, avg_loss, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id, trade_count, win_count, loss_count, total_pnl,
                avg_pnl, win_rate, profit_factor, avg_win, avg_loss,
                datetime.now().isoformat()
            ))

    def get_trade(self, trade_id: str) -> Optional[TradeRecord]:
        """Get trade by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ?", (trade_id,)
            ).fetchone()

            if not row:
                return None

            return self._row_to_trade(dict(row))

    def _row_to_trade(self, row: dict) -> TradeRecord:
        """Convert database row to TradeRecord."""
        return TradeRecord(
            trade_id=row['trade_id'],
            symbol=row['symbol'],
            side=row['side'],
            quantity=row['quantity'],
            entry_price=row['entry_price'],
            entry_time=datetime.fromisoformat(row['entry_time']),
            entry_order_id=row['entry_order_id'],
            exit_price=row['exit_price'],
            exit_time=datetime.fromisoformat(row['exit_time']) if row['exit_time'] else None,
            exit_order_id=row['exit_order_id'],
            realized_pnl=row['realized_pnl'] or 0,
            realized_pnl_pct=row['realized_pnl_pct'] or 0,
            unrealized_pnl=row['unrealized_pnl'] or 0,
            slippage=row['slippage'] or 0,
            commission=row['commission'] or 0,
            strategy_id=row['strategy_id'],
            signal_id=row['signal_id'],
            signal_confidence=row['signal_confidence'] or 0,
            initial_stop_loss=row['initial_stop_loss'],
            initial_take_profit=row['initial_take_profit'],
            max_adverse_excursion=row['max_adverse_excursion'] or 0,
            max_favorable_excursion=row['max_favorable_excursion'] or 0,
            tags=json.loads(row['tags']) if row['tags'] else [],
            notes=row['notes'] or ""
        )

    def get_open_trades(self) -> List[TradeRecord]:
        """Get all open trades."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades WHERE outcome = 'open' ORDER BY entry_time DESC"
            ).fetchall()

            return [self._row_to_trade(dict(row)) for row in rows]

    def get_trades(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100
    ) -> List[TradeRecord]:
        """Query trades with filters."""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if start_date:
            query += " AND date(entry_time) >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND date(entry_time) <= ?"
            params.append(end_date.isoformat())

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())

        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)

        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

            return [self._row_to_trade(dict(row)) for row in rows]

    def get_strategy_performance(
        self,
        strategy_id: str,
        start_date: Optional[date] = None
    ) -> StrategyPerformance:
        """Get performance metrics for a strategy."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM strategy_performance WHERE strategy_id = ?",
                (strategy_id,)
            ).fetchone()

            if not row:
                return StrategyPerformance(strategy_id=strategy_id)

            return StrategyPerformance(
                strategy_id=strategy_id,
                trade_count=row['trade_count'],
                win_count=row['win_count'],
                loss_count=row['loss_count'],
                total_pnl=row['total_pnl'],
                avg_pnl=row['avg_pnl'],
                win_rate=row['win_rate'],
                profit_factor=row['profit_factor'],
                avg_win=row['avg_win'],
                avg_loss=row['avg_loss'],
                max_drawdown=row['max_drawdown'],
                sharpe_ratio=row['sharpe_ratio'],
                last_updated=datetime.fromisoformat(row['last_updated']) if row['last_updated'] else datetime.now()
            )

    def get_all_strategy_performance(self) -> Dict[str, StrategyPerformance]:
        """Get performance for all strategies."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM strategy_performance").fetchall()

            return {
                row['strategy_id']: StrategyPerformance(
                    strategy_id=row['strategy_id'],
                    trade_count=row['trade_count'],
                    win_count=row['win_count'],
                    loss_count=row['loss_count'],
                    total_pnl=row['total_pnl'],
                    avg_pnl=row['avg_pnl'],
                    win_rate=row['win_rate'],
                    profit_factor=row['profit_factor'],
                    avg_win=row['avg_win'],
                    avg_loss=row['avg_loss'],
                    max_drawdown=row['max_drawdown'],
                    sharpe_ratio=row['sharpe_ratio']
                )
                for row in rows
            }

    def log_entry(self, entry: JournalEntry) -> str:
        """Log a general journal entry."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO journal_entries
                (entry_id, timestamp, entry_type, category, message, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.timestamp.isoformat(),
                entry.entry_type,
                entry.category,
                entry.message,
                json.dumps(entry.data)
            ))

        return entry.entry_id

    def get_entries(
        self,
        entry_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[JournalEntry]:
        """Query journal entries."""
        query = "SELECT * FROM journal_entries WHERE 1=1"
        params = []

        if entry_type:
            query += " AND entry_type = ?"
            params.append(entry_type)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

            return [
                JournalEntry(
                    entry_id=row['entry_id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    entry_type=row['entry_type'],
                    category=row['category'],
                    message=row['message'],
                    data=json.loads(row['data_json']) if row['data_json'] else {}
                )
                for row in rows
            ]

    def export_trades(
        self,
        start_date: date,
        end_date: date,
        format: str = "csv"
    ) -> bytes:
        """Export trades for analysis."""
        trades = self.get_trades(start_date=start_date, end_date=end_date, limit=10000)

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                "trade_id", "symbol", "side", "quantity",
                "entry_price", "entry_time", "exit_price", "exit_time",
                "realized_pnl", "realized_pnl_pct", "outcome",
                "strategy_id", "signal_confidence"
            ])

            # Data
            for trade in trades:
                writer.writerow([
                    trade.trade_id, trade.symbol, trade.side, trade.quantity,
                    trade.entry_price, trade.entry_time.isoformat(),
                    trade.exit_price, trade.exit_time.isoformat() if trade.exit_time else "",
                    trade.realized_pnl, trade.realized_pnl_pct, trade.outcome.value,
                    trade.strategy_id, trade.signal_confidence
                ])

            return output.getvalue().encode('utf-8')

        elif format == "json":
            return json.dumps([trade.to_dict() for trade in trades], indent=2).encode('utf-8')

        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get journal summary."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Trade stats
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(realized_pnl) as total_pnl,
                    AVG(realized_pnl) as avg_pnl
                FROM trades
                WHERE entry_time > ?
            """, (cutoff,)).fetchone()

            # Open trades
            open_count = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE outcome = 'open'"
            ).fetchone()[0]

            return {
                "period_days": days,
                "total_trades": stats['total_trades'] or 0,
                "wins": stats['wins'] or 0,
                "losses": stats['losses'] or 0,
                "win_rate": (stats['wins'] / stats['total_trades']) if stats['total_trades'] else 0,
                "total_pnl": stats['total_pnl'] or 0,
                "avg_pnl": stats['avg_pnl'] or 0,
                "open_positions": open_count,
                "timestamp": datetime.now().isoformat()
            }


# Singleton instance
_trade_journal: Optional[TradeJournal] = None


def get_trade_journal() -> TradeJournal:
    """Get global trade journal instance."""
    global _trade_journal
    if _trade_journal is None:
        _trade_journal = TradeJournal()
    return _trade_journal


__all__ = [
    'TradeJournal',
    'get_trade_journal',
]
