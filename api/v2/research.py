"""
QUANT INDUSTRY V1 - Research API (v2)
=====================================
Research data: news, 13F filings, earnings, analyst ratings.

WIRED TO REAL IMPLEMENTATIONS:
- ResearchService (SEC EDGAR, FINRA, earnings APIs)
- MarketDataService (Alpaca news)
- Backend research routes patterns
"""

from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Service imports
# ============================================================================

_research_service = None
_market_data_service = None

# Try to import ResearchService
try:
    from backend.services.research_service import get_research_service, ResearchDataStatus
    _research_available = True
except ImportError:
    try:
        from services.research_service import get_research_service, ResearchDataStatus
        _research_available = True
    except ImportError:
        try:
            from backend.research.research_service import get_research_service
            _research_available = True
        except ImportError:
            try:
                from research.research_service import get_research_service
                _research_available = True
            except ImportError:
                _research_available = False
                logger.warning("ResearchService not available")

# Try to import MarketDataService for news
try:
    from backend.services.market_data_service import get_market_data_service
    _market_service_available = True
except ImportError:
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from backend.services.market_data_service import get_market_data_service
        _market_service_available = True
    except ImportError:
        _market_service_available = False


def _get_research():
    """Get research service singleton."""
    global _research_service
    if _research_service is None and _research_available:
        try:
            _research_service = get_research_service()
        except Exception as e:
            logger.error(f"Failed to get research service: {e}")
    return _research_service


async def _get_market_service():
    """Get market data service singleton for news."""
    global _market_data_service
    if _market_data_service is None and _market_service_available:
        try:
            _market_data_service = await get_market_data_service()
        except Exception as e:
            logger.error(f"Failed to get market data service: {e}")
    return _market_data_service


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
    sentiment: NewsSentiment = Field(default=NewsSentiment.NEUTRAL)
    sentiment_score: float = Field(default=0.0, ge=-1, le=1)
    relevance_score: float = Field(default=0.5, ge=0, le=1)
    published_at: datetime


class NewsResponse(BaseModel):
    """News response."""
    articles: list[NewsArticle] = Field(default_factory=list)
    total: int
    avg_sentiment: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="unknown")


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
    status: str = Field(default="available")
    message: str = Field(default="")
    source: str = Field(default="unknown")


class InstitutionalOwnership(BaseModel):
    """Institutional ownership for a symbol."""
    symbol: str
    total_institutional_shares: Optional[int] = None
    institutional_ownership_percent: Optional[float] = None
    num_institutions: Optional[int] = None
    top_holders: list[dict] = Field(default_factory=list)
    recent_changes: list[HoldingChange] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="available")
    message: str = Field(default="")
    source: str = Field(default="unknown")


# ============================================================================
# Pydantic Models - SEC Filings
# ============================================================================

class SECFiling(BaseModel):
    """SEC filing record."""
    filing_id: str
    form_type: str
    filed_date: date
    accepted_date: Optional[datetime] = None
    description: str
    document_url: str
    filing_url: str


class SECFilingsResponse(BaseModel):
    """SEC filings response."""
    symbol: str
    filings: list[SECFiling] = Field(default_factory=list)
    total: int
    status: str = Field(default="available")
    message: str = Field(default="")
    source: str = Field(default="unknown")


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
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    eps_surprise: Optional[float] = None
    eps_surprise_percent: Optional[float] = None
    revenue_estimate: Optional[float] = None
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
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    status: str = Field(default="available")
    message: str = Field(default="")
    source: str = Field(default="unknown")


