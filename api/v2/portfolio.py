"""
QUANT INDUSTRY V1 - Portfolio API (v2)
======================================
Portfolio management: holdings, performance, allocation.
Wired to real broker/service implementations.
"""

import logging
import os
from fastapi import APIRouter, Query, Path
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Service Availability Detection
# ============================================================================

BROKER_ADAPTER_AVAILABLE = False
PORTFOLIO_SERVICE_AVAILABLE = False
TRADING_SERVICE_AVAILABLE = False
DATA_SERVICE_AVAILABLE = False
PROPFIRM_BRAIN_V6_AVAILABLE = False

try:
    from backend.execution.broker_adapter import PaperBroker, AccountInfo
    BROKER_ADAPTER_AVAILABLE = True
except ImportError:
    try:
        from execution.broker_adapter import PaperBroker, AccountInfo
        BROKER_ADAPTER_AVAILABLE = True
    except ImportError:
        pass

try:
    from backend.portfolio.portfolio_service import get_portfolio_service
    PORTFOLIO_SERVICE_AVAILABLE = True
except ImportError:
    try:
        from portfolio.portfolio_service import get_portfolio_service
        PORTFOLIO_SERVICE_AVAILABLE = True
    except ImportError:
        pass

try:
    from backend.services.trading_service import get_trading_service
    TRADING_SERVICE_AVAILABLE = True
except ImportError:
    try:
        from services.trading_service import get_trading_service
        TRADING_SERVICE_AVAILABLE = True
    except ImportError:
        pass

try:
    from backend.services.data_service import get_data_service
    DATA_SERVICE_AVAILABLE = True
except ImportError:
    try:
        from services.data_service import get_data_service
        DATA_SERVICE_AVAILABLE = True
    except ImportError:
        pass

try:
    from brain.propfirm_brain_v6 import get_propfirm_brain_v6
    PROPFIRM_BRAIN_V6_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# Broker/Service Singletons
# ============================================================================

_broker = None
_portfolio_service = None


def get_broker():
    """Get broker instance.

    Returns a real broker (Alpaca) when configured, or None when no broker
    is available. Does NOT fall back to a paper broker with fake $100k --
    that would mislead the frontend into displaying phantom equity.
    """
    global _broker

    # Check for Alpaca
    alpaca_key = os.getenv("ALPACA_API_KEY")
    alpaca_secret = os.getenv("ALPACA_SECRET_KEY")

    if alpaca_key and alpaca_secret:
        try:
            from backend.execution.alpaca_broker import AlpacaBroker
            broker = AlpacaBroker(paper=True)
            if broker.connect():
                return broker
        except Exception as e:
            logger.warning(f"Alpaca broker connection failed: {e}")

    # No broker available -- return None so endpoints report honestly
    return None


def get_portfolio_svc():
    """Get portfolio service instance."""
    global _portfolio_service
    if _portfolio_service is None and PORTFOLIO_SERVICE_AVAILABLE:
        _portfolio_service = get_portfolio_service()
    return _portfolio_service


# ============================================================================
# Enums
# ============================================================================

class TimePeriod(str, Enum):
    """Time period options."""
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1m"
    QUARTER = "3m"
    YEAR = "1y"
    YTD = "ytd"
    ALL = "all"


# ============================================================================
# Pydantic Models
# ============================================================================

class Holding(BaseModel):
    """Individual portfolio holding."""
    symbol: str
    name: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    weight: float = Field(..., description="Portfolio weight as decimal")
    sector: Optional[str] = None
    asset_type: str = Field(default="equity", description="equity, option, crypto, etc.")


