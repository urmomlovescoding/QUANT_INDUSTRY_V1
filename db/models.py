"""
QUANT_INDUSTRY_V1 Database Models

Typed dataclasses representing database entities.
These provide type safety and IDE support for database operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class RunMode(Enum):
    BACKTEST = 'backtest'
    PAPER = 'paper'
    LIVE = 'live'
    RESEARCH = 'research'


class RunStatus(Enum):
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class SignalType(Enum):
    ENTRY_LONG = 'entry_long'
    ENTRY_SHORT = 'entry_short'
    EXIT = 'exit'
    HOLD = 'hold'
    SCALE_IN = 'scale_in'
    SCALE_OUT = 'scale_out'


class Direction(Enum):
    LONG = 'long'
    SHORT = 'short'
    FLAT = 'flat'


class OrderSide(Enum):
    BUY = 'buy'
    SELL = 'sell'


class OrderType(Enum):
    MARKET = 'market'
    LIMIT = 'limit'
    STOP = 'stop'
    STOP_LIMIT = 'stop_limit'
    TRAILING_STOP = 'trailing_stop'


class OrderStatus(Enum):
    PENDING = 'pending'
    SUBMITTED = 'submitted'
    ACCEPTED = 'accepted'
    PARTIAL = 'partial'
    FILLED = 'filled'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


class TimeInForce(Enum):
    DAY = 'day'
    GTC = 'gtc'
    IOC = 'ioc'
    FOK = 'fok'


class ModelType(Enum):
    SUPERVISED = 'supervised'
    RL = 'rl'
    ENSEMBLE = 'ensemble'
    META = 'meta'
    RULE_BASED = 'rule_based'


class ModelStatus(Enum):
    CANDIDATE = 'candidate'
    STAGING = 'staging'
    PRODUCTION = 'production'
    DEPRECATED = 'deprecated'
    FAILED = 'failed'


class Severity(Enum):
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class Subsystem(Enum):
    DATA = 'data'
    BRAIN = 'brain'
    EXECUTION = 'execution'
    RISK = 'risk'
    UI = 'ui'
    API = 'api'
    DB = 'db'
    CONFIG = 'config'
    UNKNOWN = 'unknown'


@dataclass
class Run:
    """Represents a single execution run for reproducibility tracking."""
    run_id: str
    mode: RunMode
    config_hash: str
    start_ts: datetime = field(default_factory=datetime.utcnow)
    end_ts: Optional[datetime] = None
    git_hash: Optional[str] = None
    status: RunStatus = RunStatus.RUNNING
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'run_id': self.run_id,
            'mode': self.mode.value,
            'config_hash': self.config_hash,
            'start_ts': self.start_ts.isoformat() if self.start_ts else None,
            'end_ts': self.end_ts.isoformat() if self.end_ts else None,
            'git_hash': self.git_hash,
            'status': self.status.value,
            'metadata_json': json.dumps(self.metadata) if self.metadata else None,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Run':
        return cls(
            id=row.get('id'),
            run_id=row['run_id'],
            mode=RunMode(row['mode']),
            config_hash=row['config_hash'],
            start_ts=datetime.fromisoformat(row['start_ts']) if row.get('start_ts') else None,
            end_ts=datetime.fromisoformat(row['end_ts']) if row.get('end_ts') else None,
            git_hash=row.get('git_hash'),
            status=RunStatus(row['status']),
            metadata=json.loads(row['metadata_json']) if row.get('metadata_json') else {},
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )


@dataclass
class MarketBar:
    """OHLCV market data bar."""
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    is_adjusted: bool = True
    vwap: Optional[float] = None
    trade_count: Optional[int] = None
    quality_score: float = 1.0
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'ts': self.ts.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'source': self.source,
            'is_adjusted': 1 if self.is_adjusted else 0,
            'vwap': self.vwap,
            'trade_count': self.trade_count,
            'quality_score': self.quality_score,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'MarketBar':
        return cls(
            id=row.get('id'),
            symbol=row['symbol'],
            timeframe=row['timeframe'],
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume'],
            source=row['source'],
            is_adjusted=bool(row.get('is_adjusted', 1)),
            vwap=row.get('vwap'),
            trade_count=row.get('trade_count'),
            quality_score=row.get('quality_score', 1.0),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )

    def validate(self) -> List[str]:
        """Validate OHLC relationships. Returns list of validation errors."""
        errors = []
        if self.high < self.low:
            errors.append(f"High ({self.high}) < Low ({self.low})")
        if self.open > self.high or self.open < self.low:
            errors.append(f"Open ({self.open}) outside High-Low range")
        if self.close > self.high or self.close < self.low:
            errors.append(f"Close ({self.close}) outside High-Low range")
        if self.volume < 0:
            errors.append(f"Negative volume ({self.volume})")
        return errors


@dataclass
class Signal:
    """Trading signal generated by a model."""
    symbol: str
    ts: datetime
    signal_type: SignalType
    direction: Direction
    strength: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    features_hash: str
    model_id: str
    strategy_id: Optional[str] = None
    regime: Optional[str] = None
    explanation: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'ts': self.ts.isoformat(),
            'signal_type': self.signal_type.value,
            'direction': self.direction.value,
            'strength': self.strength,
            'confidence': self.confidence,
            'features_hash': self.features_hash,
            'model_id': self.model_id,
            'strategy_id': self.strategy_id,
            'regime': self.regime,
            'explanation_json': json.dumps(self.explanation) if self.explanation else None,
            'run_id': self.run_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Signal':
        return cls(
            id=row.get('id'),
            symbol=row['symbol'],
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            signal_type=SignalType(row['signal_type']),
            direction=Direction(row['direction']),
            strength=row['strength'],
            confidence=row['confidence'],
            features_hash=row['features_hash'],
            model_id=row['model_id'],
            strategy_id=row.get('strategy_id'),
            regime=row.get('regime'),
            explanation=json.loads(row['explanation_json']) if row.get('explanation_json') else {},
            run_id=row.get('run_id'),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
        )


@dataclass
class Order:
    """Order submitted to broker."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    time_in_force: TimeInForce = TimeInForce.DAY
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    signal_id: Optional[int] = None
    strategy_id: Optional[str] = None
    model_id: Optional[str] = None
    run_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'qty': self.qty,
            'time_in_force': self.time_in_force.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'signal_id': self.signal_id,
            'strategy_id': self.strategy_id,
            'model_id': self.model_id,
            'run_id': self.run_id,
            'broker_order_id': self.broker_order_id,
            'notes': self.notes,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Order':
        return cls(
            id=row.get('id'),
            order_id=row['order_id'],
            symbol=row['symbol'],
            side=OrderSide(row['side']),
            order_type=OrderType(row['order_type']),
            qty=row['qty'],
            time_in_force=TimeInForce(row.get('time_in_force', 'day')),
            limit_price=row.get('limit_price'),
            stop_price=row.get('stop_price'),
            status=OrderStatus(row['status']),
            submitted_at=datetime.fromisoformat(row['submitted_at']) if row.get('submitted_at') else None,
            filled_at=datetime.fromisoformat(row['filled_at']) if row.get('filled_at') else None,
            cancelled_at=datetime.fromisoformat(row['cancelled_at']) if row.get('cancelled_at') else None,
            signal_id=row.get('signal_id'),
            strategy_id=row.get('strategy_id'),
            model_id=row.get('model_id'),
            run_id=row.get('run_id'),
            broker_order_id=row.get('broker_order_id'),
            notes=row.get('notes'),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )


