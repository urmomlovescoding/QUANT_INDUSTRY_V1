"""
Trade Journal
=============
P1 Feature: Comprehensive trade logging and analytics.

Implements parity with quant-platform/execution/trade_journal.py

The Trade Journal:
1. Records all trade decisions (taken and rejected)
2. Tracks execution details
3. Provides analytics for learning
4. Supports replay for backtesting
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger("TRADE_JOURNAL")


class TradeAction(Enum):
    """Trade action types."""
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"


class TradeResult(Enum):
    """Trade result types."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


@dataclass
class JournalEntry:
    """
    A single trade journal entry.
    Records all relevant information about a trade.
    """
    entry_id: str
    timestamp: datetime

    # Trade identification
    symbol: str
    action: TradeAction
    direction: str  # 'LONG' or 'SHORT'

    # Decision info
    signal_confidence: float
    signal_source: str  # 'ml_model', 'ict_setup', 'manual', etc.
    decision: str  # 'taken', 'rejected', 'partial'
    rejection_reason: Optional[str] = None

    # Execution details
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0
    contracts: int = 0
    fill_price: Optional[float] = None
    slippage: float = 0.0

    # Timing
    decision_time_ms: float = 0.0
    execution_time_ms: float = 0.0

    # Result
    result: TradeResult = TradeResult.OPEN
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_time_seconds: float = 0.0

    # Context
    regime: str = "unknown"
    volatility: float = 0.0
    session: str = "unknown"

    # Features at time of trade (for ML learning)
    features: Dict[str, float] = field(default_factory=dict)

    # Notes
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["action"] = self.action.value
        d["result"] = self.result.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JournalEntry":
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["action"] = TradeAction(data["action"])
        data["result"] = TradeResult(data["result"])
        return cls(**data)


@dataclass
class DailySummary:
    """Daily trading summary."""
    date: date
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    commissions: float = 0.0

    best_trade: float = 0.0
    worst_trade: float = 0.0

    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
        }


