"""
QUANT INDUSTRY V1 - Market Data API (v2)
========================================
Consolidated market data endpoints: quotes, bars, indicators, sectors, movers.

WIRED TO REAL IMPLEMENTATIONS:
- MarketDataService (Alpaca provider)
- Market Hours service
- Technical indicators from indicators.technical
"""

from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date, timedelta
from enum import Enum
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Service imports and singletons
# ============================================================================

_market_data_service = None
_market_hours_available = False

# Try to import services
try:
    from backend.services.market_data_service import MarketDataService, get_market_data_service
    _service_available = True
except ImportError:
    try:
        # Alternate import path
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from backend.services.market_data_service import MarketDataService, get_market_data_service
        _service_available = True
    except ImportError:
        _service_available = False
        logger.warning("MarketDataService not available")

try:
    from backend.services.market_hours import get_market_status as _get_market_hours_status, MarketSession as HoursSession
    _market_hours_available = True
except ImportError:
    try:
        from services.market_hours import get_market_status as _get_market_hours_status, MarketSession as HoursSession
        _market_hours_available = True
    except ImportError:
        _market_hours_available = False
        logger.warning("Market hours service not available")

# Technical indicators
try:
    from backend.indicators.technical import calculate_rsi, calculate_sma, calculate_ema, calculate_macd, calculate_bollinger_bands, calculate_atr
    _indicators_available = True
except ImportError:
    try:
        from indicators.technical import calculate_rsi, calculate_sma, calculate_ema, calculate_macd, calculate_bollinger_bands, calculate_atr
        _indicators_available = True
    except ImportError:
        _indicators_available = False
        logger.warning("Technical indicators not available")


async def _get_service() -> Optional["MarketDataService"]:
    """Get or create the market data service singleton."""
    global _market_data_service
    if _market_data_service is None and _service_available:
        try:
            _market_data_service = await get_market_data_service()
        except Exception as e:
            logger.error(f"Failed to get market data service: {e}")
    return _market_data_service


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

