"""
Signals Module - News Sentiment and Signal Generation
QUANT_INDUSTRY_V1
"""

from .news_sentiment import (
    NewsSentimentEngine,
    NewsArticle,
    SentimentSignal,
    SentimentLabel,
    EventType,
    EventDetector,
    SymbolExtractor,
    RuleBasedSentimentAnalyzer
)

# Optional transformer analyzer
try:
    from .news_sentiment import TransformerSentimentAnalyzer
    TRANSFORMER_AVAILABLE = True
except ImportError:
    TRANSFORMER_AVAILABLE = False

__all__ = [
    'NewsSentimentEngine',
    'NewsArticle',
    'SentimentSignal',
    'SentimentLabel',
    'EventType',
    'EventDetector',
    'SymbolExtractor',
    'RuleBasedSentimentAnalyzer',
    'TRANSFORMER_AVAILABLE',
]
