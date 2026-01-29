"""
Economic and Earnings Event Calendar
====================================
Tracks upcoming events that may impact markets.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Set
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of market events."""
    # Economic
    FOMC = "fomc"
    GDP = "gdp"
    CPI = "cpi"
    PPI = "ppi"
    PCE = "pce"
    NFP = "nfp"  # Non-farm payrolls
    UNEMPLOYMENT = "unemployment"
    RETAIL_SALES = "retail_sales"
    CONSUMER_CONFIDENCE = "consumer_confidence"
    PMI = "pmi"
    ISM = "ism"
    HOUSING = "housing"
    TRADE_BALANCE = "trade_balance"
    
    # Central bank
    FED_SPEECH = "fed_speech"
    ECB = "ecb"
    BOJ = "boj"
    BOE = "boe"
    
    # Corporate
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    INVESTOR_DAY = "investor_day"
    SHAREHOLDER_MEETING = "shareholder_meeting"
    
    # Market structure
    OPTIONS_EXPIRY = "options_expiry"
    FUTURES_EXPIRY = "futures_expiry"
    INDEX_REBALANCE = "index_rebalance"
    
    # Other
    IPO = "ipo"
    DIVIDEND_EX = "dividend_ex"
    STOCK_SPLIT = "stock_split"
    
    OTHER = "other"


