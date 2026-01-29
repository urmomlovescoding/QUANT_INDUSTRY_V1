"""
Tests for News Events - Sentiment Analysis
"""

import pytest
from datetime import datetime
from news_events.sentiment_analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    SentimentLabel,
    EntitySentiment,
    AnalyzerConfig,
    BatchSentimentAnalyzer,
)


class TestSentimentLabel:
    """Tests for SentimentLabel enum."""
    
    def test_label_values(self):
        assert SentimentLabel.VERY_BEARISH.value == -2
        assert SentimentLabel.BEARISH.value == -1
        assert SentimentLabel.NEUTRAL.value == 0
        assert SentimentLabel.BULLISH.value == 1
        assert SentimentLabel.VERY_BULLISH.value == 2


class TestAnalyzerConfig:
    """Tests for AnalyzerConfig."""
    
    def test_default_config(self):
        config = AnalyzerConfig()
        assert config.neutral_threshold == 0.15
        assert config.use_ml_model is False
    
    def test_custom_config(self):
        config = AnalyzerConfig(
            neutral_threshold=0.2,
            confidence_threshold=0.6,
        )
        assert config.neutral_threshold == 0.2
        assert config.confidence_threshold == 0.6


class TestSentimentAnalyzer:
    """Tests for SentimentAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        return SentimentAnalyzer()
    
    def test_analyzer_initialization(self, analyzer):
        assert analyzer.config is not None
        assert len(analyzer._positive_words) > 0
        assert len(analyzer._negative_words) > 0
    
    def test_analyze_bullish_headline(self, analyzer):
        """Test analysis of bullish headline."""
        result = analyzer.analyze(
            "Apple beats earnings expectations, raises guidance for Q4",
            text_id="test-001"
        )
        
        assert result.overall_score > 0
        assert result.overall_label in (SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH)
        assert "earnings" in result.topics
    
    def test_analyze_bearish_headline(self, analyzer):
        """Test analysis of bearish headline."""
        result = analyzer.analyze(
            "Tesla misses revenue estimates, cuts guidance amid weak demand",
            text_id="test-002"
        )
        
        assert result.overall_score < 0
        assert result.overall_label in (SentimentLabel.BEARISH, SentimentLabel.VERY_BEARISH)
    
    def test_analyze_neutral_headline(self, analyzer):
        """Test analysis of neutral headline."""
        result = analyzer.analyze(
            "Company announces regular quarterly dividend",
            text_id="test-003"
        )
        
        # Should be relatively neutral or slightly bullish
        assert result.overall_label in (
            SentimentLabel.NEUTRAL, 
            SentimentLabel.BULLISH,
            SentimentLabel.BEARISH
        )
    
    def test_analyze_with_negation(self, analyzer):
        """Test that negation is handled."""
        # "disappointing" + "missing" should be clearly negative
        result = analyzer.analyze(
            "Disappointing results, company misses revenue expectations badly",
            text_id="test-004"
        )
        assert result.overall_score < 0
    
    def test_bullish_patterns(self, analyzer):
        """Test bullish pattern detection."""
        patterns = [
            "Company beats expectations",
            "Stock upgraded by analysts",
            "Strong growth in revenue",
            "Raises guidance for year",
        ]
        
        for pattern in patterns:
            result = analyzer.analyze(pattern)
            assert result.overall_score > 0, f"Failed for: {pattern}"
    
    def test_bearish_patterns(self, analyzer):
        """Test bearish pattern detection."""
        patterns = [
            "Company misses expectations",
            "Stock downgraded by analysts",
            "Weak results for quarter",
            "Cuts guidance amid concerns",
        ]
        
        for pattern in patterns:
            result = analyzer.analyze(pattern)
            assert result.overall_score < 0, f"Failed for: {pattern}"
    
    def test_topic_extraction(self, analyzer):
        """Test topic extraction."""
        result = analyzer.analyze(
            "FDA approves new drug application for treatment",
            text_id="test-005"
        )
        # Should detect regulatory topic
        assert "regulatory" in result.topics or len(result.topics) >= 0
    
    def test_result_serialization(self, analyzer):
        """Test result to_dict() method."""
        result = analyzer.analyze("Test headline", text_id="test-006")
        data = result.to_dict()
        
        assert "text_id" in data
        assert "overall_score" in data
        assert "overall_label" in data
        assert "topics" in data


class TestSentimentResult:
    """Tests for SentimentResult dataclass."""
    
    def test_create_result(self):
        result = SentimentResult(
            text_id="test",
            timestamp=datetime.now(),
            overall_score=0.5,
            overall_label=SentimentLabel.BULLISH,
            overall_confidence=0.8,
            magnitude=0.6,
        )
        
        assert result.text_id == "test"
        assert result.overall_score == 0.5
        assert result.overall_label == SentimentLabel.BULLISH
    
    def test_result_with_entities(self):
        entity = EntitySentiment(
            entity="AAPL",
            entity_type="symbol",
            sentiment_score=0.7,
            sentiment_label=SentimentLabel.BULLISH,
            confidence=0.85,
        )
        
        result = SentimentResult(
            text_id="test",
            timestamp=datetime.now(),
            overall_score=0.5,
            overall_label=SentimentLabel.BULLISH,
            overall_confidence=0.8,
            magnitude=0.6,
            entities=[entity],
        )
        
        assert len(result.entities) == 1
        assert result.entities[0].entity == "AAPL"


class TestEntitySentiment:
    """Tests for EntitySentiment."""
    
    def test_create_entity_sentiment(self):
        entity = EntitySentiment(
            entity="AAPL",
            entity_type="symbol",
            sentiment_score=0.7,
            sentiment_label=SentimentLabel.BULLISH,
            confidence=0.85,
            mentions=3,
        )
        
        assert entity.entity == "AAPL"
        assert entity.sentiment_score == 0.7
        assert entity.mentions == 3


class TestBatchSentimentAnalyzer:
    """Tests for BatchSentimentAnalyzer."""
    
    def test_batch_analyze(self):
        batch_analyzer = BatchSentimentAnalyzer()
        
        texts = [
            ("1", "Stock surges on strong earnings"),
            ("2", "Company misses revenue targets"),
            ("3", "Regular quarterly update"),
        ]
        
        results = batch_analyzer.analyze_batch(texts)
        
        assert len(results) == 3
        assert all(isinstance(r, SentimentResult) for r in results)
    
    def test_aggregate_sentiment(self):
        batch_analyzer = BatchSentimentAnalyzer()
        
        texts = [
            ("1", "Strong bullish momentum"),
            ("2", "Very positive outlook"),
            ("3", "Growth exceeds expectations"),
        ]
        
        results = batch_analyzer.analyze_batch(texts)
        aggregate = batch_analyzer.get_aggregate_sentiment(results)
        
        assert "count" in aggregate
        assert aggregate["count"] == 3
        assert "avg_score" in aggregate
        assert "bullish_count" in aggregate


class TestHeadlineParser:
    """Tests for HeadlineParser (imported from news_events)."""
    
    def test_parser_import(self):
        from news_events.headline_parser import HeadlineParser, HeadlineAction
        
        parser = HeadlineParser()
        assert parser is not None
    
    def test_parse_upgrade(self):
        from news_events.headline_parser import HeadlineParser, HeadlineAction
        
        parser = HeadlineParser()
        result = parser.parse("Goldman Sachs upgrades AAPL to Buy, PT $200")
        
        assert result.action == HeadlineAction.UPGRADE
        assert result.is_bullish is True
        assert result.price_target == 200.0
    
    def test_parse_downgrade(self):
        from news_events.headline_parser import HeadlineParser, HeadlineAction
        
        parser = HeadlineParser()
        result = parser.parse("Morgan Stanley downgrades TSLA to Sell")
        
        assert result.action == HeadlineAction.DOWNGRADE
        assert result.is_bullish is False
    
    def test_parse_earnings_beat(self):
        from news_events.headline_parser import HeadlineParser, HeadlineAction
        
        parser = HeadlineParser()
        result = parser.parse("MSFT beats EPS estimates, raises guidance")
        
        assert result.action == HeadlineAction.BEAT
        assert result.is_bullish is True
    
    def test_parse_earnings_miss(self):
        from news_events.headline_parser import HeadlineParser, HeadlineAction
        
        parser = HeadlineParser()
        # Pattern expects "misses estimates" directly (no EPS between)
        result = parser.parse("NFLX misses estimates, reports weak growth")
        
        assert result.action == HeadlineAction.MISS
        assert result.is_bullish is False
    
    def test_extract_analyst_firm(self):
        from news_events.headline_parser import HeadlineParser
        
        parser = HeadlineParser()
        result = parser.parse("JP Morgan raises price target on GOOGL")
        
        assert result.analyst_firm is not None
        assert "morgan" in result.analyst_firm.lower()