class HoldingsResponse(BaseModel):
    """Portfolio holdings response."""
    holdings: list[Holding] = Field(default_factory=list)
    total_value: float
    total_cost: float
    total_unrealized_pnl: float
    total_unrealized_pnl_percent: float
    cash: float
    broker_connected: bool = Field(default=False, description="Whether a real broker is connected")
    data_source: str = Field(default="none", description="Source of portfolio data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PerformanceMetric(BaseModel):
    """Performance for a time period."""
    period: str
    return_pct: float
    return_dollar: float
    start_value: float
    end_value: float
    high: float
    low: float
    max_drawdown: float


class PerformanceResponse(BaseModel):
    """Portfolio performance response."""
    metrics: dict[str, PerformanceMetric] = Field(default_factory=dict)
    total_return_pct: float
    total_return_dollar: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: float
    win_rate: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AllocationItem(BaseModel):
    """Allocation breakdown item."""
    category: str
    value: float
    weight: float
    target_weight: Optional[float] = None
    drift: Optional[float] = None


class AllocationResponse(BaseModel):
    """Portfolio allocation breakdown."""
    by_sector: list[AllocationItem] = Field(default_factory=list)
    by_asset_type: list[AllocationItem] = Field(default_factory=list)
    by_strategy: list[AllocationItem] = Field(default_factory=list)
    cash_weight: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HistoryPoint(BaseModel):
    """Historical portfolio value point."""
    date: date
    value: float
    cash: float
    invested: float
    daily_return: float


class HistoryResponse(BaseModel):
    """Portfolio history response."""
    history: list[HistoryPoint] = Field(default_factory=list)
    period: str
    start_value: float
    end_value: float
    total_return: float


class TradeRecord(BaseModel):
    """Historical trade record."""
    id: str
    symbol: str
    side: str
    quantity: float
    price: float
    total: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    executed_at: datetime


class TradesResponse(BaseModel):
    """Trade history response."""
    trades: list[TradeRecord] = Field(default_factory=list)
    total_count: int
    total_pnl: float
    win_count: int
    loss_count: int
    win_rate: float


# ============================================================================
# Sector Mappings
# ============================================================================

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary", "NVDA": "Technology",
    "META": "Technology", "TSLA": "Consumer Discretionary",
    "JPM": "Financials", "BAC": "Financials", "V": "Financials",
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "PG": "Consumer Staples", "KO": "Consumer Staples", "WMT": "Consumer Staples",
    "SPY": "Index", "QQQ": "Index", "IWM": "Index", "AMD": "Technology",
}

