"""
QUANT INDUSTRY V1 - Portfolio API (v2)
======================================
Portfolio management: holdings, performance, allocation.
"""

from fastapi import APIRouter, Query, Path
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum

router = APIRouter()


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
    holdings = [
        Holding(
            symbol="AAPL",
            name="Apple Inc",
            quantity=100,
            avg_cost=149.50,
            current_price=152.00,
            market_value=15200.00,
            cost_basis=14950.00,
            unrealized_pnl=250.00,
            unrealized_pnl_percent=1.67,
            weight=0.25,
            sector="Technology"
        ),
        Holding(
            symbol="NVDA",
            name="NVIDIA Corporation",
            quantity=25,
            avg_cost=850.00,
            current_price=875.00,
            market_value=21875.00,
            cost_basis=21250.00,
            unrealized_pnl=625.00,
            unrealized_pnl_percent=2.94,
            weight=0.35,
            sector="Technology"
        ),
        Holding(
            symbol="JPM",
            name="JPMorgan Chase & Co",
            quantity=50,
            avg_cost=195.00,
            current_price=198.00,
            market_value=9900.00,
            cost_basis=9750.00,
            unrealized_pnl=150.00,
            unrealized_pnl_percent=1.54,
            weight=0.16,
            sector="Financial"
        ),
    ]
    
    total_value = sum(h.market_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    total_pnl = sum(h.unrealized_pnl for h in holdings)
    cash = 15000.00
    
    return HoldingsResponse(
        holdings=holdings,
        total_value=total_value + cash,
        total_cost=total_cost,
        total_unrealized_pnl=total_pnl,
        total_unrealized_pnl_percent=(total_pnl / total_cost) * 100 if total_cost > 0 else 0,
        cash=cash
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
    metrics = {
        "1d": PerformanceMetric(
            period="1d", return_pct=0.85, return_dollar=520.00,
            start_value=61155.00, end_value=61675.00,
            high=61800.00, low=61000.00, max_drawdown=-0.5
        ),
        "1w": PerformanceMetric(
            period="1w", return_pct=2.15, return_dollar=1300.00,
            start_value=60375.00, end_value=61675.00,
            high=62000.00, low=59500.00, max_drawdown=-1.5
        ),
        "1m": PerformanceMetric(
            period="1m", return_pct=5.25, return_dollar=3075.00,
            start_value=58600.00, end_value=61675.00,
            high=62000.00, low=57000.00, max_drawdown=-2.8
        ),
        "ytd": PerformanceMetric(
            period="ytd", return_pct=3.15, return_dollar=1885.00,
            start_value=59790.00, end_value=61675.00,
            high=62000.00, low=58000.00, max_drawdown=-3.0
        ),
    }
    
    return PerformanceResponse(
        metrics=metrics,
        total_return_pct=15.5,
        total_return_dollar=8250.00,
        sharpe_ratio=1.85,
        sortino_ratio=2.15,
        max_drawdown=-8.5,
        win_rate=0.62
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
    by_sector = [
        AllocationItem(category="Technology", value=37075.00, weight=0.60, target_weight=0.50, drift=0.10),
        AllocationItem(category="Financial", value=9900.00, weight=0.16, target_weight=0.20, drift=-0.04),
        AllocationItem(category="Cash", value=15000.00, weight=0.24, target_weight=0.30, drift=-0.06),
    ]
    
    by_asset_type = [
        AllocationItem(category="Equity", value=46975.00, weight=0.76),
        AllocationItem(category="Cash", value=15000.00, weight=0.24),
    ]
    
    by_strategy = [
        AllocationItem(category="Momentum", value=21875.00, weight=0.35),
        AllocationItem(category="Value", value=15200.00, weight=0.25),
        AllocationItem(category="Quality", value=9900.00, weight=0.16),
        AllocationItem(category="Cash", value=15000.00, weight=0.24),
    ]
    
    return AllocationResponse(
        by_sector=by_sector,
        by_asset_type=by_asset_type,
        by_strategy=by_strategy,
        cash_weight=0.24
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
    history = [
        HistoryPoint(date=date(2025, 1, 10), value=61675.00, cash=15000.00, invested=46675.00, daily_return=0.85),
        HistoryPoint(date=date(2025, 1, 9), value=61155.00, cash=15000.00, invested=46155.00, daily_return=0.45),
        HistoryPoint(date=date(2025, 1, 8), value=60880.00, cash=15000.00, invested=45880.00, daily_return=-0.25),
        HistoryPoint(date=date(2025, 1, 7), value=61033.00, cash=15000.00, invested=46033.00, daily_return=1.20),
    ]
    
    return HistoryResponse(
        history=history,
        period=period.value,
        start_value=60300.00,
        end_value=61675.00,
        total_return=2.28
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
    trades = [
        TradeRecord(
            id="trade-001",
            symbol="AAPL",
            side="buy",
            quantity=100,
            price=149.50,
            total=14950.00,
            pnl=None,
            executed_at=datetime(2025, 1, 5, 10, 30)
        ),
        TradeRecord(
            id="trade-002",
            symbol="NVDA",
            side="buy",
            quantity=25,
            price=850.00,
            total=21250.00,
            pnl=None,
            executed_at=datetime(2025, 1, 3, 14, 15)
        ),
        TradeRecord(
            id="trade-003",
            symbol="MSFT",
            side="sell",
            quantity=50,
            price=405.00,
            total=20250.00,
            pnl=750.00,
            pnl_percent=3.85,
            executed_at=datetime(2025, 1, 2, 11, 45)
        ),
    ]
    
    return TradesResponse(
        trades=trades[:limit],
        total_count=len(trades),
        total_pnl=750.00,
        win_count=1,
        loss_count=0,
        win_rate=1.0
    )
