"""
News & Event-Driven Alpha Module
================================
Captures alpha from news, events, and macro announcements.

Components:
- news_feed: Multi-source news aggregation
- sentiment_analyzer: NLP sentiment extraction
- event_calendar: Economic and earnings calendar
- event_signals: Event-based trading signals
- headline_parser: Fast headline parsing for trading
"""

from .news_feed import (
    NewsFeed,
    NewsArticle,
    NewsSource,
    NewsCategory,
)
from .sentiment_analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    EntitySentiment,
)
from .event_calendar import (
    EventCalendar,
    EconomicEvent,
    EarningsEvent,
    EventType,
    EventImpact,
)
from .event_signals import (
    EventSignalGenerator,
    EventSignal,
    SignalType,
)
from .headline_parser import (
    HeadlineParser,
    ParsedHeadline,
    HeadlineAction,
)

__all__ = [
    "NewsFeed",
    "NewsArticle",
    "NewsSource",
    "NewsCategory",
    "SentimentAnalyzer",
    "SentimentResult",
    "EntitySentiment",
    "EventCalendar",
    "EconomicEvent",
    "EarningsEvent",
    "EventType",
    "EventImpact",
    "EventSignalGenerator",
    "EventSignal",
    "SignalType",
    "HeadlineParser",
    "ParsedHeadline",
    "HeadlineAction",
]

__version__ = "1.0.0"