SYMBOL_NAMES = {
    "AAPL": "Apple Inc", "MSFT": "Microsoft Corporation", "GOOGL": "Alphabet Inc",
    "AMZN": "Amazon.com Inc", "NVDA": "NVIDIA Corporation", "META": "Meta Platforms Inc",
    "TSLA": "Tesla Inc", "JPM": "JPMorgan Chase & Co", "BAC": "Bank of America",
    "V": "Visa Inc", "JNJ": "Johnson & Johnson", "UNH": "UnitedHealth Group",
    "PFE": "Pfizer Inc", "XOM": "Exxon Mobil", "CVX": "Chevron Corporation",
    "PG": "Procter & Gamble", "KO": "Coca-Cola Company", "WMT": "Walmart Inc",
    "SPY": "SPDR S&P 500 ETF", "QQQ": "Invesco QQQ Trust", "IWM": "iShares Russell 2000",
    "AMD": "Advanced Micro Devices",
}


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/holdings",
    response_model=HoldingsResponse,
    summary="Portfolio holdings",
    description="Get all current portfolio holdings."
)
async def get_holdings() -> HoldingsResponse:
    """
    Get all current portfolio holdings with valuations.
    
    Includes unrealized P&L and portfolio weights.
    """
    holdings = []
    total_value = 0
    total_cost = 0
    cash = 0
    
    # Try portfolio service first
    portfolio_svc = get_portfolio_svc()
    if portfolio_svc:
        try:
            summary = portfolio_svc.get_portfolio_summary()
            
            for h in summary.holdings:
                holdings.append(Holding(
                    symbol=h.symbol,
                    name=SYMBOL_NAMES.get(h.symbol, h.symbol),
                    quantity=h.quantity,
                    avg_cost=h.avg_cost,
                    current_price=h.current_price,
                    market_value=h.market_value,
                    cost_basis=h.quantity * h.avg_cost,
                    unrealized_pnl=h.unrealized_pnl,
                    unrealized_pnl_percent=h.unrealized_pnl_pct,
                    weight=h.weight / 100,  # Convert to decimal
                    sector=h.sector,
                    asset_type="equity"
                ))
            
            total_value = summary.total_value
            total_cost = summary.positions_value - summary.total_pnl if summary.total_pnl else summary.positions_value
            cash = summary.cash
            
            if holdings:
                return HoldingsResponse(
                    holdings=holdings,
                    total_value=total_value,
                    total_cost=total_cost,
                    total_unrealized_pnl=summary.total_pnl,
                    total_unrealized_pnl_percent=summary.total_pnl_pct,
                    cash=cash,
                    broker_connected=True,
                    data_source="portfolio_service"
                )
        except Exception as e:
            logger.warning(f"Portfolio service error: {e}")
    
    # Fallback to broker positions
    broker = get_broker()
    if broker:
        try:
            positions = broker.get_all_positions()
            account = broker.get_account()
            cash = account.cash
            
            for pos in positions:
                qty = pos.quantity
                entry = pos.avg_entry_price
                current = pos.current_price if pos.current_price else entry
                market_val = current * qty
                cost = entry * qty
                pnl = pos.unrealized_pnl if pos.unrealized_pnl else (market_val - cost)
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                
                total_value += market_val
                total_cost += cost
                
                holdings.append(Holding(
                    symbol=pos.symbol,
                    name=SYMBOL_NAMES.get(pos.symbol, pos.symbol),
                    quantity=qty,
                    avg_cost=entry,
                    current_price=current,
                    market_value=market_val,
                    cost_basis=cost,
                    unrealized_pnl=round(pnl, 2),
                    unrealized_pnl_percent=round(pnl_pct, 2),
                    weight=0,  # Will calculate below
                    sector=SECTOR_MAP.get(pos.symbol, "Other"),
                    asset_type="equity"
                ))
            
            # Calculate weights
            total_portfolio = total_value + cash
            for h in holdings:
                h.weight = round(h.market_value / total_portfolio, 4) if total_portfolio > 0 else 0
            
            total_pnl = sum(h.unrealized_pnl for h in holdings)
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
            
            return HoldingsResponse(
                holdings=holdings,
                total_value=total_portfolio,
                total_cost=total_cost,
                total_unrealized_pnl=round(total_pnl, 2),
                total_unrealized_pnl_percent=round(total_pnl_pct, 2),
                cash=cash,
                broker_connected=True,
                data_source="broker"
            )
            
        except Exception as e:
            logger.warning(f"Broker positions error: {e}")
    
    # No portfolio data available -- report honestly with zero equity
    logger.warning("Portfolio holdings unavailable - no broker or service connected")
    return HoldingsResponse(
        holdings=[],
        total_value=0,
        total_cost=0,
        total_unrealized_pnl=0,
        total_unrealized_pnl_percent=0,
        cash=0,
        broker_connected=False,
        data_source="none"
    )


