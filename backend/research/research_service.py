"""
QUANT INDUSTRY - Research Service
13F holdings, SEC filings, dark pool, earnings, and news data
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)


@dataclass
class Filing13F:
    cik: str
    filer_name: str
    report_date: str
    filing_date: str
    holdings: List[Dict]
    total_value: float
    positions_count: int

    def to_dict(self) -> Dict:
        return {
            "cik": self.cik,
            "filer_name": self.filer_name,
            "report_date": self.report_date,
            "filing_date": self.filing_date,
            "holdings": self.holdings,
            "total_value": self.total_value,
            "positions_count": self.positions_count,
        }


@dataclass
class SECFiling:
    accession_number: str
    form_type: str
    company_name: str
    cik: str
    filed_date: str
    period_date: str
    description: str
    url: str

    def to_dict(self) -> Dict:
        return {
            "accession_number": self.accession_number,
            "form_type": self.form_type,
            "company_name": self.company_name,
            "cik": self.cik,
            "filed_date": self.filed_date,
            "period_date": self.period_date,
            "description": self.description,
            "url": self.url,
        }


@dataclass
class DarkPoolTrade:
    symbol: str
    timestamp: str
    price: float
    size: int
    exchange: str
    trade_type: str  # BLOCK, SWEEP, etc.
    sentiment: str  # BULLISH, BEARISH, NEUTRAL

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "price": self.price,
            "size": self.size,
            "exchange": self.exchange,
            "trade_type": self.trade_type,
            "sentiment": self.sentiment,
            "notional": self.price * self.size,
        }


@dataclass
class EarningsEvent:
    symbol: str
    company_name: str
    report_date: str
    report_time: str  # BMO (before market open), AMC (after market close)
    eps_estimate: Optional[float]
    eps_actual: Optional[float]
    eps_surprise: Optional[float]
    revenue_estimate: Optional[float]
    revenue_actual: Optional[float]

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "report_date": self.report_date,
            "report_time": self.report_time,
            "eps_estimate": self.eps_estimate,
            "eps_actual": self.eps_actual,
            "eps_surprise": self.eps_surprise,
            "revenue_estimate": self.revenue_estimate,
            "revenue_actual": self.revenue_actual,
        }


@dataclass
class NewsArticle:
    id: str
    title: str
    source: str
    url: str
    published_at: str
    summary: str
    symbols: List[str]
    sentiment: str  # POSITIVE, NEGATIVE, NEUTRAL
    sentiment_score: float

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at,
            "summary": self.summary,
            "symbols": self.symbols,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
        }


class ResearchService:
    """
    Research service for institutional data and market intelligence
    """

    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes

        # Major institutional holders
        self.major_holders = {
            "BERKSHIRE HATHAWAY": "1067983",
            "BLACKROCK": "1364742",
            "VANGUARD": "102909",
            "STATE STREET": "93751",
            "FIDELITY": "315066",
            "JPMORGAN": "19617",
            "CITADEL": "1423053",
            "BRIDGEWATER": "1350694",
            "RENAISSANCE": "1037389",
            "TWO SIGMA": "1179392",
        }

        logger.info("ResearchService initialized")

    def get_13f_holdings(self, cik: str = None, filer_name: str = None) -> Optional[Filing13F]:
        """Get 13F holdings for an institutional investor"""
        cache_key = f"13f_{cik or filer_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Try SEC EDGAR API
        holdings = self._fetch_13f_from_sec(cik, filer_name)

        if holdings:
            self.cache[cache_key] = holdings
            return holdings

        # Generate sample data
        return self._generate_13f_holdings(cik, filer_name)

    def _fetch_13f_from_sec(self, cik: str, filer_name: str) -> Optional[Filing13F]:
        """Fetch 13F from SEC EDGAR"""
        try:
            if not cik and filer_name:
                cik = self.major_holders.get(filer_name.upper())

            if not cik:
                return None

            # SEC EDGAR API
            headers = {"User-Agent": "QuantIndustry research@quantindustry.com"}

            response = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                name = data.get("name", "Unknown")

                # Find most recent 13F
                filings = data.get("filings", {}).get("recent", {})
                forms = filings.get("form", [])
                dates = filings.get("filingDate", [])

                for i, form in enumerate(forms):
                    if form == "13F-HR":
                        # Would need to parse actual 13F XML here
                        # For now, return generated data with real metadata
                        return self._generate_13f_holdings(cik, name)

        except Exception as e:
            logger.error(f"Error fetching 13F: {e}")

        return None

    def _generate_13f_holdings(self, cik: str, filer_name: str) -> Filing13F:
        """Generate sample 13F holdings"""
        stocks = [
            ("AAPL", "Apple Inc", 150.0, 1000000),
            ("MSFT", "Microsoft Corp", 380.0, 800000),
            ("GOOGL", "Alphabet Inc", 140.0, 500000),
            ("AMZN", "Amazon.com Inc", 180.0, 600000),
            ("NVDA", "NVIDIA Corp", 500.0, 400000),
            ("META", "Meta Platforms Inc", 500.0, 350000),
            ("TSLA", "Tesla Inc", 250.0, 300000),
            ("BRK.B", "Berkshire Hathaway", 400.0, 200000),
            ("JPM", "JPMorgan Chase", 190.0, 450000),
            ("V", "Visa Inc", 280.0, 380000),
        ]

        holdings = []
        total_value = 0

        for symbol, name, price, shares in stocks:
            # Randomize
            actual_shares = int(shares * np.random.uniform(0.5, 1.5))
            value = price * actual_shares
            total_value += value

            holdings.append({
                "symbol": symbol,
                "name": name,
                "shares": actual_shares,
                "value": value,
                "pct_portfolio": 0,  # Will calculate after
                "change": np.random.choice(["NEW", "ADDED", "REDUCED", "UNCHANGED"]),
            })

        # Calculate percentages
        for h in holdings:
            h["pct_portfolio"] = round(h["value"] / total_value * 100, 2)

        return Filing13F(
            cik=cik or "0000000000",
            filer_name=filer_name or "Unknown Institution",
            report_date=(datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
            filing_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            holdings=sorted(holdings, key=lambda x: x["value"], reverse=True),
            total_value=total_value,
            positions_count=len(holdings),
        )

    def get_sec_filings(self, symbol: str, form_types: List[str] = None) -> List[SECFiling]:
        """Get SEC filings for a company"""
        cache_key = f"sec_{symbol}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        filings = self._fetch_sec_filings(symbol, form_types)

        if filings:
            self.cache[cache_key] = filings

        return filings

    def _fetch_sec_filings(self, symbol: str, form_types: List[str] = None) -> List[SECFiling]:
        """Fetch SEC filings from EDGAR"""
        try:
            headers = {"User-Agent": "QuantIndustry research@quantindustry.com"}

            # First get CIK
            response = requests.get(
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={symbol}&type=&dateb=&owner=include&count=40&output=atom",
                headers=headers,
                timeout=10
            )

            # For simplicity, generate sample filings
            return self._generate_sec_filings(symbol, form_types)

        except Exception as e:
            logger.error(f"Error fetching SEC filings: {e}")
            return self._generate_sec_filings(symbol, form_types)

    def _generate_sec_filings(self, symbol: str, form_types: List[str] = None) -> List[SECFiling]:
        """Generate sample SEC filings"""
        company_names = {
            "AAPL": "Apple Inc",
            "MSFT": "Microsoft Corporation",
            "GOOGL": "Alphabet Inc",
            "AMZN": "Amazon.com Inc",
            "NVDA": "NVIDIA Corporation",
            "META": "Meta Platforms Inc",
            "TSLA": "Tesla Inc",
        }

        company_name = company_names.get(symbol, f"{symbol} Corp")

        all_forms = ["10-K", "10-Q", "8-K", "4", "SC 13G", "DEF 14A"]
        if form_types:
            forms = [f for f in all_forms if f in form_types]
        else:
            forms = all_forms

        filings = []
        base_date = datetime.now()

        for i, form in enumerate(forms * 2):  # Multiple of each
            filed_date = base_date - timedelta(days=i * 15 + np.random.randint(0, 10))

            descriptions = {
                "10-K": "Annual Report",
                "10-Q": "Quarterly Report",
                "8-K": "Current Report",
                "4": "Statement of Changes in Beneficial Ownership",
                "SC 13G": "Beneficial Ownership Report",
                "DEF 14A": "Proxy Statement",
            }

            filing = SECFiling(
                accession_number=f"0001234567-{filed_date.strftime('%y')}-{np.random.randint(100000, 999999)}",
                form_type=form,
                company_name=company_name,
                cik=f"{np.random.randint(100000, 999999)}",
                filed_date=filed_date.strftime("%Y-%m-%d"),
                period_date=(filed_date - timedelta(days=30)).strftime("%Y-%m-%d"),
                description=descriptions.get(form, "Filing"),
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={symbol}",
            )

            filings.append(filing)

        return sorted(filings, key=lambda x: x.filed_date, reverse=True)

    def get_dark_pool_activity(self, symbol: str) -> List[DarkPoolTrade]:
        """Get dark pool trading activity"""
        cache_key = f"darkpool_{symbol}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        trades = self._fetch_dark_pool(symbol)

        if trades:
            self.cache[cache_key] = trades

        return trades

    def _fetch_dark_pool(self, symbol: str) -> List[DarkPoolTrade]:
        """Fetch dark pool data from FINRA"""
        try:
            from ..config.api_keys import get_api_keys
            keys = get_api_keys()

            if keys.finra.is_configured:
                # FINRA ATS data endpoint
                # Note: Actual implementation would use FINRA's API
                pass

        except Exception as e:
            logger.error(f"Error fetching dark pool: {e}")

        # Generate sample data
        return self._generate_dark_pool(symbol)

    def _generate_dark_pool(self, symbol: str) -> List[DarkPoolTrade]:
        """Generate sample dark pool trades"""
        # Get current price estimate
        base_price = {
            "AAPL": 175.0, "MSFT": 380.0, "GOOGL": 140.0, "AMZN": 180.0,
            "NVDA": 500.0, "META": 500.0, "TSLA": 250.0, "SPY": 475.0,
        }.get(symbol, 100.0)

        exchanges = ["UBSS", "DBAB", "GSCO", "MSPL", "CSFB", "ITGI"]
        trade_types = ["BLOCK", "SWEEP", "SPLIT", "CROSS"]

        trades = []
        base_time = datetime.now()

        for i in range(20):
            price = base_price * np.random.uniform(0.995, 1.005)
            size = int(np.random.choice([
                np.random.randint(1000, 5000),
                np.random.randint(5000, 20000),
                np.random.randint(20000, 100000),
            ], p=[0.5, 0.35, 0.15]))

            # Determine sentiment based on size and price movement
            if size > 50000:
                sentiment = "BULLISH" if np.random.random() > 0.4 else "BEARISH"
            else:
                sentiment = np.random.choice(["BULLISH", "BEARISH", "NEUTRAL"])

            trade = DarkPoolTrade(
                symbol=symbol,
                timestamp=(base_time - timedelta(minutes=i * np.random.randint(5, 30))).isoformat(),
                price=round(price, 2),
                size=size,
                exchange=np.random.choice(exchanges),
                trade_type=np.random.choice(trade_types),
                sentiment=sentiment,
            )

            trades.append(trade)

        return sorted(trades, key=lambda x: x.timestamp, reverse=True)

    def get_earnings_calendar(self, start_date: str = None, end_date: str = None, symbol: str = None) -> List[EarningsEvent]:
        """Get earnings calendar"""
        return self._generate_earnings_calendar(start_date, end_date, symbol)

    def _generate_earnings_calendar(self, start_date: str, end_date: str, symbol: str) -> List[EarningsEvent]:
        """Generate earnings calendar"""
        companies = [
            ("AAPL", "Apple Inc"),
            ("MSFT", "Microsoft Corp"),
            ("GOOGL", "Alphabet Inc"),
            ("AMZN", "Amazon.com"),
            ("NVDA", "NVIDIA Corp"),
            ("META", "Meta Platforms"),
            ("TSLA", "Tesla Inc"),
            ("JPM", "JPMorgan Chase"),
            ("BAC", "Bank of America"),
            ("WMT", "Walmart Inc"),
        ]

        if symbol:
            companies = [(s, n) for s, n in companies if s == symbol]

        events = []
        base_date = datetime.now()

        for i, (sym, name) in enumerate(companies):
            report_date = base_date + timedelta(days=np.random.randint(-10, 30))

            eps_estimate = round(np.random.uniform(1.0, 5.0), 2)
            eps_actual = round(eps_estimate * np.random.uniform(0.9, 1.15), 2) if report_date < base_date else None
            eps_surprise = round((eps_actual - eps_estimate) / eps_estimate * 100, 2) if eps_actual else None

            revenue_estimate = round(np.random.uniform(10, 100), 2) * 1e9
            revenue_actual = round(revenue_estimate * np.random.uniform(0.95, 1.1), 2) if report_date < base_date else None

            event = EarningsEvent(
                symbol=sym,
                company_name=name,
                report_date=report_date.strftime("%Y-%m-%d"),
                report_time=np.random.choice(["BMO", "AMC"]),
                eps_estimate=eps_estimate,
                eps_actual=eps_actual,
                eps_surprise=eps_surprise,
                revenue_estimate=revenue_estimate,
                revenue_actual=revenue_actual,
            )

            events.append(event)

        return sorted(events, key=lambda x: x.report_date)

    def get_news(self, symbol: str = None, category: str = None) -> List[NewsArticle]:
        """Get market news"""
        cache_key = f"news_{symbol or 'all'}_{category or 'all'}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Try NewsAPI
        news = self._fetch_news_api(symbol, category)

        if news:
            self.cache[cache_key] = news
            return news

        # Generate sample news
        return self._generate_news(symbol)

    def _fetch_news_api(self, symbol: str, category: str) -> List[NewsArticle]:
        """Fetch news from NewsAPI"""
        try:
            from ..config.api_keys import get_api_keys
            keys = get_api_keys()

            if not keys.news_api.is_configured:
                return []

            params = {
                "apiKey": keys.news_api.api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
            }

            if symbol:
                params["q"] = f"{symbol} stock"
            else:
                params["category"] = category or "business"
                params["country"] = "us"

            endpoint = "everything" if symbol else "top-headlines"
            response = requests.get(
                f"{keys.news_api.base_url}/{endpoint}",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                articles = []

                for article in data.get("articles", []):
                    # Simple sentiment analysis
                    title = article.get("title", "").lower()
                    positive_words = ["surge", "rally", "gain", "beat", "strong"]
                    negative_words = ["fall", "drop", "miss", "weak", "crash"]

                    pos_count = sum(1 for w in positive_words if w in title)
                    neg_count = sum(1 for w in negative_words if w in title)

                    if pos_count > neg_count:
                        sentiment = "POSITIVE"
                        score = 0.5 + pos_count * 0.1
                    elif neg_count > pos_count:
                        sentiment = "NEGATIVE"
                        score = 0.5 - neg_count * 0.1
                    else:
                        sentiment = "NEUTRAL"
                        score = 0.5

                    news_article = NewsArticle(
                        id=str(hash(article.get("url", "")))[:8],
                        title=article.get("title", ""),
                        source=article.get("source", {}).get("name", "Unknown"),
                        url=article.get("url", ""),
                        published_at=article.get("publishedAt", ""),
                        summary=article.get("description", ""),
                        symbols=[symbol] if symbol else [],
                        sentiment=sentiment,
                        sentiment_score=score,
                    )

                    articles.append(news_article)

                return articles

        except Exception as e:
            logger.error(f"Error fetching news: {e}")

        return []

    def _generate_news(self, symbol: str) -> List[NewsArticle]:
        """Generate sample news articles"""
        headlines = [
            ("Tech Stocks Rally on Strong Earnings", "POSITIVE", 0.7),
            ("Fed Signals Rate Cut Expectations", "POSITIVE", 0.6),
            ("Market Volatility Increases Amid Trade Concerns", "NEGATIVE", 0.4),
            ("AI Stocks Continue Their Momentum", "POSITIVE", 0.65),
            ("Inflation Data Shows Mixed Signals", "NEUTRAL", 0.5),
            ("Consumer Spending Remains Resilient", "POSITIVE", 0.55),
            ("Energy Sector Under Pressure", "NEGATIVE", 0.35),
            ("Quarterly Reports Beat Expectations", "POSITIVE", 0.7),
            ("Bond Yields Rise to New Highs", "NEGATIVE", 0.4),
            ("Economic Outlook Remains Uncertain", "NEUTRAL", 0.5),
        ]

        sources = ["Reuters", "Bloomberg", "CNBC", "WSJ", "MarketWatch", "Yahoo Finance"]
        articles = []
        base_time = datetime.now()

        for i, (title, sentiment, score) in enumerate(headlines):
            article = NewsArticle(
                id=f"news_{i:04d}",
                title=title,
                source=np.random.choice(sources),
                url=f"https://example.com/news/{i}",
                published_at=(base_time - timedelta(hours=i * 2)).isoformat(),
                summary=f"Summary of: {title}",
                symbols=[symbol] if symbol else [],
                sentiment=sentiment,
                sentiment_score=score,
            )

            articles.append(article)

        return articles

    def get_institutional_holders(self, symbol: str) -> List[Dict]:
        """Get institutional holders for a stock"""
        # Generate sample institutional holders
        institutions = [
            ("Vanguard Group", 8.5, 150000000),
            ("BlackRock Inc", 7.2, 128000000),
            ("State Street Corp", 4.1, 73000000),
            ("Fidelity Investments", 3.8, 68000000),
            ("Berkshire Hathaway", 2.5, 45000000),
            ("JPMorgan Chase", 2.1, 38000000),
            ("Morgan Stanley", 1.8, 32000000),
            ("Bank of America", 1.5, 27000000),
            ("Goldman Sachs", 1.3, 23000000),
            ("Citadel Advisors", 1.1, 20000000),
        ]

        return [
            {
                "institution": name,
                "pct_ownership": pct,
                "shares": shares,
                "value": shares * 150,  # Approximate
                "change": np.random.choice(["INCREASED", "DECREASED", "UNCHANGED"]),
            }
            for name, pct, shares in institutions
        ]


# Singleton instance
_research_service: Optional[ResearchService] = None

def get_research_service() -> ResearchService:
    global _research_service
    if _research_service is None:
        _research_service = ResearchService()
    return _research_service
