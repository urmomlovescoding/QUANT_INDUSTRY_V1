"""
QUANT INDUSTRY V1 - Market Data API (v2)
========================================
Consolidated market data endpoints: quotes, bars, indicators, sectors, movers.
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

class Timeframe(str, Enum):
    """Bar timeframe options."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class MarketSession(str, Enum):
    """Market session types."""
    PRE = "pre"
    REGULAR = "regular"
    POST = "post"
    CLOSED = "closed"


# ============================================================================
# Pydantic Models
# ============================================================================

class MarketStatus(BaseModel):
    """Market hours and status."""
    session: MarketSession = Field(..., description="Current market session")
    is_open: bool = Field(..., description="Whether market is currently open")
    next_open: Optional[datetime] = Field(None, description="Next market open time")
    next_close: Optional[datetime] = Field(None, description="Next market close time")
    early_close: bool = Field(False, description="Whether today is an early close day")


class Quote(BaseModel):
    """Real-time quote data."""
    symbol: str = Field(..., description="Ticker symbol")
    bid: float = Field(..., description="Current bid price")
    ask: float = Field(..., description="Current ask price")
    last: float = Field(..., description="Last trade price")
    volume: int = Field(..., description="Today's volume")
    change: float = Field(..., description="Price change from previous close")
    change_percent: float = Field(..., description="Percentage change")
    high: float = Field(..., description="Today's high")
    low: float = Field(..., description="Today's low")
    open: float = Field(..., description="Today's open")
    prev_close: float = Field(..., description="Previous close")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QuotesResponse(BaseModel):
    """Batch quotes response."""
    quotes: list[Quote] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Bar(BaseModel):
    """OHLCV bar data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None


class BarsResponse(BaseModel):
    """Historical bars response."""
    symbol: str
    timeframe: str
    bars: list[Bar] = Field(default_factory=list)
    count: int = Field(..., description="Number of bars returned")


class TechnicalIndicators(BaseModel):
    """Technical indicator values."""
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    atr_14: Optional[float] = None
    adx_14: Optional[float] = None
    obv: Optional[float] = None
    vwap: Optional[float] = None


class SectorPerformance(BaseModel):
    """Sector performance data."""
    sector: str
    change_percent: float
    volume: int
    market_cap: float
    top_gainer: str
    top_loser: str


class SectorsResponse(BaseModel):
    """Sector performance response."""
    sectors: list[SectorPerformance] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Mover(BaseModel):
    """Market mover data."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    avg_volume: int
    volume_ratio: float


class MoversResponse(BaseModel):
    """Market movers response."""
    gainers: list[Mover] = Field(default_factory=list)
    losers: list[Mover] = Field(default_factory=list)
    most_active: list[Mover] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Snapshot(BaseModel):
    """Full market snapshot for a symbol."""
    symbol: str
    quote: Quote
    indicators: TechnicalIndicators
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/status",
    response_model=MarketStatus,
    summary="Market status",
    description="Get current market session and trading hours."
)
async def get_market_status() -> MarketStatus:
    """
    Get current market status including session type and hours.
    
    Returns information about:
    - Current session (pre, regular, post, closed)
    - Next open/close times
    - Early close indicators
    """
    return MarketStatus(
        session=MarketSession.REGULAR,
        is_open=True,
        next_close=datetime(2025, 1, 13, 21, 0, 0),  # 4 PM EST
        early_close=False
    )