class EventImpact(Enum):
    """Expected market impact level."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class EconomicEvent:
    """Economic calendar event."""
    id: str
    event_type: EventType
    name: str
    datetime_utc: datetime
    
    # Expected values
    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None
    
    # Metadata
    country: str = "US"
    currency: str = "USD"
    impact: EventImpact = EventImpact.MEDIUM
    
    # Status
    is_released: bool = False
    released_at: Optional[datetime] = None
    
    @property
    def surprise(self) -> Optional[float]:
        """Actual vs forecast surprise."""
        if self.actual is not None and self.forecast is not None:
            return self.actual - self.forecast
        return None
    
    @property
    def surprise_pct(self) -> Optional[float]:
        """Percentage surprise."""
        if self.surprise is not None and self.forecast and self.forecast != 0:
            return (self.surprise / abs(self.forecast)) * 100
        return None
    
    @property
    def is_upcoming(self) -> bool:
        return not self.is_released and self.datetime_utc > datetime.utcnow()
    
    @property
    def time_until(self) -> timedelta:
        return self.datetime_utc - datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "name": self.name,
            "datetime_utc": self.datetime_utc.isoformat(),
            "forecast": self.forecast,
            "previous": self.previous,
            "actual": self.actual,
            "surprise": self.surprise,
            "surprise_pct": self.surprise_pct,
            "country": self.country,
            "impact": self.impact.value,
            "is_released": self.is_released,
        }


@dataclass
class EarningsEvent:
    """Earnings announcement event."""
    symbol: str
    company_name: str
    report_date: date
    report_time: str  # "BMO" (before market open), "AMC" (after market close), "TAS" (time not specified)
    
    # Estimates
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None
    
    # Actuals (after release)
    eps_actual: Optional[float] = None
    revenue_actual: Optional[float] = None
    
    # Guidance
    guidance_eps: Optional[float] = None
    guidance_revenue: Optional[float] = None
    
    # Metadata
    fiscal_quarter: str = ""  # e.g., "Q3 2024"
    market_cap: float = 0.0
    sector: str = ""
    
    # Status
    is_confirmed: bool = True
    is_reported: bool = False
    
    @property
    def eps_surprise(self) -> Optional[float]:
        if self.eps_actual is not None and self.eps_estimate is not None:
            return self.eps_actual - self.eps_estimate
        return None
    
    @property
    def eps_surprise_pct(self) -> Optional[float]:
        if self.eps_surprise is not None and self.eps_estimate and self.eps_estimate != 0:
            return (self.eps_surprise / abs(self.eps_estimate)) * 100
        return None
    
    @property
    def revenue_surprise_pct(self) -> Optional[float]:
        if self.revenue_actual and self.revenue_estimate and self.revenue_estimate != 0:
            return ((self.revenue_actual - self.revenue_estimate) / self.revenue_estimate) * 100
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "report_date": self.report_date.isoformat(),
            "report_time": self.report_time,
            "eps_estimate": self.eps_estimate,
            "eps_actual": self.eps_actual,
            "eps_surprise_pct": self.eps_surprise_pct,
            "revenue_estimate": self.revenue_estimate,
            "revenue_actual": self.revenue_actual,
            "revenue_surprise_pct": self.revenue_surprise_pct,
            "fiscal_quarter": self.fiscal_quarter,
            "is_reported": self.is_reported,
        }


@dataclass
class CalendarConfig:
    """Configuration for event calendar."""
    # Lookback/forward
    lookback_days: int = 30
    lookahead_days: int = 30
    
    # Filtering
    min_impact: EventImpact = EventImpact.LOW
    countries: Set[str] = field(default_factory=lambda: {"US"})
    
    # Alerts
    alert_hours_before: List[float] = field(default_factory=lambda: [24, 1, 0.25])


class EventCalendar:
    """
    Manages economic and earnings calendar.
    
    Features:
    - Upcoming event tracking
    - Actual vs estimate comparison
    - Impact assessment
    - Alert generation
    """
    
    def __init__(self, config: Optional[CalendarConfig] = None):
        self.config = config or CalendarConfig()
        
        # Event storage
        self._economic_events: Dict[str, EconomicEvent] = {}
        self._earnings_events: Dict[str, EarningsEvent] = {}
        
        # Indices
        self._by_date: Dict[date, List[str]] = defaultdict(list)
        self._by_type: Dict[EventType, List[str]] = defaultdict(list)
        self._by_symbol: Dict[str, List[str]] = defaultdict(list)
        
        # Known high-impact events
        self._high_impact_types = {
            EventType.FOMC,
            EventType.NFP,
            EventType.CPI,
            EventType.GDP,
            EventType.PCE,
        }
        
    def add_economic_event(self, event: EconomicEvent):
        """Add economic event to calendar."""
        self._economic_events[event.id] = event
        
        event_date = event.datetime_utc.date()
        self._by_date[event_date].append(event.id)
        self._by_type[event.event_type].append(event.id)
        
    def add_earnings_event(self, event: EarningsEvent):
        """Add earnings event to calendar."""
        key = f"{event.symbol}_{event.report_date}"
        self._earnings_events[key] = event
        
        self._by_date[event.report_date].append(key)
        self._by_symbol[event.symbol].append(key)
        self._by_type[EventType.EARNINGS].append(key)
        
    def update_economic_actual(
        self,
        event_id: str,
        actual: float,
    ):
        """Update economic event with actual value."""
        if event_id in self._economic_events:
            event = self._economic_events[event_id]
            event.actual = actual
            event.is_released = True
            event.released_at = datetime.utcnow()
            
    def update_earnings_actual(
        self,
        symbol: str,
        report_date: date,
        eps_actual: Optional[float] = None,
        revenue_actual: Optional[float] = None,
    ):
        """Update earnings event with actuals."""
        key = f"{symbol}_{report_date}"
        if key in self._earnings_events:
            event = self._earnings_events[key]
            if eps_actual is not None:
                event.eps_actual = eps_actual
            if revenue_actual is not None:
                event.revenue_actual = revenue_actual
            event.is_reported = True
            
    def get_events_for_date(
        self,
        event_date: date,
        include_earnings: bool = True,
    ) -> Dict[str, Any]:
        """Get all events for a date."""
        event_ids = self._by_date.get(event_date, [])
        
        economic = []
        earnings = []
        
        for eid in event_ids:
            if eid in self._economic_events:
                economic.append(self._economic_events[eid])
            elif eid in self._earnings_events and include_earnings:
                earnings.append(self._earnings_events[eid])
                
        return {
            "date": event_date.isoformat(),
            "economic": [e.to_dict() for e in economic],
            "earnings": [e.to_dict() for e in earnings],
            "total_count": len(economic) + len(earnings),
        }
    
    def get_upcoming_economic(
        self,
        days: int = 7,
        min_impact: Optional[EventImpact] = None,
        event_types: Optional[Set[EventType]] = None,
    ) -> List[EconomicEvent]:
        """Get upcoming economic events."""
        min_impact = min_impact or self.config.min_impact
        cutoff = datetime.utcnow() + timedelta(days=days)
        
        events = [
            e for e in self._economic_events.values()
            if e.is_upcoming
            and e.datetime_utc <= cutoff
            and e.impact.value >= min_impact.value
            and e.country in self.config.countries
            and (event_types is None or e.event_type in event_types)
        ]
        
        events.sort(key=lambda e: e.datetime_utc)
        return events
    
    def get_upcoming_earnings(
        self,
        days: int = 7,
        symbols: Optional[Set[str]] = None,
        min_market_cap: float = 0,
    ) -> List[EarningsEvent]:
        """Get upcoming earnings events."""
        today = date.today()
        cutoff = today + timedelta(days=days)
        
        events = [
            e for e in self._earnings_events.values()
            if not e.is_reported
            and today <= e.report_date <= cutoff
            and (symbols is None or e.symbol in symbols)
            and e.market_cap >= min_market_cap
        ]
        
        events.sort(key=lambda e: e.report_date)
        return events
    
    def get_symbol_earnings(self, symbol: str) -> List[EarningsEvent]:
        """Get earnings history for symbol."""
        keys = self._by_symbol.get(symbol, [])
        events = [
            self._earnings_events[k]
            for k in keys
            if k in self._earnings_events
        ]
        events.sort(key=lambda e: e.report_date, reverse=True)
        return events
    
    def get_high_impact_events(
        self,
        hours: float = 24,
    ) -> List[EconomicEvent]:
        """Get high-impact events in next N hours."""
        cutoff = datetime.utcnow() + timedelta(hours=hours)
        
        return [
            e for e in self._economic_events.values()
            if e.is_upcoming
            and e.datetime_utc <= cutoff
            and (e.impact in (EventImpact.HIGH, EventImpact.CRITICAL)
                 or e.event_type in self._high_impact_types)
        ]
    
    def get_recent_surprises(
        self,
        days: int = 7,
        min_surprise_pct: float = 0,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get recent economic and earnings surprises."""
        cutoff_date = date.today() - timedelta(days=days)
        
        economic_surprises = []
        for e in self._economic_events.values():
            if e.is_released and e.datetime_utc.date() >= cutoff_date:
                if e.surprise_pct and abs(e.surprise_pct) >= min_surprise_pct:
                    economic_surprises.append({
                        **e.to_dict(),
                        "type": "economic",
                    })
                    
        earnings_surprises = []
        for e in self._earnings_events.values():
            if e.is_reported and e.report_date >= cutoff_date:
                if e.eps_surprise_pct and abs(e.eps_surprise_pct) >= min_surprise_pct:
                    earnings_surprises.append({
                        **e.to_dict(),
                        "type": "earnings",
                    })
                    
        return {
            "economic": sorted(economic_surprises, key=lambda x: abs(x.get("surprise_pct", 0)), reverse=True),
            "earnings": sorted(earnings_surprises, key=lambda x: abs(x.get("eps_surprise_pct", 0)), reverse=True),
        }
    
    def get_week_summary(self, week_start: Optional[date] = None) -> Dict[str, Any]:
        """Get summary of week's events."""
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            
        week_end = week_start + timedelta(days=6)
        
        economic_count = 0
        high_impact_count = 0
        earnings_count = 0
        
        for d in range(7):
            event_date = week_start + timedelta(days=d)
            events = self.get_events_for_date(event_date)
            
            economic_count += len(events["economic"])
            high_impact_count += len([
                e for e in events["economic"]
                if self._economic_events.get(e.get("id", ""), EconomicEvent("", EventType.OTHER, "", datetime.now())).impact.value >= EventImpact.HIGH.value
            ])
            earnings_count += len(events["earnings"])
            
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "economic_events": economic_count,
            "high_impact_events": high_impact_count,
            "earnings_reports": earnings_count,
            "busiest_day": self._find_busiest_day(week_start, week_end),
        }
    
    def _find_busiest_day(self, start: date, end: date) -> str:
        """Find day with most events."""
        max_events = 0
        busiest = start
        
        current = start
        while current <= end:
            count = len(self._by_date.get(current, []))
            if count > max_events:
                max_events = count
                busiest = current
            current += timedelta(days=1)
            
        return busiest.strftime("%A, %B %d")
