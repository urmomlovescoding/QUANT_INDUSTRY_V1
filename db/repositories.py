"""
QUANT_INDUSTRY_V1 Repository Pattern Implementation

Repositories provide a clean abstraction over database operations.
Each repository handles CRUD operations for a specific domain entity.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from abc import ABC, abstractmethod
import logging

from .dal import DatabaseManager, get_db
from .models import (
    Run, RunMode, RunStatus,
    MarketBar,
    Signal, SignalType, Direction,
    Order, OrderSide, OrderType, OrderStatus, TimeInForce,
    Trade,
    Position,
    Model, ModelType, ModelStatus,
    Strategy,
    RiskLimit,
    AuditEntry,
    ErrorEntry, Severity, Subsystem,
    HealthMetric,
    SelfGradeScore,
)

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    """Base repository with common functionality."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self._db = db

    @property
    def db(self) -> DatabaseManager:
        """Get database manager."""
        return self._db or get_db()


class RunRepository(BaseRepository):
    """Repository for run management."""

    def create(self, run: Run) -> int:
        """Create a new run."""
        return self.db.insert('runs', run.to_dict())

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """Get run by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        )
        return Run.from_row(row) if row else None

    def get_active(self) -> List[Run]:
        """Get all active (running) runs."""
        rows = self.db.fetch_all(
            "SELECT * FROM runs WHERE status = 'running' ORDER BY start_ts DESC"
        )
        return [Run.from_row(r) for r in rows]

    def update_status(self, run_id: str, status: RunStatus, end_ts: Optional[datetime] = None) -> int:
        """Update run status."""
        data = {'status': status.value}
        if end_ts:
            data['end_ts'] = end_ts.isoformat()
        return self.db.update('runs', data, 'run_id = ?', (run_id,))

    def complete(self, run_id: str) -> int:
        """Mark run as completed."""
        return self.update_status(run_id, RunStatus.COMPLETED, datetime.utcnow())

    def fail(self, run_id: str) -> int:
        """Mark run as failed."""
        return self.update_status(run_id, RunStatus.FAILED, datetime.utcnow())

    def get_recent(self, limit: int = 10) -> List[Run]:
        """Get recent runs."""
        rows = self.db.fetch_all(
            "SELECT * FROM runs ORDER BY start_ts DESC LIMIT ?",
            (limit,)
        )
        return [Run.from_row(r) for r in rows]


class MarketDataRepository(BaseRepository):
    """Repository for market data operations."""

    def insert_bar(self, bar: MarketBar) -> int:
        """Insert a market bar."""
        return self.db.insert('market_bars', bar.to_dict(), or_replace=True)

    def insert_bars(self, bars: List[MarketBar]) -> int:
        """Bulk insert market bars."""
        if not bars:
            return 0

        sql = """
            INSERT OR REPLACE INTO market_bars
            (symbol, timeframe, ts, open, high, low, close, volume, source, is_adjusted, vwap, trade_count, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            (b.symbol, b.timeframe, b.ts.isoformat(), b.open, b.high, b.low,
             b.close, b.volume, b.source, 1 if b.is_adjusted else 0,
             b.vwap, b.trade_count, b.quality_score)
            for b in bars
        ]
        return self.db.execute_many(sql, params)

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start_ts: datetime,
        end_ts: Optional[datetime] = None,
        source: Optional[str] = None
    ) -> List[MarketBar]:
        """Get market bars for a symbol."""
        sql = """
            SELECT * FROM market_bars
            WHERE symbol = ? AND timeframe = ? AND ts >= ?
        """
        params = [symbol, timeframe, start_ts.isoformat()]

        if end_ts:
            sql += " AND ts <= ?"
            params.append(end_ts.isoformat())

        if source:
            sql += " AND source = ?"
            params.append(source)

        sql += " ORDER BY ts ASC"

        rows = self.db.fetch_all(sql, tuple(params))
        return [MarketBar.from_row(r) for r in rows]

    def get_latest_bar(self, symbol: str, timeframe: str = '1d') -> Optional[MarketBar]:
        """Get the most recent bar for a symbol."""
        row = self.db.fetch_one(
            """
            SELECT * FROM market_bars
            WHERE symbol = ? AND timeframe = ?
            ORDER BY ts DESC LIMIT 1
            """,
            (symbol, timeframe)
        )
        return MarketBar.from_row(row) if row else None

    def get_symbols(self) -> List[str]:
        """Get all symbols in the database."""
        rows = self.db.fetch_all(
            "SELECT DISTINCT symbol FROM market_bars ORDER BY symbol"
        )
        return [r['symbol'] for r in rows]

    def get_data_freshness(self, symbol: str, timeframe: str = '1d') -> Optional[float]:
        """Get seconds since last data update."""
        bar = self.get_latest_bar(symbol, timeframe)
        if bar:
            delta = datetime.utcnow() - bar.ts
            return delta.total_seconds()
        return None

    def log_quality_event(
        self,
        symbol: str,
        ts: datetime,
        event_type: str,
        severity: str,
        description: str,
        run_id: Optional[str] = None
    ) -> int:
        """Log a data quality event."""
        return self.db.insert('data_quality_events', {
            'symbol': symbol,
            'ts': ts.isoformat(),
            'event_type': event_type,
            'severity': severity,
            'description': description,
            'run_id': run_id,
        })