@router.get(
    "/quotes",
    response_model=QuotesResponse,
    summary="Batch quotes",
    description="Get real-time quotes for multiple symbols."
)
async def get_quotes(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., SPY,QQQ,AAPL)")
) -> QuotesResponse:
    """
    Get real-time quotes for multiple symbols.
    
    Supports up to 100 symbols per request.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    
    # Mock data
    quotes = []
    for symbol in symbol_list[:100]:
        quotes.append(Quote(
            symbol=symbol,
            bid=100.00,
            ask=100.05,
            last=100.02,
            volume=1000000,
            change=1.50,
            change_percent=1.52,
            high=101.00,
            low=98.50,
            open=99.00,
            prev_close=98.52
        ))
    
    return QuotesResponse(quotes=quotes)


@router.get(
    "/quotes/{symbol}",
    response_model=Quote,
    summary="Single quote",
    description="Get real-time quote for a single symbol."
)
async def get_quote(
    symbol: str = Path(..., description="Ticker symbol (e.g., AAPL)")
) -> Quote:
    """
    Get real-time quote for a single symbol.
    
    Returns bid, ask, last, volume, and change data.
    """
    return Quote(
        symbol=symbol.upper(),
        bid=150.00,
        ask=150.05,
        last=150.02,
        volume=50000000,
        change=2.50,
        change_percent=1.69,
        high=152.00,
        low=148.00,
        open=149.00,
        prev_close=147.52
    )


@router.get(
    "/bars/{symbol}",
    response_model=BarsResponse,
    summary="Historical bars",
    description="Get OHLCV bar data for a symbol."
)
async def get_bars(
    symbol: str = Path(..., description="Ticker symbol"),
    timeframe: Timeframe = Query(Timeframe.D1, description="Bar timeframe"),
    start: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum bars to return")
) -> BarsResponse:
    """
    Get historical OHLCV bars for a symbol.
    
    Supports multiple timeframes from 1-minute to weekly.
    """
    # Mock data
    bars = [
        Bar(
            timestamp=datetime(2025, 1, 10, 9, 30),
            open=100.0, high=101.0, low=99.5, close=100.5,
            volume=1000000, vwap=100.25
        ),
        Bar(
            timestamp=datetime(2025, 1, 9, 9, 30),
            open=99.0, high=100.5, low=98.5, close=100.0,
            volume=1200000, vwap=99.5
        ),
    ]
    
    return BarsResponse(
        symbol=symbol.upper(),
        timeframe=timeframe.value,
        bars=bars,
        count=len(bars)
    )


@router.get(
    "/indicators/{symbol}",
    response_model=TechnicalIndicators,
    summary="Technical indicators",
    description="Get calculated technical indicators for a symbol."
)
async def get_indicators(
    symbol: str = Path(..., description="Ticker symbol"),
    timeframe: Timeframe = Query(Timeframe.D1, description="Timeframe for indicator calculation")
) -> TechnicalIndicators:
    """
    Get technical indicators for a symbol.
    
    Includes moving averages, RSI, MACD, Bollinger Bands, and more.
    """
    return TechnicalIndicators(
        symbol=symbol.upper(),
        sma_20=150.50,
        sma_50=148.25,
        sma_200=142.00,
        ema_12=151.00,
        ema_26=149.50,
        rsi_14=58.5,
        macd=1.50,
        macd_signal=1.25,
        macd_histogram=0.25,
        bollinger_upper=155.00,
        bollinger_middle=150.00,
        bollinger_lower=145.00,
        atr_14=2.50,
        adx_14=25.0,
        obv=50000000.0,
        vwap=150.25
    )


@router.get(
    "/sectors",
    response_model=SectorsResponse,
    summary="Sector performance",
    description="Get performance data for market sectors."
)
async def get_sectors() -> SectorsResponse:
    """
    Get sector performance summary.
    
    Returns change percentages, volumes, and top movers by sector.
    """
    sectors = [
        SectorPerformance(
            sector="Technology",
            change_percent=1.25,
            volume=500000000,
            market_cap=15000000000000,
            top_gainer="NVDA",
            top_loser="INTC"
        ),
        SectorPerformance(
            sector="Healthcare",
            change_percent=-0.50,
            volume=200000000,
            market_cap=5000000000000,
            top_gainer="LLY",
            top_loser="PFE"
        ),
        SectorPerformance(
            sector="Financial",
            change_percent=0.75,
            volume=300000000,
            market_cap=8000000000000,
            top_gainer="JPM",
            top_loser="WFC"
        ),
    ]
    
    return SectorsResponse(sectors=sectors)


@router.get(
    "/movers",
    response_model=MoversResponse,
    summary="Market movers",
    description="Get top gainers, losers, and most active stocks."
)
async def get_movers(
    limit: int = Query(10, ge=1, le=50, description="Number of movers per category")
) -> MoversResponse:
    """
    Get market movers.
    
    Returns top gainers, losers, and most actively traded stocks.
    """
    gainers = [
        Mover(
            symbol="NVDA", name="NVIDIA Corp", price=875.50,
            change=45.00, change_percent=5.42,
            volume=80000000, avg_volume=50000000, volume_ratio=1.6
        ),
    ]
    
    losers = [
        Mover(
            symbol="BA", name="Boeing Co", price=175.25,
            change=-8.50, change_percent=-4.63,
            volume=25000000, avg_volume=15000000, volume_ratio=1.67
        ),
    ]
    
    most_active = [
        Mover(
            symbol="TSLA", name="Tesla Inc", price=245.00,
            change=5.00, change_percent=2.08,
            volume=150000000, avg_volume=100000000, volume_ratio=1.5
        ),
    ]
    
    return MoversResponse(
        gainers=gainers[:limit],
        losers=losers[:limit],
        most_active=most_active[:limit]
    )


@router.get(
    "/snapshot/{symbol}",
    response_model=Snapshot,
    summary="Full snapshot",
    description="Get complete market snapshot including quote and indicators."
)
async def get_snapshot(
    symbol: str = Path(..., description="Ticker symbol")
) -> Snapshot:
    """
    Get full market snapshot for a symbol.
    
    Combines real-time quote with technical indicators in a single call.
    """
    quote = await get_quote(symbol)
    indicators = await get_indicators(symbol)
    
    return Snapshot(
        symbol=symbol.upper(),
        quote=quote,
        indicators=indicators
    )
