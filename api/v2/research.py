"""
QUANT INDUSTRY V1 - Research API (v2)
=====================================
Research data: news, 13F filings, earnings.
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

class NewsSentiment(str, Enum):
    """News sentiment classification."""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class EarningsSurprise(str, Enum):
    """Earnings surprise classification."""
    BEAT = "beat"
    MEET = "meet"
    MISS = "miss"


# ============================================================================
# Pydantic Models - News
# ============================================================================

class NewsArticle(BaseModel):
    """News article."""
    id: str
    title: str
    summary: str
    source: str
    url: str
    symbols: list[str] = Field(default_factory=list)
    sentiment: NewsSentiment
    sentiment_score: float = Field(..., ge=-1, le=1)
    relevance_score: float = Field(..., ge=0, le=1)
    published_at: datetime


class NewsResponse(BaseModel):
    """News response."""
    articles: list[NewsArticle] = Field(default_factory=list)
    total: int
    avg_sentiment: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Pydantic Models - 13F Filings
# ============================================================================

class HoldingChange(BaseModel):
    """Holding change from 13F."""
    symbol: str
    name: str
    shares: int
    value: float
    shares_change: int
    shares_change_percent: float
    is_new_position: bool
    is_closed_position: bool


class Filing13F(BaseModel):
    """13F filing."""
    filing_id: str
    filer_name: str
    filer_cik: str
    filing_date: date
    quarter_end: date
    total_value: float
    holdings_count: int
    new_positions: int
    closed_positions: int
    top_holdings: list[HoldingChange] = Field(default_factory=list)
    notable_changes: list[HoldingChange] = Field(default_factory=list)


class Filing13FResponse(BaseModel):
    """13F filings response."""
    filings: list[Filing13F] = Field(default_factory=list)
    total: int


class InstitutionalOwnership(BaseModel):
    """Institutional ownership for a symbol."""
    symbol: str
    total_institutional_shares: int
    institutional_ownership_percent: float
    num_institutions: int
    top_holders: list[dict] = Field(default_factory=list)
    recent_changes: list[HoldingChange] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Pydantic Models - Earnings
# ============================================================================

class EarningsReport(BaseModel):
    """Earnings report."""
    symbol: str
    company_name: str
    report_date: date
    fiscal_quarter: str
    fiscal_year: int
    eps_estimate: float
    eps_actual: Optional[float] = None
    eps_surprise: Optional[float] = None
    eps_surprise_percent: Optional[float] = None
    revenue_estimate: float
    revenue_actual: Optional[float] = None
    revenue_surprise: Optional[float] = None
    revenue_surprise_percent: Optional[float] = None
    surprise_classification: Optional[EarningsSurprise] = None
    guidance: Optional[str] = None
    report_time: str = Field(..., description="BMO (before market) or AMC (after market)")


class EarningsCalendarResponse(BaseModel):
    """Earnings calendar response."""
    earnings: list[EarningsReport] = Field(default_factory=list)
    total: int
    date_range_start: date
    date_range_end: date


class EarningsHistoryResponse(BaseModel):
    """Earnings history for a symbol."""
    symbol: str
    earnings: list[EarningsReport] = Field(default_factory=list)
    beat_rate: float
    avg_surprise_percent: float


# ============================================================================
# Pydantic Models - Analyst Ratings
# ============================================================================

class AnalystRating(BaseModel):
    """Analyst rating."""
    analyst: str
    firm: str
    rating: str
    price_target: Optional[float] = None
    previous_rating: Optional[str] = None
    previous_price_target: Optional[float] = None
    date: date


class AnalystRatingsResponse(BaseModel):
    """Analyst ratings response."""
    symbol: str
    current_price: float
    avg_price_target: float
    high_price_target: float
    low_price_target: float
    num_analysts: int
    buy_count: int
    hold_count: int
    sell_count: int
    ratings: list[AnalystRating] = Field(default_factory=list)


# ============================================================================
# Endpoints - News
# ============================================================================

@router.get(
    "/news",
    response_model=NewsResponse,
    summary="Get news",
    description="Get market news and analysis."
)
async def get_news(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    sentiment: Optional[NewsSentiment] = Query(None, description="Filter by sentiment"),
    source: Optional[str] = Query(None, description="Filter by source"),
    limit: int = Query(20, ge=1, le=100)
) -> NewsResponse:
    """
    Get market news with sentiment analysis.
    """
    articles = [
        NewsArticle(
            id="news-001",
            title="Tech Stocks Rally on Strong Earnings Reports",
            summary="Major technology companies exceeded earnings expectations, driving the NASDAQ to new highs...",
            source="Bloomberg",
            url="https://bloomberg.com/news/tech-rally",
            symbols=["AAPL", "MSFT", "NVDA"],
            sentiment=NewsSentiment.BULLISH,
            sentiment_score=0.72,
            relevance_score=0.95,
            published_at=datetime(2025, 1, 13, 10, 30)
        ),
        NewsArticle(
            id="news-002",
            title="Federal Reserve Signals Patience on Rate Cuts",
            summary="Fed officials indicated they will take a measured approach to rate adjustments in 2025...",
            source="Reuters",
            url="https://reuters.com/fed-rates",
            symbols=["SPY", "TLT"],
            sentiment=NewsSentiment.NEUTRAL,
            sentiment_score=0.05,
            relevance_score=0.88,
            published_at=datetime(2025, 1, 13, 9, 15)
        ),
        NewsArticle(
            id="news-003",
            title="Oil Prices Drop on Demand Concerns",
            summary="Crude oil futures fell sharply as global demand forecasts were revised downward...",
            source="CNBC",
            url="https://cnbc.com/oil-drop",
            symbols=["XLE", "USO", "XOM"],
            sentiment=NewsSentiment.BEARISH,
            sentiment_score=-0.45,
            relevance_score=0.82,
            published_at=datetime(2025, 1, 13, 8, 45)
        ),
    ]
    
    # Apply filters
    if symbol:
        articles = [a for a in articles if symbol.upper() in a.symbols]
    if sentiment:
        articles = [a for a in articles if a.sentiment == sentiment]
    if source:
        articles = [a for a in articles if a.source.lower() == source.lower()]
    
    avg_sentiment = sum(a.sentiment_score for a in articles) / len(articles) if articles else 0
    
    return NewsResponse(
        articles=articles[:limit],
        total=len(articles),
        avg_sentiment=avg_sentiment
    )


@router.get(
    "/news/{symbol}",
    response_model=NewsResponse,
    summary="Get symbol news",
    description="Get news for a specific symbol."
)
async def get_symbol_news(
    symbol: str = Path(...),
    limit: int = Query(20, ge=1, le=100)
) -> NewsResponse:
    """
    Get news specifically for a symbol.
    """
    return await get_news(symbol=symbol, limit=limit)


# ============================================================================
# Endpoints - 13F Filings
# ============================================================================

@router.get(
    "/13f",
    response_model=Filing13FResponse,
    summary="Get 13F filings",
    description="Get institutional 13F filings."
)
async def get_13f_filings(
    filer: Optional[str] = Query(None, description="Filter by filer name"),
    symbol: Optional[str] = Query(None, description="Filter by held symbol"),
    quarter: Optional[str] = Query(None, description="Filter by quarter (e.g., 2024Q4)"),
    limit: int = Query(20, ge=1, le=100)
) -> Filing13FResponse:
    """
    Get 13F filings from institutional investors.
    """
    filings = [
        Filing13F(
            filing_id="13f-001",
            filer_name="Berkshire Hathaway Inc",
            filer_cik="0001067983",
            filing_date=date(2025, 2, 14),
            quarter_end=date(2024, 12, 31),
            total_value=350000000000,
            holdings_count=45,
            new_positions=3,
            closed_positions=2,
            top_holdings=[
                HoldingChange(
                    symbol="AAPL", name="Apple Inc", shares=915000000,
                    value=140000000000, shares_change=0, shares_change_percent=0,
                    is_new_position=False, is_closed_position=False
                ),
            ],
            notable_changes=[
                HoldingChange(
                    symbol="OXY", name="Occidental Petroleum", shares=250000000,
                    value=15000000000, shares_change=25000000, shares_change_percent=11.1,
                    is_new_position=False, is_closed_position=False
                ),
            ]
        ),
        Filing13F(
            filing_id="13f-002",
            filer_name="Bridgewater Associates",
            filer_cik="0001350694",
            filing_date=date(2025, 2, 14),
            quarter_end=date(2024, 12, 31),
            total_value=18000000000,
            holdings_count=850,
            new_positions=125,
            closed_positions=98,
            top_holdings=[],
            notable_changes=[]
        ),
    ]
    
    return Filing13FResponse(
        filings=filings[:limit],
        total=len(filings)
    )


@router.get(
    "/13f/{symbol}",
    response_model=InstitutionalOwnership,
    summary="Institutional ownership",
    description="Get institutional ownership for a symbol."
)
async def get_institutional_ownership(
    symbol: str = Path(...)
) -> InstitutionalOwnership:
    """
    Get institutional ownership breakdown for a symbol.
    """
    return InstitutionalOwnership(
        symbol=symbol.upper(),
        total_institutional_shares=5000000000,
        institutional_ownership_percent=62.5,
        num_institutions=4500,
        top_holders=[
            {"name": "Vanguard Group", "shares": 850000000, "percent": 5.5},
            {"name": "BlackRock", "shares": 780000000, "percent": 5.1},
            {"name": "Berkshire Hathaway", "shares": 915000000, "percent": 5.9},
        ],
        recent_changes=[]
    )


# ============================================================================
# Endpoints - Earnings
# ============================================================================

@router.get(
    "/earnings/calendar",
    response_model=EarningsCalendarResponse,
    summary="Earnings calendar",
    description="Get upcoming earnings releases."
)
async def get_earnings_calendar(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
) -> EarningsCalendarResponse:
    """
    Get earnings calendar with estimates.
    """
    earnings = [
        EarningsReport(
            symbol="AAPL",
            company_name="Apple Inc",
            report_date=date(2025, 1, 30),
            fiscal_quarter="Q1",
            fiscal_year=2025,
            eps_estimate=2.35,
            revenue_estimate=123500000000,
            report_time="AMC"
        ),
        EarningsReport(
            symbol="MSFT",
            company_name="Microsoft Corporation",
            report_date=date(2025, 1, 28),
            fiscal_quarter="Q2",
            fiscal_year=2025,
            eps_estimate=2.85,
            revenue_estimate=61500000000,
            report_time="AMC"
        ),
        EarningsReport(
            symbol="TSLA",
            company_name="Tesla Inc",
            report_date=date(2025, 1, 29),
            fiscal_quarter="Q4",
            fiscal_year=2024,
            eps_estimate=0.75,
            revenue_estimate=25800000000,
            report_time="AMC"
        ),
    ]
    
    if symbol:
        earnings = [e for e in earnings if e.symbol == symbol.upper()]
    
    return EarningsCalendarResponse(
        earnings=earnings[:limit],
        total=len(earnings),
        date_range_start=start_date or date(2025, 1, 1),
        date_range_end=end_date or date(2025, 2, 28)
    )


@router.get(
    "/earnings/{symbol}",
    response_model=EarningsHistoryResponse,
    summary="Earnings history",
    description="Get earnings history for a symbol."
)
async def get_earnings_history(
    symbol: str = Path(...),
    quarters: int = Query(8, ge=1, le=20)
) -> EarningsHistoryResponse:
    """
    Get historical earnings for a symbol.
    """
    earnings = [
        EarningsReport(
            symbol=symbol.upper(),
            company_name="Apple Inc",
            report_date=date(2024, 10, 31),
            fiscal_quarter="Q4",
            fiscal_year=2024,
            eps_estimate=1.55,
            eps_actual=1.64,
            eps_surprise=0.09,
            eps_surprise_percent=5.8,
            revenue_estimate=94500000000,
            revenue_actual=94930000000,
            revenue_surprise=430000000,
            revenue_surprise_percent=0.45,
            surprise_classification=EarningsSurprise.BEAT,
            report_time="AMC"
        ),
        EarningsReport(
            symbol=symbol.upper(),
            company_name="Apple Inc",
            report_date=date(2024, 8, 1),
            fiscal_quarter="Q3",
            fiscal_year=2024,
            eps_estimate=1.35,
            eps_actual=1.40,
            eps_surprise=0.05,
            eps_surprise_percent=3.7,
            revenue_estimate=84500000000,
            revenue_actual=85780000000,
            revenue_surprise=1280000000,
            revenue_surprise_percent=1.5,
            surprise_classification=EarningsSurprise.BEAT,
            report_time="AMC"
        ),
    ]
    
    beat_count = sum(1 for e in earnings if e.surprise_classification == EarningsSurprise.BEAT)
    avg_surprise = sum(e.eps_surprise_percent or 0 for e in earnings) / len(earnings) if earnings else 0
    
    return EarningsHistoryResponse(
        symbol=symbol.upper(),
        earnings=earnings[:quarters],
        beat_rate=beat_count / len(earnings) if earnings else 0,
        avg_surprise_percent=avg_surprise
    )


# ============================================================================
# Endpoints - Analyst Ratings
# ============================================================================

@router.get(
    "/ratings/{symbol}",
    response_model=AnalystRatingsResponse,
    summary="Analyst ratings",
    description="Get analyst ratings and price targets."
)
async def get_analyst_ratings(
    symbol: str = Path(...)
) -> AnalystRatingsResponse:
    """
    Get analyst ratings and price targets for a symbol.
    """
    ratings = [
        AnalystRating(
            analyst="Dan Ives",
            firm="Wedbush",
            rating="Outperform",
            price_target=250.00,
            previous_rating="Outperform",
            previous_price_target=225.00,
            date=date(2025, 1, 10)
        ),
        AnalystRating(
            analyst="Amit Daryanani",
            firm="Evercore ISI",
            rating="Outperform",
            price_target=235.00,
            date=date(2025, 1, 8)
        ),
        AnalystRating(
            analyst="Samik Chatterjee",
            firm="JP Morgan",
            rating="Overweight",
            price_target=225.00,
            date=date(2025, 1, 5)
        ),
    ]
    
    return AnalystRatingsResponse(
        symbol=symbol.upper(),
        current_price=152.00,
        avg_price_target=236.67,
        high_price_target=250.00,
        low_price_target=225.00,
        num_analysts=35,
        buy_count=28,
        hold_count=6,
        sell_count=1,
        ratings=ratings
    )