class TradeJournal:
    """
    Comprehensive trade journal.

    Records all trading activity with detailed context
    for analysis and machine learning.

    Matches quant-platform behavior.
    """

    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or Path("journal")
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Entry storage
        self.entries: List[JournalEntry] = []
        self.max_entries: int = 10000

        # Daily summaries
        self.daily_summaries: Dict[str, DailySummary] = {}

        # Current session
        self.session_start: Optional[datetime] = None
        self.session_entries: List[JournalEntry] = []

        # Load persisted data
        self._load_entries()

        logger.info(f"TradeJournal initialized with {len(self.entries)} entries")

    def _load_entries(self) -> None:
        """Load persisted journal entries."""
        entries_file = self.state_dir / "entries.json"
        try:
            if entries_file.exists():
                with open(entries_file) as f:
                    data = json.load(f)
                self.entries = [
                    JournalEntry.from_dict(e) for e in data.get("entries", [])
                ]
        except Exception as e:
            logger.error(f"Error loading journal: {e}")

    def _save_entries(self) -> None:
        """Save journal entries to disk."""
        entries_file = self.state_dir / "entries.json"
        try:
            # Keep most recent entries
            entries_to_save = self.entries[-self.max_entries:]
            data = {
                "entries": [e.to_dict() for e in entries_to_save],
                "updated": datetime.now().isoformat(),
            }
            with open(entries_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving journal: {e}")

    def start_session(self) -> None:
        """Start a new trading session."""
        self.session_start = datetime.now()
        self.session_entries = []
        logger.info(f"Trading session started at {self.session_start}")

    def end_session(self) -> DailySummary:
        """End current trading session and generate summary."""
        if not self.session_start:
            return self._create_empty_summary()

        summary = self._calculate_daily_summary(
            self.session_entries,
            self.session_start.date(),
        )

        self.daily_summaries[self.session_start.date().isoformat()] = summary
        self._save_daily_summary(summary)

        logger.info(
            f"Session ended: {summary.total_trades} trades, "
            f"PnL=${summary.net_pnl:.2f}, WR={summary.win_rate:.1%}"
        )

        self.session_start = None
        self.session_entries = []

        return summary

    def record_decision(
        self,
        symbol: str,
        action: TradeAction,
        direction: str,
        signal_confidence: float,
        signal_source: str,
        decision: str,
        rejection_reason: Optional[str] = None,
        **kwargs,
    ) -> JournalEntry:
        """
        Record a trade decision (taken or rejected).

        Args:
            symbol: Trading symbol
            action: Trade action type
            direction: 'LONG' or 'SHORT'
            signal_confidence: Signal confidence (0-1)
            signal_source: Source of the signal
            decision: 'taken', 'rejected', or 'partial'
            rejection_reason: Reason if rejected
            **kwargs: Additional entry fields

        Returns:
            Created journal entry
        """
        entry_id = f"j_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        entry = JournalEntry(
            entry_id=entry_id,
            timestamp=datetime.now(),
            symbol=symbol,
            action=action,
            direction=direction,
            signal_confidence=signal_confidence,
            signal_source=signal_source,
            decision=decision,
            rejection_reason=rejection_reason,
            **kwargs,
        )

        self.entries.append(entry)
        if self.session_start:
            self.session_entries.append(entry)

        logger.debug(f"Recorded decision: {entry_id} {symbol} {action.value} {decision}")

        return entry

    def record_execution(
        self,
        entry_id: str,
        fill_price: float,
        contracts: int,
        execution_time_ms: float,
    ) -> Optional[JournalEntry]:
        """
        Record trade execution details.

        Args:
            entry_id: Entry to update
            fill_price: Actual fill price
            contracts: Contracts filled
            execution_time_ms: Execution latency

        Returns:
            Updated entry or None
        """
        entry = self._find_entry(entry_id)
        if not entry:
            logger.warning(f"Entry not found: {entry_id}")
            return None

        entry.fill_price = fill_price
        entry.contracts = contracts
        entry.execution_time_ms = execution_time_ms

        # Calculate slippage
        if entry.entry_price > 0:
            entry.slippage = abs(fill_price - entry.entry_price)

        return entry

    def record_exit(
        self,
        entry_id: str,
        exit_price: float,
        pnl: float,
        result: TradeResult,
    ) -> Optional[JournalEntry]:
        """
        Record trade exit.

        Args:
            entry_id: Entry to update
            exit_price: Exit price
            pnl: Realized P&L
            result: Trade result

        Returns:
            Updated entry or None
        """
        entry = self._find_entry(entry_id)
        if not entry:
            logger.warning(f"Entry not found: {entry_id}")
            return None

        entry.exit_price = exit_price
        entry.pnl = pnl
        entry.result = result

        # Calculate holding time
        entry.holding_time_seconds = (datetime.now() - entry.timestamp).total_seconds()

        # Calculate P&L percentage
        if entry.entry_price > 0 and entry.contracts > 0:
            entry.pnl_pct = pnl / (entry.entry_price * entry.contracts) * 100

        self._save_entries()

        logger.info(
            f"Trade exit: {entry_id} {entry.symbol} "
            f"Result={result.value} PnL=${pnl:.2f}"
        )

        return entry

    def _find_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """Find entry by ID."""
        for entry in reversed(self.entries):
            if entry.entry_id == entry_id:
                return entry
        return None

    def _calculate_daily_summary(
        self,
        entries: List[JournalEntry],
        summary_date: date,
    ) -> DailySummary:
        """Calculate daily summary from entries."""
        summary = DailySummary(date=summary_date)

        # Filter to executed trades with results
        trades = [
            e for e in entries
            if e.decision == "taken" and e.result != TradeResult.OPEN
        ]

        if not trades:
            return summary

        summary.total_trades = len(trades)

        wins = [t for t in trades if t.result == TradeResult.WIN]
        losses = [t for t in trades if t.result == TradeResult.LOSS]
        breakevens = [t for t in trades if t.result == TradeResult.BREAKEVEN]

        summary.winning_trades = len(wins)
        summary.losing_trades = len(losses)
        summary.breakeven_trades = len(breakevens)

        # P&L calculations
        summary.gross_pnl = sum(t.pnl for t in trades)
        summary.net_pnl = summary.gross_pnl - summary.commissions

        if trades:
            summary.best_trade = max(t.pnl for t in trades)
            summary.worst_trade = min(t.pnl for t in trades)

        # Win rate
        if summary.total_trades > 0:
            summary.win_rate = summary.winning_trades / summary.total_trades

        # Average win/loss
        if wins:
            summary.avg_win = sum(t.pnl for t in wins) / len(wins)
        if losses:
            summary.avg_loss = sum(t.pnl for t in losses) / len(losses)

        # Profit factor
        total_wins = sum(t.pnl for t in wins)
        total_losses = abs(sum(t.pnl for t in losses))
        if total_losses > 0:
            summary.profit_factor = total_wins / total_losses

        return summary

    def _create_empty_summary(self) -> DailySummary:
        """Create empty summary for current date."""
        return DailySummary(date=date.today())

    def _save_daily_summary(self, summary: DailySummary) -> None:
        """Save daily summary to file."""
        summary_file = self.state_dir / f"summary_{summary.date.isoformat()}.json"
        try:
            with open(summary_file, "w") as f:
                json.dump(summary.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving summary: {e}")

    def calculate_performance_metrics(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.
        Matches quant-platform analytics patterns.
        """
        import math
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=period_days)
        recent_entries = [
            e for e in self.entries
            if e.timestamp >= cutoff and e.decision == "taken" and e.result != TradeResult.OPEN
        ]

        if not recent_entries:
            return {
                "period_days": period_days,
                "total_trades": 0,
                "error": "No completed trades in period"
            }

        # Basic stats
        pnls = [e.pnl for e in recent_entries]
        total_pnl = sum(pnls)
        num_trades = len(pnls)

        # Win/loss breakdown
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        win_rate = len(wins) / num_trades if num_trades > 0 else 0

        # Average trade metrics
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Expectancy (expected value per trade)
        expectancy = total_pnl / num_trades if num_trades > 0 else 0

        # Sharpe Ratio (annualized, assuming daily data)
        if len(pnls) >= 2:
            mean_return = sum(pnls) / len(pnls)
            variance = sum((p - mean_return) ** 2 for p in pnls) / (len(pnls) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 0.001
            sharpe_ratio = (mean_return / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        else:
            sharpe_ratio = 0

        # Sortino Ratio (only considers downside deviation)
        downside_returns = [p for p in pnls if p < 0]
        if len(downside_returns) >= 2:
            mean_return = sum(pnls) / len(pnls)
            downside_variance = sum(p ** 2 for p in downside_returns) / len(downside_returns)
            downside_dev = math.sqrt(downside_variance) if downside_variance > 0 else 0.001
            sortino_ratio = (mean_return / downside_dev) * math.sqrt(252) if downside_dev > 0 else 0
        else:
            sortino_ratio = 0

        # Max Drawdown (cumulative)
        cumulative = 0
        peak = 0
        max_drawdown = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        max_drawdown_pct = (max_drawdown / peak * 100) if peak > 0 else 0

        # Recovery factor (total profit / max drawdown)
        recovery_factor = total_pnl / max_drawdown if max_drawdown > 0 else float('inf')

        # Consecutive wins/losses
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        for pnl in pnls:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        return {
            "period_days": period_days,
            "total_trades": num_trades,
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate * 100, 1),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "N/A",
            "expectancy": round(expectancy, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 1),
            "recovery_factor": round(recovery_factor, 2) if recovery_factor != float('inf') else "N/A",
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
        }

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent journal entries."""
        return [e.to_dict() for e in self.entries[-limit:]]

    def get_entries_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get entries for a specific symbol."""
        filtered = [e for e in self.entries if e.symbol == symbol]
        return [e.to_dict() for e in filtered[-limit:]]

    def get_entries_by_date(self, target_date: date) -> List[Dict[str, Any]]:
        """Get entries for a specific date."""
        filtered = [e for e in self.entries if e.timestamp.date() == target_date]
        return [e.to_dict() for e in filtered]

    def get_rejection_analysis(self, limit: int = 100) -> Dict[str, Any]:
        """Analyze rejected trades."""
        rejected = [e for e in self.entries[-limit:] if e.decision == "rejected"]

        reasons = {}
        for entry in rejected:
            reason = entry.rejection_reason or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1

        return {
            "total_rejected": len(rejected),
            "rejection_reasons": reasons,
            "most_common_reason": max(reasons, key=reasons.get) if reasons else None,
        }

    def get_performance_by_session(self) -> Dict[str, Any]:
        """Analyze performance by trading session."""
        sessions = {}

        for entry in self.entries:
            if entry.result == TradeResult.OPEN:
                continue

            session = entry.session
            if session not in sessions:
                sessions[session] = {
                    "trades": 0,
                    "wins": 0,
                    "pnl": 0.0,
                }

            sessions[session]["trades"] += 1
            if entry.result == TradeResult.WIN:
                sessions[session]["wins"] += 1
            sessions[session]["pnl"] += entry.pnl

        # Calculate win rates
        for session in sessions:
            trades = sessions[session]["trades"]
            if trades > 0:
                sessions[session]["win_rate"] = sessions[session]["wins"] / trades
            else:
                sessions[session]["win_rate"] = 0.0

        return sessions

    def get_stats(self) -> Dict[str, Any]:
        """Get overall journal statistics."""
        total = len(self.entries)
        taken = len([e for e in self.entries if e.decision == "taken"])
        rejected = len([e for e in self.entries if e.decision == "rejected"])

        completed = [
            e for e in self.entries
            if e.decision == "taken" and e.result != TradeResult.OPEN
        ]

        total_pnl = sum(e.pnl for e in completed)
        wins = len([e for e in completed if e.result == TradeResult.WIN])

        return {
            "total_entries": total,
            "trades_taken": taken,
            "trades_rejected": rejected,
            "completed_trades": len(completed),
            "total_pnl": total_pnl,
            "win_rate": wins / len(completed) if completed else 0,
            "avg_pnl": total_pnl / len(completed) if completed else 0,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get journal status."""
        return {
            "entry_count": len(self.entries),
            "session_active": self.session_start is not None,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "session_trades": len(self.session_entries),
            "stats": self.get_stats(),
        }


# Singleton instance
_trade_journal: Optional[TradeJournal] = None


def get_trade_journal() -> TradeJournal:
    """Get or create trade journal singleton."""
    global _trade_journal
    if _trade_journal is None:
        _trade_journal = TradeJournal()
    return _trade_journal