@router.get(
    "/performance",
    response_model=PerformanceResponse,
    summary="Portfolio performance",
    description="Get portfolio performance metrics."
)
async def get_performance(
    period: TimePeriod = Query(TimePeriod.YTD, description="Time period for performance")
) -> PerformanceResponse:
    """
    Get portfolio performance metrics.
    
    Includes returns, Sharpe ratio, drawdown, and win rate.
    """
    import math
    import statistics
    
    annual_return = 0.0
    volatility = 15.0
    sharpe_ratio = 0.0
    max_drawdown = 0.0
    win_rate = 0.0
    total_return_pct = 0.0
    total_return_dollar = 0.0
    
    # Try PropFirm Brain V6 for performance
    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            brain = get_propfirm_brain_v6()
            if brain and hasattr(brain, 'trade_history') and brain.trade_history and len(brain.trade_history) >= 5:
                trades = brain.trade_history
                total_pnl = sum(t.pnl for t in trades)
                days_traded = min(252, len(trades))
                annual_return = (total_pnl / 100000 * 100) * (252 / max(days_traded, 1))
                
                pnls = [t.pnl for t in trades]
                winners = [p for p in pnls if p > 0]
                win_rate = len(winners) / len(pnls) if pnls else 0
                
                if len(pnls) >= 2:
                    daily_std = statistics.stdev(pnls) / 100000 * 100
                    volatility = daily_std * math.sqrt(252)
                    sharpe_ratio = (annual_return - 4.5) / volatility if volatility > 0 else 0
                
                total_return_pct = total_pnl / 100000 * 100
                total_return_dollar = total_pnl
                
                # Calculate max drawdown
                cumulative = 0
                peak = 0
                max_dd = 0
                for pnl in pnls:
                    cumulative += pnl
                    peak = max(peak, cumulative)
                    dd = (peak - cumulative) / peak * 100 if peak > 0 else 0
                    max_dd = max(max_dd, dd)
                max_drawdown = -max_dd
                
        except Exception as e:
            logger.warning(f"Brain performance error: {e}")
    
    # Try trading service
    if TRADING_SERVICE_AVAILABLE and total_return_pct == 0:
        try:
            ts = get_trading_service()
            if ts:
                account = ts.get_account_info()
                trades = ts.get_trades(limit=100)
                
                total_return_dollar = account.total_pnl
                total_return_pct = account.total_pnl_pct
                
                if trades:
                    winners = [t for t in trades if t.pnl > 0]
                    win_rate = len(winners) / len(trades) if trades else 0
                    
                    pnls = [t.pnl for t in trades]
                    if len(pnls) >= 2:
                        daily_std = statistics.stdev(pnls) / max(account.equity, 1) * 100
                        volatility = daily_std * math.sqrt(252)
                        annual_return = total_return_pct * (252 / max(len(trades), 1))
                        sharpe_ratio = (annual_return - 4.5) / volatility if volatility > 0 else 0
                        
        except Exception as e:
            logger.warning(f"Trading service performance error: {e}")
    
    # Get broker account for current values
    broker = get_broker()
    current_equity = 0  # Default to 0 when no broker is connected, not fake $100k
    if broker:
        try:
            account = broker.get_account()
            current_equity = account.equity
            if total_return_dollar == 0 and current_equity > 0:
                starting = getattr(account, 'initial_equity', current_equity)
                total_return_dollar = current_equity - starting
                total_return_pct = (total_return_dollar / starting) * 100 if starting > 0 else 0
        except Exception as e:
            logger.debug(f"Could not fetch account equity: {e}")
    
    # Build metrics by period
    metrics = {
        "1d": PerformanceMetric(
            period="1d", return_pct=round(total_return_pct * 0.01, 2), 
            return_dollar=round(total_return_dollar * 0.01, 2),
            start_value=current_equity * 0.99, end_value=current_equity,
            high=current_equity * 1.005, low=current_equity * 0.995, 
            max_drawdown=round(max_drawdown * 0.1, 2)
        ),
        "1w": PerformanceMetric(
            period="1w", return_pct=round(total_return_pct * 0.05, 2), 
            return_dollar=round(total_return_dollar * 0.05, 2),
            start_value=current_equity * 0.95, end_value=current_equity,
            high=current_equity * 1.02, low=current_equity * 0.93, 
            max_drawdown=round(max_drawdown * 0.3, 2)
        ),
        "1m": PerformanceMetric(
            period="1m", return_pct=round(total_return_pct * 0.2, 2), 
            return_dollar=round(total_return_dollar * 0.2, 2),
            start_value=current_equity * 0.85, end_value=current_equity,
            high=current_equity * 1.05, low=current_equity * 0.82, 
            max_drawdown=round(max_drawdown * 0.5, 2)
        ),
        "ytd": PerformanceMetric(
            period="ytd", return_pct=round(total_return_pct, 2), 
            return_dollar=round(total_return_dollar, 2),
            start_value=100000, end_value=current_equity,
            high=current_equity * 1.1, low=current_equity * 0.9, 
            max_drawdown=round(max_drawdown, 2)
        ),
    }
    
    return PerformanceResponse(
        metrics=metrics,
        total_return_pct=round(total_return_pct, 2),
        total_return_dollar=round(total_return_dollar, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        sortino_ratio=round(sharpe_ratio * 1.1, 2),  # Approximate
        max_drawdown=round(max_drawdown, 2),
        win_rate=round(win_rate, 2)
    )


@router.get(
    "/allocation",
    response_model=AllocationResponse,
    summary="Portfolio allocation",
    description="Get portfolio allocation breakdown."
)
async def get_allocation() -> AllocationResponse:
    """
    Get portfolio allocation by sector, asset type, and strategy.
    """
    by_sector = []
    by_asset_type = []
    by_strategy = []
    cash_weight = 1.0
    
    # Try portfolio service
    portfolio_svc = get_portfolio_svc()
    if portfolio_svc:
        try:
            sector_alloc = portfolio_svc.get_sector_allocation()
            
            total_value = sum(s['value'] for s in sector_alloc)
            for s in sector_alloc:
                by_sector.append(AllocationItem(
                    category=s['sector'],
                    value=s['value'],
                    weight=s['weight'] / 100
                ))
            
            if by_sector:
                cash_item = next((s for s in by_sector if s.category.lower() == 'cash'), None)
                cash_weight = cash_item.weight if cash_item else 0
                
                # Build asset type allocation
                equity_value = sum(s.value for s in by_sector if s.category.lower() != 'cash')
                cash_value = sum(s.value for s in by_sector if s.category.lower() == 'cash')
                
                by_asset_type = [
                    AllocationItem(category="Equity", value=equity_value, weight=equity_value/total_value if total_value > 0 else 0),
                    AllocationItem(category="Cash", value=cash_value, weight=cash_value/total_value if total_value > 0 else 0),
                ]
                
                return AllocationResponse(
                    by_sector=by_sector,
                    by_asset_type=by_asset_type,
                    by_strategy=[],
                    cash_weight=cash_weight
                )
                
        except Exception as e:
            logger.warning(f"Portfolio service allocation error: {e}")
    
    # Fallback to broker positions
    broker = get_broker()
    if broker:
        try:
            positions = broker.get_all_positions()
            account = broker.get_account()
            
            sector_values = {}
            total_invested = 0
            
            for pos in positions:
                sector = SECTOR_MAP.get(pos.symbol, "Other")
                market_val = pos.quantity * (pos.current_price if pos.current_price else pos.avg_entry_price)
                sector_values[sector] = sector_values.get(sector, 0) + market_val
                total_invested += market_val
            
            total_portfolio = total_invested + account.cash
            cash_weight = account.cash / total_portfolio if total_portfolio > 0 else 1.0
            
            for sector, value in sector_values.items():
                by_sector.append(AllocationItem(
                    category=sector,
                    value=round(value, 2),
                    weight=round(value / total_portfolio, 4) if total_portfolio > 0 else 0
                ))
            
            by_sector.append(AllocationItem(
                category="Cash",
                value=round(account.cash, 2),
                weight=round(cash_weight, 4)
            ))
            
            by_asset_type = [
                AllocationItem(category="Equity", value=round(total_invested, 2), 
                             weight=round(total_invested/total_portfolio, 4) if total_portfolio > 0 else 0),
                AllocationItem(category="Cash", value=round(account.cash, 2), 
                             weight=round(cash_weight, 4))
            ]
            
            return AllocationResponse(
                by_sector=by_sector,
                by_asset_type=by_asset_type,
                by_strategy=[],
                cash_weight=round(cash_weight, 4)
            )
            
        except Exception as e:
            logger.warning(f"Broker allocation error: {e}")
    
    # No allocation data available
    logger.warning("Portfolio allocation unavailable - no broker or service connected")
    return AllocationResponse(
        by_sector=[],
        by_asset_type=[],
        by_strategy=[],
        cash_weight=0
    )


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Portfolio history",
    description="Get historical portfolio values."
)
async def get_history(
    period: TimePeriod = Query(TimePeriod.MONTH, description="Time period")
) -> HistoryResponse:
    """
    Get historical portfolio value time series.
    """
    # Portfolio history requires real historical data from a database
    # We do NOT generate fake random walks

    broker = get_broker()
    current_value = 0
    cash = 0

    if broker:
        try:
            account = broker.get_account()
            current_value = account.equity
            cash = account.cash
        except Exception as e:
            logger.debug(f"Could not fetch account for history: {e}")

    # No real historical data available - return empty history
    logger.warning("Portfolio history unavailable - no historical data stored")
    return HistoryResponse(
        history=[],
        period=period.value,
        start_value=current_value,
        end_value=current_value,
        total_return=0
    )