# Map v2 timeframes to Alpaca timeframes
TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "30m": "30Min",
    "1h": "1Hour",
    "4h": "4Hour",
    "1d": "1Day",
    "1w": "1Week",
}


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
    source: str = Field(default="unknown", description="Data source")


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
    source: str = Field(default="unknown")


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
    source: str = Field(default="unknown")


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
    source: str = Field(default="unknown")


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
    source: str = Field(default="unknown")


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
    if _market_hours_available:
        try:
            status = _get_market_hours_status()
            
            # Map session types
            session_map = {
                "regular": MarketSession.REGULAR,
                "pre_market": MarketSession.PRE,
                "after_hours": MarketSession.POST,
                "closed": MarketSession.CLOSED,
            }
            session = session_map.get(status.get("session", "closed"), MarketSession.CLOSED)
            
            return MarketStatus(
                session=session,
                is_open=status.get("is_open", False),
                next_close=None,  # Would need parsing from status string
                early_close=status.get("is_early_close", False)
            )
        except Exception as e:
            logger.warning(f"Market hours failed: {e}")
    
    # Fallback
    from datetime import datetime
    import pytz
    try:
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)
    except:
        now = datetime.now()
    
    hour = now.hour
    weekday = now.weekday()
    
    if weekday >= 5:
        session = MarketSession.CLOSED
        is_open = False
    elif 9 <= hour < 16:
        session = MarketSession.REGULAR
        is_open = True
    elif 4 <= hour < 9:
        session = MarketSession.PRE
        is_open = False
    elif 16 <= hour < 20:
        session = MarketSession.POST
        is_open = False
    else:
        session = MarketSession.CLOSED
        is_open = False
    
    return MarketStatus(
        session=session,
        is_open=is_open,
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
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:100]
    
    service = await _get_service()
    if service:
        try:
            quote_data = await service.get_quotes(symbol_list)
            quotes = []
            for symbol in symbol_list:
                q = quote_data.get(symbol)
                if q:
                    # Calculate change from prev close if available
                    price = q.last or q.mid
                    # We don't have prev_close directly, estimate from snapshot or use 0
                    quotes.append(Quote(
                        symbol=symbol,
                        bid=q.bid or 0,
                        ask=q.ask or 0,
                        last=price,
                        volume=q.volume or 0,
                        change=0,  # Would need daily bar for accurate change
                        change_percent=0,
                        high=price,  # Would need daily bar
                        low=price,
                        open=price,
                        prev_close=price,
                        source=q.source
                    ))
            return QuotesResponse(quotes=quotes)
        except Exception as e:
            logger.warning(f"Quote fetch failed: {e}")
    
    # Fallback mock
    quotes = []
    for symbol in symbol_list:
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
            prev_close=98.52,
            source="fallback"
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
    symbol = symbol.upper()
    
    service = await _get_service()
    if service:
        try:
            # Get quote
            q = await service.get_quote(symbol)
            
            # Validate data quality - check for suspicious bid/ask spread
            price = q.last or q.mid
            if q.bid and q.ask and price:
                spread_pct = abs(q.ask - q.bid) / price * 100
                if spread_pct > 3:  # More than 3% spread is suspicious
                    logger.warning(f"Suspicious spread for {symbol}: {spread_pct:.1f}% - falling back to yfinance")
                    raise ValueError(f"Bad data quality: spread={spread_pct:.1f}%")
            
            # Get snapshot for daily data (prev close, change, etc.)
            snapshot = await service.get_snapshot(symbol)
            
            daily_bar = snapshot.get("daily_bar", {})
            prev_bar = snapshot.get("prev_daily_bar", {})
            
            prev_close = prev_bar.get("c", price) if prev_bar else price
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            
            return Quote(
                symbol=symbol,
                bid=q.bid or 0,
                ask=q.ask or 0,
                last=price,
                volume=q.volume or daily_bar.get("v", 0),
                change=round(change, 2),
                change_percent=round(change_pct, 2),
                high=daily_bar.get("h", price),
                low=daily_bar.get("l", price),
                open=daily_bar.get("o", price),
                prev_close=prev_close,
                source=q.source
            )
        except Exception as e:
            logger.warning(f"Quote fetch failed for {symbol}: {e}")
    
    # Fallback to yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose', 0)
        prev_close = info.get('previousClose', price)
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return Quote(
            symbol=symbol,
            bid=info.get('bid', price * 0.999),
            ask=info.get('ask', price * 1.001),
            last=price,
            volume=info.get('volume', 0),
            change=round(change, 2),
            change_percent=round(change_pct, 2),
            high=info.get('dayHigh', price),
            low=info.get('dayLow', price),
            open=info.get('open', price),
            prev_close=prev_close,
            source="yfinance"
        )
    except Exception as yf_error:
        logger.warning(f"yfinance fallback failed for {symbol}: {yf_error}")
    
    # Last resort fallback
    return Quote(
        symbol=symbol,
        bid=0,
        ask=0,
        last=0,
        volume=0,
        change=0,
        change_percent=0,
        high=0,
        low=0,
        open=0,
        prev_close=0,
        source="unavailable"
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
    symbol = symbol.upper()
    alpaca_tf = TIMEFRAME_MAP.get(timeframe.value, "1Day")
    
    # Calculate date range
    end_dt = datetime.combine(end, datetime.max.time()) if end else datetime.now()
    if start:
        start_dt = datetime.combine(start, datetime.min.time())
    else:
        # Default based on timeframe
        days = 30 if "Min" in alpaca_tf or "Hour" in alpaca_tf else 365
        start_dt = end_dt - timedelta(days=days)
    
    service = await _get_service()
    if service:
        try:
            bar_data = await service.get_bars(
                symbol=symbol,
                timeframe=alpaca_tf,
                start=start_dt,
                end=end_dt,
                limit=limit
            )
            
            bars = [
                Bar(
                    timestamp=b.timestamp,
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=int(b.volume),
                    vwap=b.vwap
                )
                for b in bar_data[-limit:]
            ]
            
            return BarsResponse(
                symbol=symbol,
                timeframe=timeframe.value,
                bars=bars,
                count=len(bars),
                source="alpaca" if bars else "none"
            )
        except Exception as e:
            logger.warning(f"Bars fetch failed for {symbol}: {e}")
    
    # Fallback mock
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
        symbol=symbol,
        timeframe=timeframe.value,
        bars=bars,
        count=len(bars),
        source="fallback"
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
    symbol = symbol.upper()
    alpaca_tf = TIMEFRAME_MAP.get(timeframe.value, "1Day")
    
    service = await _get_service()
    if service and _indicators_available:
        try:
            # Get enough bars for 200 SMA
            bars = await service.get_bars(
                symbol=symbol,
                timeframe=alpaca_tf,
                days=400,
                limit=400
            )
            
            if len(bars) >= 20:
                closes = [b.close for b in bars]
                highs = [b.high for b in bars]
                lows = [b.low for b in bars]
                
                import numpy as np
                
                # Calculate indicators
                sma_20 = calculate_sma(closes, 20)
                sma_50 = calculate_sma(closes, 50) if len(closes) >= 50 else [np.nan] * len(closes)
                sma_200 = calculate_sma(closes, 200) if len(closes) >= 200 else [np.nan] * len(closes)
                ema_12 = calculate_ema(closes, 12)
                ema_26 = calculate_ema(closes, 26) if len(closes) >= 26 else [np.nan] * len(closes)
                rsi = calculate_rsi(closes, 14)
                macd_line, signal, histogram = calculate_macd(closes)
                upper, middle, lower = calculate_bollinger_bands(closes, 20, 2)
                atr = calculate_atr(highs, lows, closes, 14)
                
                # Get latest values
                def safe_get(arr, default=None):
                    if arr is not None and len(arr) > 0 and not np.isnan(arr[-1]):
                        return float(arr[-1])
                    return default
                
                # VWAP from latest bar if available
                vwap = bars[-1].vwap if bars else None
                
                return TechnicalIndicators(
                    symbol=symbol,
                    sma_20=safe_get(sma_20),
                    sma_50=safe_get(sma_50),
                    sma_200=safe_get(sma_200),
                    ema_12=safe_get(ema_12),
                    ema_26=safe_get(ema_26),
                    rsi_14=safe_get(rsi),
                    macd=safe_get(macd_line),
                    macd_signal=safe_get(signal),
                    macd_histogram=safe_get(histogram),
                    bollinger_upper=safe_get(upper),
                    bollinger_middle=safe_get(middle),
                    bollinger_lower=safe_get(lower),
                    atr_14=safe_get(atr),
                    vwap=vwap,
                    source="calculated"
                )
        except Exception as e:
            logger.warning(f"Indicators calc failed for {symbol}: {e}")
    
    # Fallback
    return TechnicalIndicators(
        symbol=symbol,
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
        vwap=150.25,
        source="fallback"
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
    # Sector ETFs to track
    sector_etfs = {
        "XLK": "Technology",
        "XLV": "Healthcare", 
        "XLF": "Financial",
        "XLY": "Consumer Discretionary",
        "XLC": "Communication Services",
        "XLI": "Industrials",
        "XLP": "Consumer Staples",
        "XLE": "Energy",
        "XLU": "Utilities",
        "XLRE": "Real Estate",
        "XLB": "Materials",
    }
    
    service = await _get_service()
    if service:
        try:
            quotes = await service.get_quotes(list(sector_etfs.keys()))
            
            sectors = []
            for etf, sector_name in sector_etfs.items():
                q = quotes.get(etf)
                if q:
                    # Get snapshot for change data
                    try:
                        snapshot = await service.get_snapshot(etf)
                        daily = snapshot.get("daily_bar", {})
                        prev = snapshot.get("prev_daily_bar", {})
                        
                        price = q.last or q.mid
                        prev_close = prev.get("c", price) if prev else price
                        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
                        volume = daily.get("v", q.volume) or 0
                    except:
                        change_pct = 0
                        volume = q.volume or 0
                    
                    sectors.append(SectorPerformance(
                        sector=sector_name,
                        change_percent=round(change_pct, 2),
                        volume=int(volume),
                        market_cap=0,  # Would need separate lookup
                        top_gainer="",
                        top_loser=""
                    ))
            
            if sectors:
                return SectorsResponse(sectors=sectors, source="alpaca")
        except Exception as e:
            logger.warning(f"Sector fetch failed: {e}")
    
    # Fallback
    sectors = [
        SectorPerformance(
            sector="Technology", change_percent=1.25, volume=500000000,
            market_cap=15000000000000, top_gainer="NVDA", top_loser="INTC"
        ),
        SectorPerformance(
            sector="Healthcare", change_percent=-0.50, volume=200000000,
            market_cap=5000000000000, top_gainer="LLY", top_loser="PFE"
        ),
        SectorPerformance(
            sector="Financial", change_percent=0.75, volume=300000000,
            market_cap=8000000000000, top_gainer="JPM", top_loser="WFC"
        ),
    ]
    
    return SectorsResponse(sectors=sectors, source="fallback")


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
    
    Note: Alpaca doesn't have a direct movers endpoint, so we scan a universe of stocks.
    """
    # Universe of stocks to scan for movers
    universe = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
        "NFLX", "CRM", "ORCL", "ADBE", "INTC", "CSCO", "IBM", "QCOM",
        "JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA",
        "JNJ", "UNH", "PFE", "MRK", "ABBV", "LLY", "TMO", "ABT",
        "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "OXY", "VLO",
        "HD", "LOW", "TGT", "WMT", "COST", "NKE", "SBUX", "MCD"
    ]
    
    service = await _get_service()
    if service:
        try:
            # Get quotes for universe
            quotes = await service.get_quotes(universe)
            
            # Calculate changes and sort
            stock_data = []
            for symbol in universe:
                q = quotes.get(symbol)
                if q:
                    try:
                        snapshot = await service.get_snapshot(symbol)
                        daily = snapshot.get("daily_bar", {})
                        prev = snapshot.get("prev_daily_bar", {})
                        
                        price = q.last or q.mid
                        prev_close = prev.get("c", price) if prev else price
                        change = price - prev_close
                        change_pct = (change / prev_close * 100) if prev_close else 0
                        volume = daily.get("v", q.volume) or 0
                        
                        stock_data.append({
                            "symbol": symbol,
                            "name": symbol,  # Would need company name lookup
                            "price": price,
                            "change": change,
                            "change_pct": change_pct,
                            "volume": int(volume),
                        })
                    except:
                        continue
            
            # Sort for gainers/losers/volume
            gainers = sorted(stock_data, key=lambda x: x["change_pct"], reverse=True)[:limit]
            losers = sorted(stock_data, key=lambda x: x["change_pct"])[:limit]
            most_active = sorted(stock_data, key=lambda x: x["volume"], reverse=True)[:limit]
            
            def to_mover(d):
                return Mover(
                    symbol=d["symbol"],
                    name=d["name"],
                    price=round(d["price"], 2),
                    change=round(d["change"], 2),
                    change_percent=round(d["change_pct"], 2),
                    volume=d["volume"],
                    avg_volume=d["volume"],  # Would need historical avg
                    volume_ratio=1.0
                )
            
            return MoversResponse(
                gainers=[to_mover(d) for d in gainers],
                losers=[to_mover(d) for d in losers],
                most_active=[to_mover(d) for d in most_active],
                source="alpaca"
            )
        except Exception as e:
            logger.warning(f"Movers fetch failed: {e}")
    
    # Fallback
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
        most_active=most_active[:limit],
        source="fallback"
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
