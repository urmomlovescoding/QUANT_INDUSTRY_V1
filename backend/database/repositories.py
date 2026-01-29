"""
Database Repositories
=====================
Data access patterns for the quant trading platform.

Each repository provides:
- CRUD operations
- Specialized queries
- Caching integration
- Async support
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
import logging

from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Trade, Position, Signal, MarketBar, 
    PortfolioSnapshot, RiskMetric, BacktestRun, Feature,
    Side, OrderStatus, SignalStatus
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def commit(self):
        self.session.commit()
    
    def rollback(self):
        self.session.rollback()


class AsyncBaseRepository:
    """Async base repository."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def commit(self):
        await self.session.commit()
    
    async def rollback(self):
        await self.session.rollback()


# ============== TRADE REPOSITORY ==============

class TradeRepository(BaseRepository):
    """Repository for trade operations."""
    
    def create(self, **kwargs) -> Trade:
        """Create a new trade."""
        trade = Trade(**kwargs)
        self.session.add(trade)
        self.session.flush()
        return trade
    
    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        return self.session.query(Trade).filter(
            Trade.trade_id == trade_id
        ).first()
    
    def get_recent(self, limit: int = 50) -> List[Trade]:
        """Get recent trades."""
        return self.session.query(Trade).order_by(
            desc(Trade.created_at)
        ).limit(limit).all()
    
    def get_by_symbol(
        self, 
        symbol: str, 
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[Trade]:
        """Get trades for a symbol."""
        query = self.session.query(Trade).filter(Trade.symbol == symbol)
        
        if start:
            query = query.filter(Trade.entry_time >= start)
        if end:
            query = query.filter(Trade.entry_time <= end)
        
        return query.order_by(desc(Trade.entry_time)).all()
    
    def get_by_strategy(self, strategy: str, days: int = 30) -> List[Trade]:
        """Get trades for a strategy."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.session.query(Trade).filter(
            and_(
                Trade.strategy == strategy,
                Trade.entry_time >= cutoff
            )
        ).order_by(desc(Trade.entry_time)).all()
    
    def get_open(self) -> List[Trade]:
        """Get open trades."""
        return self.session.query(Trade).filter(
            Trade.status.in_([OrderStatus.PENDING, OrderStatus.PARTIAL])
        ).all()
    
    def get_pnl_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get P&L summary."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        result = self.session.query(
            func.sum(Trade.realized_pnl).label('total_pnl'),
            func.count(Trade.id).label('total_trades'),
            func.sum(
                func.case((Trade.realized_pnl > 0, 1), else_=0)
            ).label('winning_trades'),
            func.avg(
                func.case((Trade.realized_pnl > 0, Trade.realized_pnl), else_=None)
            ).label('avg_win'),
            func.avg(
                func.case((Trade.realized_pnl < 0, Trade.realized_pnl), else_=None)
            ).label('avg_loss'),
        ).filter(
            and_(
                Trade.status == OrderStatus.FILLED,
                Trade.exit_time >= cutoff
            )
        ).first()
        
        total_trades = result.total_trades or 0
        winning_trades = result.winning_trades or 0
        
        return {
            'total_pnl': float(result.total_pnl or 0),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'avg_win': float(result.avg_win or 0),
            'avg_loss': float(result.avg_loss or 0),
        }
    
    def update_status(self, trade_id: str, status: OrderStatus) -> Optional[Trade]:
        """Update trade status."""
        trade = self.get_by_id(trade_id)
        if trade:
            trade.status = status
            self.session.flush()
        return trade


# ============== POSITION REPOSITORY ==============

class PositionRepository(BaseRepository):
    """Repository for position operations."""
    
    def get_all(self) -> List[Position]:
        """Get all positions."""
        return self.session.query(Position).all()
    
    def get_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        return self.session.query(Position).filter(
            Position.symbol == symbol
        ).first()
    
    def upsert(self, symbol: str, **kwargs) -> Position:
        """Insert or update position."""
        position = self.get_by_symbol(symbol)
        
        if position:
            for key, value in kwargs.items():
                if hasattr(position, key):
                    setattr(position, key, value)
        else:
            position = Position(symbol=symbol, **kwargs)
            self.session.add(position)
        
        self.session.flush()
        return position
    
    def delete(self, symbol: str) -> bool:
        """Delete position (when fully closed)."""
        position = self.get_by_symbol(symbol)
        if position:
            self.session.delete(position)
            return True
        return False
    
    def get_exposure(self) -> Dict[str, Any]:
        """Get portfolio exposure summary."""
        positions = self.get_all()
        
        long_value = sum(
            float(p.market_value or 0) 
            for p in positions if p.side == Side.LONG
        )
        short_value = sum(
            float(p.market_value or 0) 
            for p in positions if p.side == Side.SHORT
        )
        
        return {
            'long_exposure': long_value,
            'short_exposure': short_value,
            'net_exposure': long_value - short_value,
            'gross_exposure': long_value + short_value,
            'position_count': len(positions),
        }


# ============== SIGNAL REPOSITORY ==============

class SignalRepository(BaseRepository):
    """Repository for signal operations."""
    
    def create(self, **kwargs) -> Signal:
        """Create a new signal."""
        signal = Signal(**kwargs)
        self.session.add(signal)
        self.session.flush()
        return signal
    
    def get_active(self) -> List[Signal]:
        """Get active signals."""
        return self.session.query(Signal).filter(
            Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
        ).order_by(desc(Signal.created_at)).all()
    
    def get_by_strategy(
        self, 
        strategy: str, 
        status: Optional[SignalStatus] = None
    ) -> List[Signal]:
        """Get signals by strategy."""
        query = self.session.query(Signal).filter(Signal.strategy == strategy)
        
        if status:
            query = query.filter(Signal.status == status)
        
        return query.order_by(desc(Signal.created_at)).all()
    
    def expire_old(self) -> int:
        """Expire signals past their expiry time."""
        now = datetime.utcnow()
        count = self.session.query(Signal).filter(
            and_(
                Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE]),
                Signal.expires_at < now
            )
        ).update({Signal.status: SignalStatus.EXPIRED})
        
        return count


# ============== MARKET DATA REPOSITORY ==============

class MarketDataRepository(BaseRepository):
    """Repository for market data operations."""
    
    def insert_bars(self, bars: List[Dict[str, Any]], symbol: str, timeframe: str) -> int:
        """Bulk insert market bars."""
        count = 0
        for bar in bars:
            existing = self.session.query(MarketBar).filter(
                and_(
                    MarketBar.symbol == symbol,
                    MarketBar.timeframe == timeframe,
                    MarketBar.timestamp == bar['timestamp']
                )
            ).first()
            
            if not existing:
                market_bar = MarketBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=bar['timestamp'],
                    open=bar['open'],
                    high=bar['high'],
                    low=bar['low'],
                    close=bar['close'],
                    volume=bar['volume'],
                    vwap=bar.get('vwap'),
                    trade_count=bar.get('trade_count'),
                    source=bar.get('source', 'alpaca')
                )
                self.session.add(market_bar)
                count += 1
        
        self.session.flush()
        return count
    
    def get_bars(
        self,
        symbol: str,
        timeframe: str = '1d',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[MarketBar]:
        """Get market bars."""
        query = self.session.query(MarketBar).filter(
            and_(
                MarketBar.symbol == symbol,
                MarketBar.timeframe == timeframe
            )
        )
        
        if start:
            query = query.filter(MarketBar.timestamp >= start)
        if end:
            query = query.filter(MarketBar.timestamp <= end)
        
        return query.order_by(MarketBar.timestamp).limit(limit).all()
    
    def get_latest_bar(self, symbol: str, timeframe: str = '1d') -> Optional[MarketBar]:
        """Get the most recent bar."""
        return self.session.query(MarketBar).filter(
            and_(
                MarketBar.symbol == symbol,
                MarketBar.timeframe == timeframe
            )
        ).order_by(desc(MarketBar.timestamp)).first()
    
    def get_ohlcv_arrays(
        self,
        symbol: str,
        timeframe: str = '1d',
        days: int = 365
    ) -> Dict[str, List]:
        """Get OHLCV data as arrays (for analysis)."""
        start = datetime.utcnow() - timedelta(days=days)
        bars = self.get_bars(symbol, timeframe, start=start)
        
        return {
            'timestamp': [b.timestamp for b in bars],
            'open': [float(b.open) for b in bars],
            'high': [float(b.high) for b in bars],
            'low': [float(b.low) for b in bars],
            'close': [float(b.close) for b in bars],
            'volume': [float(b.volume) for b in bars],
        }


# ============== PORTFOLIO REPOSITORY ==============

class PortfolioRepository(BaseRepository):
    """Repository for portfolio snapshots."""
    
    def create_snapshot(self, **kwargs) -> PortfolioSnapshot:
        """Create portfolio snapshot."""
        snapshot = PortfolioSnapshot(**kwargs)
        self.session.add(snapshot)
        self.session.flush()
        return snapshot
    
    def get_equity_curve(self, days: int = 90) -> List[PortfolioSnapshot]:
        """Get equity curve data."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.session.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.timestamp >= cutoff
        ).order_by(PortfolioSnapshot.timestamp).all()
    
    def get_latest(self) -> Optional[PortfolioSnapshot]:
        """Get most recent snapshot."""
        return self.session.query(PortfolioSnapshot).order_by(
            desc(PortfolioSnapshot.timestamp)
        ).first()