class SignalRepository(BaseRepository):
    """Repository for trading signals."""

    def create(self, signal: Signal) -> int:
        """Create a new signal."""
        return self.db.insert('signals', signal.to_dict())

    def get_by_id(self, signal_id: int) -> Optional[Signal]:
        """Get signal by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM signals WHERE id = ?",
            (signal_id,)
        )
        return Signal.from_row(row) if row else None

    def get_recent(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Signal]:
        """Get recent signals."""
        sql = "SELECT * FROM signals WHERE 1=1"
        params = []

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)

        if since:
            sql += " AND ts >= ?"
            params.append(since.isoformat())

        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(sql, tuple(params))
        return [Signal.from_row(r) for r in rows]

    def get_by_model(
        self,
        model_id: str,
        limit: int = 100
    ) -> List[Signal]:
        """Get signals generated by a specific model."""
        rows = self.db.fetch_all(
            "SELECT * FROM signals WHERE model_id = ? ORDER BY ts DESC LIMIT ?",
            (model_id, limit)
        )
        return [Signal.from_row(r) for r in rows]

    def get_by_strategy(
        self,
        strategy_id: str,
        limit: int = 100
    ) -> List[Signal]:
        """Get signals for a specific strategy."""
        rows = self.db.fetch_all(
            "SELECT * FROM signals WHERE strategy_id = ? ORDER BY ts DESC LIMIT ?",
            (strategy_id, limit)
        )
        return [Signal.from_row(r) for r in rows]


class TradeRepository(BaseRepository):
    """Repository for trade operations."""

    def create_order(self, order: Order) -> int:
        """Create a new order."""
        return self.db.insert('orders', order.to_dict())

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        broker_order_id: Optional[str] = None
    ) -> int:
        """Update order status."""
        data = {'status': status.value}
        if status == OrderStatus.SUBMITTED:
            data['submitted_at'] = datetime.utcnow().isoformat()
        elif status == OrderStatus.FILLED:
            data['filled_at'] = datetime.utcnow().isoformat()
        elif status == OrderStatus.CANCELLED:
            data['cancelled_at'] = datetime.utcnow().isoformat()
        if broker_order_id:
            data['broker_order_id'] = broker_order_id
        return self.db.update('orders', data, 'order_id = ?', (order_id,))

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,)
        )
        return Order.from_row(row) if row else None

    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders."""
        rows = self.db.fetch_all(
            "SELECT * FROM orders WHERE status IN ('pending', 'submitted', 'accepted', 'partial')"
        )
        return [Order.from_row(r) for r in rows]

    def create_trade(self, trade: Trade) -> int:
        """Record a trade execution."""
        return self.db.insert('trades', trade.to_dict())

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM trades WHERE trade_id = ?",
            (trade_id,)
        )
        return Trade.from_row(row) if row else None

    def get_trades(
        self,
        symbol: Optional[str] = None,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Trade]:
        """Get trades with optional filters."""
        sql = "SELECT * FROM trades WHERE 1=1"
        params = []

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)
        if start_ts:
            sql += " AND executed_at >= ?"
            params.append(start_ts.isoformat())
        if end_ts:
            sql += " AND executed_at <= ?"
            params.append(end_ts.isoformat())

        sql += " ORDER BY executed_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(sql, tuple(params))
        return [Trade.from_row(r) for r in rows]

    def get_execution_stats(
        self,
        start_ts: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get execution quality statistics."""
        sql = """
            SELECT
                COUNT(*) as total_trades,
                AVG(slippage) as avg_slippage,
                MAX(slippage) as max_slippage,
                MIN(slippage) as min_slippage,
                SUM(commission) as total_commission
            FROM trades
        """
        if start_ts:
            sql += " WHERE executed_at >= ?"
            row = self.db.fetch_one(sql, (start_ts.isoformat(),))
        else:
            row = self.db.fetch_one(sql)

        return row or {}


class PositionRepository(BaseRepository):
    """Repository for position management."""

    def upsert(self, position: Position) -> int:
        """Insert or update a position."""
        return self.db.insert('positions', position.to_dict(), or_replace=True)

    def get_current(self, symbol: str, strategy_id: Optional[str] = None) -> Optional[Position]:
        """Get current position for a symbol."""
        sql = "SELECT * FROM positions WHERE symbol = ?"
        params = [symbol]

        if strategy_id:
            sql += " AND strategy_id = ?"
            params.append(strategy_id)

        sql += " ORDER BY ts DESC LIMIT 1"

        row = self.db.fetch_one(sql, tuple(params))
        return Position.from_row(row) if row else None

    def get_all_active(self, strategy_id: Optional[str] = None) -> List[Position]:
        """Get all positions with non-zero quantity."""
        sql = "SELECT * FROM v_active_positions"
        if strategy_id:
            sql = f"SELECT * FROM positions WHERE qty != 0 AND strategy_id = ?"
            rows = self.db.fetch_all(sql, (strategy_id,))
        else:
            rows = self.db.fetch_all(sql)
        return [Position.from_row(r) for r in rows]

    def close_position(self, symbol: str, realized_pnl: float, strategy_id: Optional[str] = None) -> int:
        """Close a position by setting quantity to 0."""
        data = {
            'qty': 0,
            'realized_pnl': realized_pnl,
            'ts': datetime.utcnow().isoformat(),
        }
        where = "symbol = ?"
        params = [symbol]
        if strategy_id:
            where += " AND strategy_id = ?"
            params.append(strategy_id)
        return self.db.update('positions', data, where, tuple(params))

    def snapshot_portfolio(
        self,
        cash: float,
        equity: float,
        buying_power: float,
        positions: List[Position],
        run_id: Optional[str] = None
    ) -> int:
        """Save a portfolio snapshot."""
        import json

        gross_exposure = sum(abs(p.market_value) for p in positions)
        net_exposure = sum(p.market_value for p in positions)
        positions_json = json.dumps([p.to_dict() for p in positions])

        return self.db.insert('portfolio_snapshots', {
            'ts': datetime.utcnow().isoformat(),
            'cash': cash,
            'equity': equity,
            'buying_power': buying_power,
            'gross_exposure': gross_exposure,
            'net_exposure': net_exposure,
            'positions_json': positions_json,
            'run_id': run_id,
        })


class ModelRepository(BaseRepository):
    """Repository for model registry operations."""

    def create(self, model: Model) -> int:
        """Register a new model."""
        return self.db.insert('models', model.to_dict())

    def get_by_id(self, model_id: str) -> Optional[Model]:
        """Get model by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM models WHERE model_id = ?",
            (model_id,)
        )
        return Model.from_row(row) if row else None

    def get_production_models(self) -> List[Model]:
        """Get all production models."""
        rows = self.db.fetch_all(
            "SELECT * FROM v_production_models"
        )
        return [Model.from_row(r) for r in rows]

    def get_by_type(self, model_type: ModelType) -> List[Model]:
        """Get models by type."""
        rows = self.db.fetch_all(
            "SELECT * FROM models WHERE model_type = ? ORDER BY created_at DESC",
            (model_type.value,)
        )
        return [Model.from_row(r) for r in rows]

    def promote_to_production(self, model_id: str) -> int:
        """Promote a model to production status."""
        return self.db.update(
            'models',
            {'status': 'production', 'promoted_at': datetime.utcnow().isoformat()},
            'model_id = ?',
            (model_id,)
        )

    def deprecate(self, model_id: str) -> int:
        """Deprecate a model."""
        return self.db.update(
            'models',
            {'status': 'deprecated', 'deprecated_at': datetime.utcnow().isoformat()},
            'model_id = ?',
            (model_id,)
        )

    def add_validation_result(
        self,
        model_id: str,
        validation_type: str,
        threshold: float,
        actual_value: float,
        passed: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add a validation result for a model."""
        import json
        return self.db.insert('model_validations', {
            'model_id': model_id,
            'validation_type': validation_type,
            'threshold': threshold,
            'actual_value': actual_value,
            'passed': 1 if passed else 0,
            'details_json': json.dumps(details) if details else None,
        })

    def get_validation_results(self, model_id: str) -> List[Dict[str, Any]]:
        """Get validation results for a model."""
        return self.db.fetch_all(
            "SELECT * FROM model_validations WHERE model_id = ? ORDER BY validated_at DESC",
            (model_id,)
        )


class StrategyRepository(BaseRepository):
    """Repository for strategy governance."""

    def create(self, strategy: Strategy) -> int:
        """Register a new strategy."""
        return self.db.insert('strategies', strategy.to_dict())

    def get_by_id(self, strategy_id: str) -> Optional[Strategy]:
        """Get strategy by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM strategies WHERE strategy_id = ?",
            (strategy_id,)
        )
        return Strategy.from_row(row) if row else None

    def get_active(self) -> List[Strategy]:
        """Get all active strategies."""
        rows = self.db.fetch_all(
            "SELECT * FROM strategies WHERE is_active = 1"
        )
        return [Strategy.from_row(r) for r in rows]

    def activate(self, strategy_id: str) -> int:
        """Activate a strategy."""
        return self.db.update(
            'strategies',
            {'is_active': 1},
            'strategy_id = ?',
            (strategy_id,)
        )

    def deactivate(self, strategy_id: str) -> int:
        """Deactivate a strategy."""
        return self.db.update(
            'strategies',
            {'is_active': 0},
            'strategy_id = ?',
            (strategy_id,)
        )

    def update_weights(self, weights: Dict[str, float]) -> int:
        """Update strategy weights."""
        count = 0
        for strategy_id, weight in weights.items():
            count += self.db.update(
                'strategies',
                {'weight': weight},
                'strategy_id = ?',
                (strategy_id,)
            )
        return count

    def record_performance(
        self,
        strategy_id: str,
        period: str,
        pnl: float,
        sharpe: Optional[float] = None,
        sortino: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        win_rate: Optional[float] = None,
        trade_count: int = 0,
        run_id: Optional[str] = None
    ) -> int:
        """Record strategy performance."""
        return self.db.insert('strategy_performance', {
            'strategy_id': strategy_id,
            'ts': datetime.utcnow().isoformat(),
            'period': period,
            'pnl': pnl,
            'sharpe': sharpe,
            'sortino': sortino,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trade_count': trade_count,
            'run_id': run_id,
        })

    def get_leaderboard(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get strategy performance leaderboard."""
        return self.db.fetch_all(
            """
            SELECT
                strategy_id,
                SUM(pnl) as total_pnl,
                AVG(sharpe) as avg_sharpe,
                MIN(max_drawdown) as worst_drawdown,
                AVG(win_rate) as avg_win_rate,
                SUM(trade_count) as total_trades
            FROM strategy_performance
            WHERE ts >= datetime('now', ? || ' days')
            GROUP BY strategy_id
            ORDER BY total_pnl DESC
            """,
            (f'-{days}',)
        )


class RiskRepository(BaseRepository):
    """Repository for risk management."""

    def create_limit(self, limit: RiskLimit) -> int:
        """Create a new risk limit."""
        return self.db.insert('risk_limits', limit.to_dict())

    def get_active_limits(self) -> List[RiskLimit]:
        """Get all active risk limits."""
        rows = self.db.fetch_all(
            "SELECT * FROM risk_limits WHERE is_active = 1"
        )
        return [RiskLimit.from_row(r) for r in rows]

    def get_limits_for_symbol(self, symbol: str) -> List[RiskLimit]:
        """Get risk limits applicable to a symbol."""
        rows = self.db.fetch_all(
            "SELECT * FROM risk_limits WHERE (symbol = ? OR symbol IS NULL) AND is_active = 1",
            (symbol,)
        )
        return [RiskLimit.from_row(r) for r in rows]

    def record_metric(
        self,
        metric_type: str,
        value: float,
        lookback_days: Optional[int] = None,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> int:
        """Record a risk metric."""
        return self.db.insert('risk_metrics', {
            'ts': datetime.utcnow().isoformat(),
            'metric_type': metric_type,
            'value': value,
            'lookback_days': lookback_days,
            'symbol': symbol,
            'strategy_id': strategy_id,
            'run_id': run_id,
        })

    def get_latest_metrics(self, metric_types: Optional[List[str]] = None) -> Dict[str, float]:
        """Get latest value for each risk metric."""
        if metric_types:
            placeholders = ','.join(['?' for _ in metric_types])
            sql = f"""
                SELECT metric_type, value
                FROM risk_metrics
                WHERE metric_type IN ({placeholders})
                AND ts = (SELECT MAX(ts) FROM risk_metrics r2 WHERE r2.metric_type = risk_metrics.metric_type)
            """
            rows = self.db.fetch_all(sql, tuple(metric_types))
        else:
            rows = self.db.fetch_all("""
                SELECT metric_type, value
                FROM risk_metrics
                WHERE ts = (SELECT MAX(ts) FROM risk_metrics r2 WHERE r2.metric_type = risk_metrics.metric_type)
            """)

        return {r['metric_type']: r['value'] for r in rows}

    def record_breach(
        self,
        limit_id: int,
        limit_type: str,
        limit_value: float,
        actual_value: float,
        action_taken: str,
        details: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None
    ) -> int:
        """Record a risk limit breach."""
        import json
        return self.db.insert('risk_breaches', {
            'ts': datetime.utcnow().isoformat(),
            'limit_id': limit_id,
            'limit_type': limit_type,
            'limit_value': limit_value,
            'actual_value': actual_value,
            'action_taken': action_taken,
            'details_json': json.dumps(details) if details else None,
            'run_id': run_id,
        })


class AuditRepository(BaseRepository):
    """Repository for audit logging."""

    def log(self, entry: AuditEntry) -> int:
        """Log an audit entry."""
        return self.db.insert('audit_log', entry.to_dict())

    def log_action(
        self,
        actor: str,
        action: str,
        object_type: str,
        object_id: str,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> int:
        """Convenience method to log an action."""
        entry = AuditEntry(
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            old_value=old_value,
            new_value=new_value,
            details=details,
            run_id=run_id,
            correlation_id=correlation_id,
        )
        return self.log(entry)

    def get_by_object(
        self,
        object_type: str,
        object_id: str,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Get audit entries for an object."""
        rows = self.db.fetch_all(
            "SELECT * FROM audit_log WHERE object_type = ? AND object_id = ? ORDER BY ts DESC LIMIT ?",
            (object_type, object_id, limit)
        )
        return [AuditEntry.from_row(r) for r in rows]

    def get_by_correlation(self, correlation_id: str) -> List[AuditEntry]:
        """Get audit entries by correlation ID."""
        rows = self.db.fetch_all(
            "SELECT * FROM audit_log WHERE correlation_id = ? ORDER BY ts ASC",
            (correlation_id,)
        )
        return [AuditEntry.from_row(r) for r in rows]

    def get_recent(
        self,
        limit: int = 100,
        actions: Optional[List[str]] = None
    ) -> List[AuditEntry]:
        """Get recent audit entries."""
        if actions:
            placeholders = ','.join(['?' for _ in actions])
            sql = f"SELECT * FROM audit_log WHERE action IN ({placeholders}) ORDER BY ts DESC LIMIT ?"
            rows = self.db.fetch_all(sql, tuple(actions) + (limit,))
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?",
                (limit,)
            )
        return [AuditEntry.from_row(r) for r in rows]