@dataclass
class Trade:
    """Executed trade fill."""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: float
    executed_at: datetime
    fill_status: str = 'full'
    commission: float = 0.0
    slippage: Optional[float] = None
    expected_price: Optional[float] = None
    strategy_id: Optional[str] = None
    model_id: Optional[str] = None
    run_id: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'qty': self.qty,
            'price': self.price,
            'executed_at': self.executed_at.isoformat(),
            'fill_status': self.fill_status,
            'commission': self.commission,
            'slippage': self.slippage,
            'expected_price': self.expected_price,
            'strategy_id': self.strategy_id,
            'model_id': self.model_id,
            'run_id': self.run_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Trade':
        return cls(
            id=row.get('id'),
            trade_id=row['trade_id'],
            order_id=row['order_id'],
            symbol=row['symbol'],
            side=OrderSide(row['side']),
            qty=row['qty'],
            price=row['price'],
            executed_at=datetime.fromisoformat(row['executed_at']) if isinstance(row['executed_at'], str) else row['executed_at'],
            fill_status=row.get('fill_status', 'full'),
            commission=row.get('commission', 0.0),
            slippage=row.get('slippage'),
            expected_price=row.get('expected_price'),
            strategy_id=row.get('strategy_id'),
            model_id=row.get('model_id'),
            run_id=row.get('run_id'),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
        )