# ============== FEATURE REPOSITORY ==============

class FeatureRepository(BaseRepository):
    """Repository for ML features."""
    
    def store_features(
        self,
        symbol: str,
        timestamp: datetime,
        feature_set: str,
        values: Dict[str, Any],
        version: str = "1.0"
    ) -> Feature:
        """Store computed features."""
        feature = Feature(
            symbol=symbol,
            timestamp=timestamp,
            feature_set=feature_set,
            values=values,
            version=version
        )
        self.session.merge(feature)
        self.session.flush()
        return feature
    
    def get_features(
        self,
        symbol: str,
        feature_set: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[Feature]:
        """Get features for a symbol."""
        query = self.session.query(Feature).filter(
            and_(
                Feature.symbol == symbol,
                Feature.feature_set == feature_set
            )
        )
        
        if start:
            query = query.filter(Feature.timestamp >= start)
        if end:
            query = query.filter(Feature.timestamp <= end)
        
        return query.order_by(Feature.timestamp).all()
    
    def get_latest_features(
        self,
        symbol: str,
        feature_set: str
    ) -> Optional[Dict[str, Any]]:
        """Get most recent features."""
        feature = self.session.query(Feature).filter(
            and_(
                Feature.symbol == symbol,
                Feature.feature_set == feature_set
            )
        ).order_by(desc(Feature.timestamp)).first()
        
        return feature.values if feature else None