class HealthRepository(BaseRepository):
    """Repository for system health monitoring."""

    def record_metric(self, metric: HealthMetric) -> int:
        """Record a health metric."""
        return self.db.insert('system_health', metric.to_dict())

    def record(
        self,
        metric_type: str,
        value: float,
        unit: str,
        subsystem: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> int:
        """Convenience method to record a health metric."""
        metric = HealthMetric(
            metric_type=metric_type,
            value=value,
            unit=unit,
            subsystem=subsystem,
            run_id=run_id,
        )
        return self.record_metric(metric)

    def log_error(self, error: ErrorEntry) -> int:
        """Log an error."""
        return self.db.insert('errors', error.to_dict())

    def log_error_simple(
        self,
        subsystem: Subsystem,
        severity: Severity,
        message: str,
        error_code: Optional[str] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None
    ) -> int:
        """Convenience method to log an error."""
        error = ErrorEntry(
            subsystem=subsystem,
            severity=severity,
            message=message,
            error_code=error_code,
            stack_trace=stack_trace,
            context=context,
            run_id=run_id,
        )
        return self.log_error(error)

    def get_unresolved_errors(
        self,
        severity: Optional[Severity] = None,
        limit: int = 100
    ) -> List[ErrorEntry]:
        """Get unresolved errors."""
        sql = "SELECT * FROM errors WHERE resolved = 0"
        params = []

        if severity:
            sql += " AND severity = ?"
            params.append(severity.value)

        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(sql, tuple(params))
        return [ErrorEntry.from_row(r) for r in rows]

    def resolve_error(self, error_id: int, notes: str) -> int:
        """Mark an error as resolved."""
        return self.db.update(
            'errors',
            {
                'resolved': 1,
                'resolved_at': datetime.utcnow().isoformat(),
                'resolution_notes': notes,
            },
            'id = ?',
            (error_id,)
        )

    def record_grade(self, score: SelfGradeScore) -> int:
        """Record a self-grade score."""
        return self.db.insert('self_grade_scores', score.to_dict())

    def get_latest_grades(self) -> Dict[str, float]:
        """Get latest score for each category."""
        rows = self.db.fetch_all("""
            SELECT category, score
            FROM self_grade_scores
            WHERE ts = (
                SELECT MAX(ts) FROM self_grade_scores s2
                WHERE s2.category = self_grade_scores.category
            )
        """)
        return {r['category']: r['score'] for r in rows}

    def get_grade_history(
        self,
        category: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get score history for a category."""
        return self.db.fetch_all(
            """
            SELECT ts, score, issues_found
            FROM self_grade_scores
            WHERE category = ? AND ts >= datetime('now', ? || ' days')
            ORDER BY ts ASC
            """,
            (category, f'-{days}')
        )

    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        db_health = self.db.health_check()

        # Get error counts by severity
        error_counts = {}
        for severity in ['critical', 'error', 'warning']:
            row = self.db.fetch_one(
                "SELECT COUNT(*) as cnt FROM errors WHERE severity = ? AND resolved = 0",
                (severity,)
            )
            error_counts[severity] = row['cnt'] if row else 0

        # Get latest grades
        grades = self.get_latest_grades()

        # Determine overall status
        if error_counts.get('critical', 0) > 0:
            status = 'critical'
        elif error_counts.get('error', 0) > 5:
            status = 'degraded'
        elif grades.get('overall', 100) < 50:
            status = 'unhealthy'
        else:
            status = 'healthy'

        return {
            'status': status,
            'database': db_health,
            'unresolved_errors': error_counts,
            'grades': grades,
            'checked_at': datetime.utcnow().isoformat(),
        }