@dataclass
class Position:
    """Current or historical position."""
    symbol: str
    ts: datetime
    qty: float
    avg_price: float
    cost_basis: float
    market_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: float = 0.0
    strategy_id: Optional[str] = None
    run_id: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def market_value(self) -> float:
        """Calculate current market value."""
        price = self.market_price or self.avg_price
        return self.qty * price

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'ts': self.ts.isoformat(),
            'qty': self.qty,
            'avg_price': self.avg_price,
            'cost_basis': self.cost_basis,
            'market_price': self.market_price,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'strategy_id': self.strategy_id,
            'run_id': self.run_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Position':
        return cls(
            id=row.get('id'),
            symbol=row['symbol'],
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            qty=row['qty'],
            avg_price=row['avg_price'],
            cost_basis=row['cost_basis'],
            market_price=row.get('market_price'),
            unrealized_pnl=row.get('unrealized_pnl'),
            realized_pnl=row.get('realized_pnl', 0.0),
            strategy_id=row.get('strategy_id'),
            run_id=row.get('run_id'),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )


@dataclass
class Model:
    """Trained model registry entry."""
    model_id: str
    model_type: ModelType
    name: str
    dataset_hash: str
    feature_hash: str
    hyperparams: Dict[str, Any]
    version: int = 1
    description: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    artifact_path: Optional[str] = None
    status: ModelStatus = ModelStatus.CANDIDATE
    promoted_at: Optional[datetime] = None
    deprecated_at: Optional[datetime] = None
    run_id: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_id': self.model_id,
            'model_type': self.model_type.value,
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'dataset_hash': self.dataset_hash,
            'feature_hash': self.feature_hash,
            'hyperparams_json': json.dumps(self.hyperparams),
            'metrics_json': json.dumps(self.metrics) if self.metrics else None,
            'training_config_json': json.dumps(self.training_config) if self.training_config else None,
            'artifact_path': self.artifact_path,
            'status': self.status.value,
            'promoted_at': self.promoted_at.isoformat() if self.promoted_at else None,
            'deprecated_at': self.deprecated_at.isoformat() if self.deprecated_at else None,
            'run_id': self.run_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Model':
        return cls(
            id=row.get('id'),
            model_id=row['model_id'],
            model_type=ModelType(row['model_type']),
            name=row['name'],
            version=row.get('version', 1),
            description=row.get('description'),
            dataset_hash=row['dataset_hash'],
            feature_hash=row['feature_hash'],
            hyperparams=json.loads(row['hyperparams_json']) if row.get('hyperparams_json') else {},
            metrics=json.loads(row['metrics_json']) if row.get('metrics_json') else {},
            training_config=json.loads(row['training_config_json']) if row.get('training_config_json') else {},
            artifact_path=row.get('artifact_path'),
            status=ModelStatus(row.get('status', 'candidate')),
            promoted_at=datetime.fromisoformat(row['promoted_at']) if row.get('promoted_at') else None,
            deprecated_at=datetime.fromisoformat(row['deprecated_at']) if row.get('deprecated_at') else None,
            run_id=row.get('run_id'),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )


@dataclass
class Strategy:
    """Strategy registry entry."""
    strategy_id: str
    name: str
    strategy_type: str
    config: Dict[str, Any]
    version: int = 1
    description: Optional[str] = None
    required_data: Dict[str, Any] = field(default_factory=dict)
    failure_modes: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = False
    weight: float = 1.0
    max_allocation: float = 0.25
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy_id': self.strategy_id,
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'strategy_type': self.strategy_type,
            'config_json': json.dumps(self.config),
            'required_data_json': json.dumps(self.required_data) if self.required_data else None,
            'failure_modes_json': json.dumps(self.failure_modes) if self.failure_modes else None,
            'is_active': 1 if self.is_active else 0,
            'weight': self.weight,
            'max_allocation': self.max_allocation,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Strategy':
        return cls(
            id=row.get('id'),
            strategy_id=row['strategy_id'],
            name=row['name'],
            version=row.get('version', 1),
            description=row.get('description'),
            strategy_type=row['strategy_type'],
            config=json.loads(row['config_json']) if row.get('config_json') else {},
            required_data=json.loads(row['required_data_json']) if row.get('required_data_json') else {},
            failure_modes=json.loads(row['failure_modes_json']) if row.get('failure_modes_json') else {},
            is_active=bool(row.get('is_active', 0)),
            weight=row.get('weight', 1.0),
            max_allocation=row.get('max_allocation', 0.25),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )


@dataclass
class RiskLimit:
    """Risk constraint configuration."""
    limit_type: str
    limit_value: float
    symbol: Optional[str] = None
    sector: Optional[str] = None
    strategy_id: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'limit_type': self.limit_type,
            'limit_value': self.limit_value,
            'symbol': self.symbol,
            'sector': self.sector,
            'strategy_id': self.strategy_id,
            'is_active': 1 if self.is_active else 0,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'RiskLimit':
        return cls(
            id=row.get('id'),
            limit_type=row['limit_type'],
            limit_value=row['limit_value'],
            symbol=row.get('symbol'),
            sector=row.get('sector'),
            strategy_id=row.get('strategy_id'),
            is_active=bool(row.get('is_active', 1)),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None,
        )


@dataclass
class AuditEntry:
    """Audit log entry."""
    actor: str
    action: str
    object_type: str
    object_id: str
    ts: datetime = field(default_factory=datetime.utcnow)
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    run_id: Optional[str] = None
    correlation_id: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ts': self.ts.isoformat(),
            'actor': self.actor,
            'action': self.action,
            'object_type': self.object_type,
            'object_id': self.object_id,
            'old_value_json': json.dumps(self.old_value) if self.old_value else None,
            'new_value_json': json.dumps(self.new_value) if self.new_value else None,
            'details_json': json.dumps(self.details) if self.details else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'run_id': self.run_id,
            'correlation_id': self.correlation_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'AuditEntry':
        return cls(
            id=row.get('id'),
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            actor=row['actor'],
            action=row['action'],
            object_type=row['object_type'],
            object_id=row['object_id'],
            old_value=json.loads(row['old_value_json']) if row.get('old_value_json') else None,
            new_value=json.loads(row['new_value_json']) if row.get('new_value_json') else None,
            details=json.loads(row['details_json']) if row.get('details_json') else None,
            ip_address=row.get('ip_address'),
            user_agent=row.get('user_agent'),
            run_id=row.get('run_id'),
            correlation_id=row.get('correlation_id'),
        )


@dataclass
class ErrorEntry:
    """System error log entry."""
    subsystem: Subsystem
    severity: Severity
    message: str
    ts: datetime = field(default_factory=datetime.utcnow)
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None
    correlation_id: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ts': self.ts.isoformat(),
            'subsystem': self.subsystem.value,
            'severity': self.severity.value,
            'error_code': self.error_code,
            'message': self.message,
            'stack_trace': self.stack_trace,
            'context_json': json.dumps(self.context) if self.context else None,
            'run_id': self.run_id,
            'correlation_id': self.correlation_id,
            'resolved': 1 if self.resolved else 0,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'ErrorEntry':
        return cls(
            id=row.get('id'),
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            subsystem=Subsystem(row['subsystem']),
            severity=Severity(row['severity']),
            error_code=row.get('error_code'),
            message=row['message'],
            stack_trace=row.get('stack_trace'),
            context=json.loads(row['context_json']) if row.get('context_json') else None,
            run_id=row.get('run_id'),
            correlation_id=row.get('correlation_id'),
            resolved=bool(row.get('resolved', 0)),
            resolved_at=datetime.fromisoformat(row['resolved_at']) if row.get('resolved_at') else None,
            resolution_notes=row.get('resolution_notes'),
        )


@dataclass
class HealthMetric:
    """System health metric."""
    metric_type: str
    value: float
    unit: str
    ts: datetime = field(default_factory=datetime.utcnow)
    subsystem: Optional[str] = None
    run_id: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ts': self.ts.isoformat(),
            'metric_type': self.metric_type,
            'value': self.value,
            'unit': self.unit,
            'subsystem': self.subsystem,
            'run_id': self.run_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'HealthMetric':
        return cls(
            id=row.get('id'),
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            metric_type=row['metric_type'],
            value=row['value'],
            unit=row['unit'],
            subsystem=row.get('subsystem'),
            run_id=row.get('run_id'),
        )


@dataclass
class SelfGradeScore:
    """Self-grading system score."""
    category: str
    score: float
    ts: datetime = field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None
    issues_found: int = 0
    run_id: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ts': self.ts.isoformat(),
            'category': self.category,
            'score': self.score,
            'details_json': json.dumps(self.details) if self.details else None,
            'issues_found': self.issues_found,
            'run_id': self.run_id,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'SelfGradeScore':
        return cls(
            id=row.get('id'),
            ts=datetime.fromisoformat(row['ts']) if isinstance(row['ts'], str) else row['ts'],
            category=row['category'],
            score=row['score'],
            details=json.loads(row['details_json']) if row.get('details_json') else None,
            issues_found=row.get('issues_found', 0),
            run_id=row.get('run_id'),
        )