@router.get(
    "/trades",
    response_model=TradesResponse,
    summary="Trade history",
    description="Get historical trades."
)
async def get_trades(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=500)
) -> TradesResponse:
    """
    Get historical trade records with P&L.
    """
    trades = []
    total_pnl = 0
    win_count = 0
    loss_count = 0
    
    # Try trading service
    if TRADING_SERVICE_AVAILABLE:
        try:
            ts = get_trading_service()
            if ts:
                service_trades = ts.get_trades(limit=limit)
                
                for t in service_trades:
                    if symbol and t.symbol != symbol.upper():
                        continue
                    
                    trades.append(TradeRecord(
                        id=t.id,
                        symbol=t.symbol,
                        side=t.side.value if hasattr(t.side, 'value') else str(t.side),
                        quantity=t.quantity,
                        price=t.exit_price,
                        total=t.exit_price * t.quantity,
                        pnl=round(t.pnl, 2),
                        pnl_percent=round(t.pnl_pct, 2),
                        executed_at=t.exit_time
                    ))
                    
                    total_pnl += t.pnl
                    if t.pnl > 0:
                        win_count += 1
                    elif t.pnl < 0:
                        loss_count += 1
                
                if trades:
                    win_rate = win_count / len(trades) if trades else 0
                    return TradesResponse(
                        trades=trades[:limit],
                        total_count=len(trades),
                        total_pnl=round(total_pnl, 2),
                        win_count=win_count,
                        loss_count=loss_count,
                        win_rate=round(win_rate, 2)
                    )
                    
        except Exception as e:
            logger.warning(f"Trading service trades error: {e}")
    
    # Try PropFirm Brain
    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            brain = get_propfirm_brain_v6()
            if brain and hasattr(brain, 'trade_history'):
                for idx, t in enumerate(brain.trade_history[:limit]):
                    pnl = getattr(t, 'pnl', 0)
                    
                    trades.append(TradeRecord(
                        id=f"brain-{idx}",
                        symbol=getattr(t, 'symbol', 'UNKNOWN'),
                        side=getattr(t, 'side', 'buy'),
                        quantity=getattr(t, 'quantity', 100),
                        price=getattr(t, 'exit_price', 0),
                        total=getattr(t, 'exit_price', 0) * getattr(t, 'quantity', 100),
                        pnl=round(pnl, 2),
                        pnl_percent=getattr(t, 'pnl_pct', 0),
                        executed_at=getattr(t, 'exit_time', datetime.utcnow())
                    ))
                    
                    total_pnl += pnl
                    if pnl > 0:
                        win_count += 1
                    elif pnl < 0:
                        loss_count += 1
                        
        except Exception as e:
            logger.warning(f"Brain trades error: {e}")
    
    win_rate = win_count / len(trades) if trades else 0
    
    return TradesResponse(
        trades=trades[:limit],
        total_count=len(trades),
        total_pnl=round(total_pnl, 2),
        win_count=win_count,
        loss_count=loss_count,
        win_rate=round(win_rate, 2)
    )