class EarningsHistoryResponse(BaseModel):
    """Earnings history for a symbol."""
    symbol: str
    earnings: list[EarningsReport] = Field(default_factory=list)
    beat_rate: Optional[float] = None
    avg_surprise_percent: Optional[float] = None
    status: str = Field(default="available")
    message: str = Field(default="")
    source: str = Field(default="unknown")


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
    current_price: Optional[float] = None
    avg_price_target: Optional[float] = None
    high_price_target: Optional[float] = None
    low_price_target: Optional[float] = None
    num_analysts: Optional[int] = None
    buy_count: Optional[int] = None
    hold_count: Optional[int] = None
    sell_count: Optional[int] = None
    ratings: list[AnalystRating] = Field(default_factory=list)
    status: str = Field(default="available")
    message: str = Field(default="")
    source: str = Field(default="unknown")


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
    
    Uses Alpaca News API when available.
    """
    service = await _get_market_service()
    if service:
        try:
            symbols = [symbol.upper()] if symbol else None
            news_data = await service.get_news(symbols=symbols, limit=limit)
            
            articles = []
            for item in news_data:
                # Infer sentiment from content (basic heuristic)
                headline = item.get("headline", "").lower()
                summary = item.get("summary", "").lower()
                text = headline + " " + summary
                
                # Simple keyword sentiment
                bullish_words = ["surge", "rally", "gain", "beat", "record", "soar", "jump", "rise"]
                bearish_words = ["fall", "drop", "plunge", "miss", "decline", "crash", "tumble", "sink"]
                
                bullish_score = sum(1 for w in bullish_words if w in text)
                bearish_score = sum(1 for w in bearish_words if w in text)
                
                if bullish_score > bearish_score + 1:
                    sent = NewsSentiment.BULLISH
                    score = min(0.8, 0.3 + bullish_score * 0.1)
                elif bearish_score > bullish_score + 1:
                    sent = NewsSentiment.BEARISH
                    score = max(-0.8, -0.3 - bearish_score * 0.1)
                else:
                    sent = NewsSentiment.NEUTRAL
                    score = 0.0
                
                # Parse timestamp
                try:
                    ts = datetime.fromisoformat(item.get("created_at", "").replace("Z", "+00:00"))
                except:
                    ts = datetime.utcnow()
                
                articles.append(NewsArticle(
                    id=item.get("id", ""),
                    title=item.get("headline", ""),
                    summary=item.get("summary", ""),
                    source=item.get("source", "unknown"),
                    url=item.get("url", ""),
                    symbols=item.get("symbols", []),
                    sentiment=sent,
                    sentiment_score=score,
                    relevance_score=0.8,
                    published_at=ts
                ))
            
            # Apply filters
            if sentiment:
                articles = [a for a in articles if a.sentiment == sentiment]
            if source:
                articles = [a for a in articles if a.source.lower() == source.lower()]
            
            avg_sentiment = sum(a.sentiment_score for a in articles) / len(articles) if articles else 0
            
            return NewsResponse(
                articles=articles[:limit],
                total=len(articles),
                avg_sentiment=avg_sentiment,
                source="alpaca"
            )
        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
    
    # Fallback mock data
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
            published_at=datetime.utcnow()
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
            published_at=datetime.utcnow()
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
        avg_sentiment=avg_sentiment,
        source="fallback"
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
    
    Note: Requires SEC EDGAR API connection.
    """
    research = _get_research()
    if research and symbol:
        try:
            response = research.get_13f_holdings(symbol)
            data = response.to_dict()
            
            if data.get("status") == "unavailable":
                return Filing13FResponse(
                    filings=[],
                    total=0,
                    status="unavailable",
                    message=data.get("message", "13F data requires SEC EDGAR API connection"),
                    source="none"
                )
        except Exception as e:
            logger.warning(f"13F fetch failed: {e}")
    
    # Return unavailable status - we don't fake 13F data
    return Filing13FResponse(
        filings=[],
        total=0,
        status="unavailable",
        message="13F institutional holdings require SEC EDGAR API connection. Configure sec_edgar_api_key to enable.",
        source="none"
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
    
    Note: Requires SEC EDGAR API connection.
    """
    symbol = symbol.upper()
    
    research = _get_research()
    if research:
        try:
            response = research.get_13f_holdings(symbol)
            data = response.to_dict()
            
            if data.get("status") == "unavailable":
                return InstitutionalOwnership(
                    symbol=symbol,
                    status="unavailable",
                    message=data.get("message", "Institutional ownership data requires SEC EDGAR API"),
                    source="none"
                )
            
            # If we got real data, map it
            inner_data = data.get("data", {})
            return InstitutionalOwnership(
                symbol=symbol,
                total_institutional_shares=inner_data.get("total_institutional_shares"),
                institutional_ownership_percent=inner_data.get("institutional_ownership_percent"),
                num_institutions=len(inner_data.get("holders", [])),
                top_holders=inner_data.get("holders", [])[:10],
                status="available",
                source=data.get("source", "sec_edgar")
            )
        except Exception as e:
            logger.warning(f"Institutional ownership failed for {symbol}: {e}")
    
    return InstitutionalOwnership(
        symbol=symbol,
        status="unavailable",
        message="Institutional ownership data requires SEC EDGAR API connection. Configure sec_edgar_api_key to enable.",
        source="none"
    )


# ============================================================================
# Endpoints - SEC Filings
# ============================================================================

@router.get(
    "/sec/{symbol}",
    response_model=SECFilingsResponse,
    summary="SEC filings",
    description="Get SEC filings for a symbol."
)
async def get_sec_filings(
    symbol: str = Path(...),
    form_type: Optional[str] = Query(None, description="Filter by form type (10-K, 10-Q, 8-K, etc.)"),
    limit: int = Query(20, ge=1, le=100)
) -> SECFilingsResponse:
    """
    Get SEC filings for a symbol.
    
    Note: Requires SEC EDGAR API connection.
    """
    symbol = symbol.upper()
    
    research = _get_research()
    if research:
        try:
            response = research.get_sec_filings(symbol, limit)
            data = response.to_dict()
            
            if data.get("status") == "unavailable":
                return SECFilingsResponse(
                    symbol=symbol,
                    filings=[],
                    total=0,
                    status="unavailable",
                    message=data.get("message", "SEC filings require SEC EDGAR API connection"),
                    source="none"
                )
            
            # Map real data if available
            inner = data.get("data", {})
            filings = []
            for f in inner.get("filings", []):
                filings.append(SECFiling(
                    filing_id=f.get("accession_number", ""),
                    form_type=f.get("form_type", ""),
                    filed_date=date.fromisoformat(f["filed_date"]) if f.get("filed_date") else date.today(),
                    description=f.get("description", ""),
                    document_url=f.get("document_url", ""),
                    filing_url=f.get("filing_url", "")
                ))
            
            return SECFilingsResponse(
                symbol=symbol,
                filings=filings,
                total=len(filings),
                status="available",
                source=data.get("source", "sec_edgar")
            )
        except Exception as e:
            logger.warning(f"SEC filings failed for {symbol}: {e}")
    
    return SECFilingsResponse(
        symbol=symbol,
        filings=[],
        total=0,
        status="unavailable",
        message=f"SEC filings require SEC EDGAR API connection. Browse manually: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}",
        source="none"
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
    
    Note: Requires earnings API connection (Alpha Vantage or FMP).
    """
    research = _get_research()
    if research:
        try:
            symbols = [symbol.upper()] if symbol else None
            response = research.get_earnings(symbols=symbols)
            data = response.to_dict()
            
            if data.get("status") == "unavailable":
                return EarningsCalendarResponse(
                    earnings=[],
                    total=0,
                    date_range_start=start_date,
                    date_range_end=end_date,
                    status="unavailable",
                    message=data.get("message", "Earnings data requires API connection"),
                    source="none"
                )
        except Exception as e:
            logger.warning(f"Earnings calendar failed: {e}")
    
    return EarningsCalendarResponse(
        earnings=[],
        total=0,
        date_range_start=start_date or date.today(),
        date_range_end=end_date or date.today(),
        status="unavailable",
        message="Earnings calendar requires earnings API connection (Alpha Vantage or FMP). Configure earnings_api_key to enable.",
        source="none"
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
    
    Note: Requires earnings API connection.
    """
    symbol = symbol.upper()
    
    research = _get_research()
    if research:
        try:
            response = research.get_earnings(symbol=symbol)
            data = response.to_dict()
            
            if data.get("status") == "unavailable":
                return EarningsHistoryResponse(
                    symbol=symbol,
                    earnings=[],
                    status="unavailable",
                    message=data.get("message", "Earnings history requires API connection"),
                    source="none"
                )
        except Exception as e:
            logger.warning(f"Earnings history failed for {symbol}: {e}")
    
    return EarningsHistoryResponse(
        symbol=symbol,
        earnings=[],
        status="unavailable",
        message="Earnings history requires earnings API connection (Alpha Vantage or FMP). Configure earnings_api_key to enable.",
        source="none"
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
    
    Note: Requires financial data API (FMP, TipRanks, etc.)
    """
    symbol = symbol.upper()
    
    # Analyst ratings would need a dedicated API (e.g., TipRanks, FMP)
    # For now, return unavailable status
    return AnalystRatingsResponse(
        symbol=symbol,
        ratings=[],
        status="unavailable",
        message="Analyst ratings require financial data API connection (FMP, TipRanks). Not yet configured.",
        source="none"
    )


# ============================================================================
# Endpoints - Dark Pool
# ============================================================================

@router.get(
    "/darkpool/{symbol}",
    summary="Dark pool activity",
    description="Get dark pool / ATS trading activity."
)
async def get_dark_pool(symbol: str = Path(...)):
    """
    Get dark pool activity for a symbol.
    
    Note: Requires FINRA ATS API connection.
    """
    symbol = symbol.upper()
    
    research = _get_research()
    if research:
        try:
            response = research.get_dark_pool_data(symbol)
            return response.to_dict()
        except Exception as e:
            logger.warning(f"Dark pool data failed for {symbol}: {e}")
    
    return {
        "symbol": symbol,
        "status": "unavailable",
        "message": "Dark pool data requires FINRA ATS API connection. Configure finra_api_key to enable.",
        "source": "none",
        "data": {
            "dark_pool_volume": None,
            "lit_volume": None,
            "dark_pool_pct": None,
            "_link": "https://www.finra.org/finra-data/browse-catalog/equity-short-interest/api"
        }
    }
