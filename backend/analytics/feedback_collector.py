"""
Feedback Collector - User Feedback Loop for Model Improvement

This module collects user feedback on trading signals and trades
to enable continuous model improvement.

Key Features:
- Signal rating collection
- Trade annotation
- Feedback aggregation
- Model weight adjustment based on feedback
- Analytics on feedback patterns

Usage:
    from backend.analytics.feedback_collector import FeedbackCollector

    collector = FeedbackCollector()
    collector.record_signal_feedback(signal_id, rating=4, comment="Good entry")
    adjustments = collector.compute_model_adjustments()
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import numpy as np
import json

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback."""
    SIGNAL_RATING = "signal_rating"
    TRADE_ANNOTATION = "trade_annotation"
    MODEL_PREFERENCE = "model_preference"
    STRATEGY_FEEDBACK = "strategy_feedback"


class SignalOutcome(Enum):
    """Outcome of a signal."""
    PROFITABLE = "profitable"
    LOSS = "loss"
    SCRATCH = "scratch"
    NOT_TAKEN = "not_taken"
    PENDING = "pending"


@dataclass
class SignalFeedback:
    """Feedback on a trading signal."""
    signal_id: str
    timestamp: datetime
    model_name: str
    symbol: str
    signal_value: float
    rating: int  # 1-5
    outcome: SignalOutcome
    comment: Optional[str] = None
    actual_return: Optional[float] = None
    user_id: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'signal_id': self.signal_id,
            'timestamp': self.timestamp.isoformat(),
            'model_name': self.model_name,
            'symbol': self.symbol,
            'signal_value': self.signal_value,
            'rating': self.rating,
            'outcome': self.outcome.value,
            'comment': self.comment,
            'actual_return': self.actual_return,
            'user_id': self.user_id,
        }


@dataclass
class TradeAnnotation:
    """User annotation on a trade."""
    trade_id: str
    timestamp: datetime
    annotation_type: str  # 'entry_quality', 'exit_quality', 'sizing', etc.
    score: int  # 1-5
    notes: str
    tags: List[str] = field(default_factory=list)
    user_id: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'timestamp': self.timestamp.isoformat(),
            'annotation_type': self.annotation_type,
            'score': self.score,
            'notes': self.notes,
            'tags': self.tags,
            'user_id': self.user_id,
        }


@dataclass
class ModelAdjustment:
    """Recommended model adjustment based on feedback."""
    model_name: str
    adjustment_type: str
    current_value: float
    recommended_value: float
    confidence: float
    reason: str
    feedback_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'adjustment_type': self.adjustment_type,
            'current_value': self.current_value,
            'recommended_value': self.recommended_value,
            'confidence': self.confidence,
            'reason': self.reason,
            'feedback_count': self.feedback_count,
        }


class FeedbackCollector:
    """
    Collects and analyzes user feedback for model improvement.

    Aggregates feedback on signals and trades to identify patterns
    and recommend model adjustments.

    Example:
        collector = FeedbackCollector()

        # Record signal feedback
        collector.record_signal_feedback(
            signal_id="SIG-001",
            model_name="momentum_model",
            symbol="AAPL",
            signal_value=0.75,
            rating=4,
            outcome=SignalOutcome.PROFITABLE,
            comment="Good momentum identification"
        )

        # Get model adjustments
        adjustments = collector.compute_model_adjustments()
    """

    def __init__(self, max_history: int = 100000):
        self._signal_feedback: deque = deque(maxlen=max_history)
        self._trade_annotations: deque = deque(maxlen=max_history)

        # Aggregated metrics
        self._model_ratings: Dict[str, List[int]] = defaultdict(list)
        self._symbol_ratings: Dict[str, List[int]] = defaultdict(list)
        self._outcome_counts: Dict[str, Dict[SignalOutcome, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Current model weights (for adjustment)
        self._current_weights: Dict[str, float] = {}

        logger.info("FeedbackCollector initialized")

    def record_signal_feedback(
        self,
        signal_id: str,
        model_name: str,
        symbol: str,
        signal_value: float,
        rating: int,
        outcome: SignalOutcome = SignalOutcome.PENDING,
        comment: Optional[str] = None,
        actual_return: Optional[float] = None,
        user_id: str = "default",
    ) -> SignalFeedback:
        """
        Record feedback on a trading signal.

        Args:
            signal_id: Unique signal identifier
            model_name: Name of the model that generated the signal
            symbol: Trading symbol
            signal_value: Signal value
            rating: User rating (1-5)
            outcome: Signal outcome
            comment: Optional comment
            actual_return: Actual return if known
            user_id: User providing feedback

        Returns:
            SignalFeedback record
        """
        rating = max(1, min(5, rating))

        feedback = SignalFeedback(
            signal_id=signal_id,
            timestamp=datetime.now(timezone.utc),
            model_name=model_name,
            symbol=symbol,
            signal_value=signal_value,
            rating=rating,
            outcome=outcome,
            comment=comment,
            actual_return=actual_return,
            user_id=user_id,
        )

        self._signal_feedback.append(feedback)

        # Update aggregates
        self._model_ratings[model_name].append(rating)
        self._symbol_ratings[symbol].append(rating)
        self._outcome_counts[model_name][outcome] += 1

        logger.debug(f"Recorded signal feedback: {signal_id}, rating={rating}")

        return feedback

    def record_trade_annotation(
        self,
        trade_id: str,
        annotation_type: str,
        score: int,
        notes: str,
        tags: Optional[List[str]] = None,
        user_id: str = "default",
    ) -> TradeAnnotation:
        """
        Record annotation on a trade.

        Args:
            trade_id: Unique trade identifier
            annotation_type: Type of annotation
            score: Score (1-5)
            notes: Annotation notes
            tags: Optional tags
            user_id: User providing annotation

        Returns:
            TradeAnnotation record
        """
        score = max(1, min(5, score))

        annotation = TradeAnnotation(
            trade_id=trade_id,
            timestamp=datetime.now(timezone.utc),
            annotation_type=annotation_type,
            score=score,
            notes=notes,
            tags=tags or [],
            user_id=user_id,
        )

        self._trade_annotations.append(annotation)

        logger.debug(f"Recorded trade annotation: {trade_id}, type={annotation_type}")

        return annotation

    def update_signal_outcome(
        self,
        signal_id: str,
        outcome: SignalOutcome,
        actual_return: Optional[float] = None,
    ) -> bool:
        """
        Update the outcome of a previously recorded signal.

        Args:
            signal_id: Signal identifier
            outcome: Actual outcome
            actual_return: Actual return

        Returns:
            True if signal was found and updated
        """
        for feedback in self._signal_feedback:
            if feedback.signal_id == signal_id:
                old_outcome = feedback.outcome
                feedback.outcome = outcome
                feedback.actual_return = actual_return

                # Update outcome counts
                self._outcome_counts[feedback.model_name][old_outcome] -= 1
                self._outcome_counts[feedback.model_name][outcome] += 1

                return True

        return False

    def set_model_weights(self, weights: Dict[str, float]) -> None:
        """Set current model weights for adjustment computation."""
        self._current_weights = weights.copy()

    def compute_model_adjustments(
        self,
        lookback_days: int = 30,
        min_feedback_count: int = 10,
    ) -> List[ModelAdjustment]:
        """
        Compute recommended model adjustments based on feedback.

        Args:
            lookback_days: Period to analyze
            min_feedback_count: Minimum feedback count for adjustment

        Returns:
            List of ModelAdjustment recommendations
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Get recent feedback
        recent_feedback = [
            f for f in self._signal_feedback
            if f.timestamp >= cutoff
        ]

        if len(recent_feedback) < min_feedback_count:
            return []

        # Group by model
        model_feedback: Dict[str, List[SignalFeedback]] = defaultdict(list)
        for f in recent_feedback:
            model_feedback[f.model_name].append(f)

        adjustments = []

        for model_name, feedback_list in model_feedback.items():
            if len(feedback_list) < min_feedback_count:
                continue

            # Compute metrics
            avg_rating = np.mean([f.rating for f in feedback_list])
            profitable_count = sum(
                1 for f in feedback_list
                if f.outcome == SignalOutcome.PROFITABLE
            )
            total_with_outcome = sum(
                1 for f in feedback_list
                if f.outcome in (SignalOutcome.PROFITABLE, SignalOutcome.LOSS)
            )

            win_rate = profitable_count / total_with_outcome if total_with_outcome > 0 else 0.5

            # Compute adjustment
            current_weight = self._current_weights.get(model_name, 1.0)

            # Adjustment based on rating and win rate
            rating_factor = (avg_rating - 3) / 2  # -1 to +1
            winrate_factor = (win_rate - 0.5) * 2  # -1 to +1

            adjustment_factor = (rating_factor + winrate_factor) / 2
            recommended_weight = current_weight * (1 + adjustment_factor * 0.2)
            recommended_weight = max(0.1, min(2.0, recommended_weight))

            # Only suggest if significant
            if abs(recommended_weight - current_weight) > 0.05:
                reason = []
                if avg_rating > 3.5:
                    reason.append(f"high user rating ({avg_rating:.1f})")
                elif avg_rating < 2.5:
                    reason.append(f"low user rating ({avg_rating:.1f})")

                if win_rate > 0.6:
                    reason.append(f"high win rate ({win_rate:.1%})")
                elif win_rate < 0.4:
                    reason.append(f"low win rate ({win_rate:.1%})")

                adjustments.append(ModelAdjustment(
                    model_name=model_name,
                    adjustment_type='weight',
                    current_value=current_weight,
                    recommended_value=recommended_weight,
                    confidence=min(1.0, len(feedback_list) / 50),
                    reason=', '.join(reason) if reason else 'performance-based',
                    feedback_count=len(feedback_list),
                ))

        return adjustments

    def get_model_metrics(
        self,
        model_name: str,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for a model.

        Args:
            model_name: Model name
            lookback_days: Analysis period

        Returns:
            Dictionary of metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        feedback = [
            f for f in self._signal_feedback
            if f.model_name == model_name and f.timestamp >= cutoff
        ]

        if not feedback:
            return {
                'model_name': model_name,
                'feedback_count': 0,
            }

        ratings = [f.rating for f in feedback]
        outcomes = [f.outcome for f in feedback]
        returns = [f.actual_return for f in feedback if f.actual_return is not None]

        profitable = sum(1 for o in outcomes if o == SignalOutcome.PROFITABLE)
        loss = sum(1 for o in outcomes if o == SignalOutcome.LOSS)

        return {
            'model_name': model_name,
            'feedback_count': len(feedback),
            'avg_rating': np.mean(ratings),
            'rating_std': np.std(ratings),
            'profitable_signals': profitable,
            'loss_signals': loss,
            'win_rate': profitable / (profitable + loss) if (profitable + loss) > 0 else None,
            'avg_return': np.mean(returns) if returns else None,
            'total_return': sum(returns) if returns else None,
        }

    def get_symbol_metrics(
        self,
        symbol: str,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for a symbol.

        Args:
            symbol: Trading symbol
            lookback_days: Analysis period

        Returns:
            Dictionary of metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        feedback = [
            f for f in self._signal_feedback
            if f.symbol == symbol and f.timestamp >= cutoff
        ]

        if not feedback:
            return {
                'symbol': symbol,
                'feedback_count': 0,
            }

        ratings = [f.rating for f in feedback]
        models_used = list(set(f.model_name for f in feedback))

        return {
            'symbol': symbol,
            'feedback_count': len(feedback),
            'avg_rating': np.mean(ratings),
            'models_used': models_used,
        }

    def get_feedback_trends(
        self,
        lookback_days: int = 30,
        granularity: str = 'daily',
    ) -> Dict[str, Any]:
        """
        Get feedback trends over time.

        Args:
            lookback_days: Analysis period
            granularity: 'daily' or 'weekly'

        Returns:
            Dictionary with trend data
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        feedback = [
            f for f in self._signal_feedback
            if f.timestamp >= cutoff
        ]

        if not feedback:
            return {'period_days': lookback_days, 'data': []}

        # Group by period
        if granularity == 'weekly':
            key_func = lambda f: f.timestamp.strftime('%Y-W%W')
        else:
            key_func = lambda f: f.timestamp.strftime('%Y-%m-%d')

        grouped = defaultdict(list)
        for f in feedback:
            grouped[key_func(f)].append(f)

        data = []
        for period, period_feedback in sorted(grouped.items()):
            data.append({
                'period': period,
                'count': len(period_feedback),
                'avg_rating': np.mean([f.rating for f in period_feedback]),
            })

        return {
            'period_days': lookback_days,
            'granularity': granularity,
            'data': data,
        }

    def get_common_issues(
        self,
        lookback_days: int = 30,
        min_count: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Identify common issues from feedback comments.

        Args:
            lookback_days: Analysis period
            min_count: Minimum mentions

        Returns:
            List of common issues
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Get low-rated feedback with comments
        low_rated = [
            f for f in self._signal_feedback
            if f.timestamp >= cutoff and f.rating <= 2 and f.comment
        ]

        # Simple keyword extraction
        keywords = defaultdict(int)
        issue_keywords = [
            'late', 'early', 'false', 'missed', 'wrong', 'bad',
            'timing', 'size', 'risk', 'volatility', 'trend'
        ]

        for f in low_rated:
            comment_lower = f.comment.lower()
            for keyword in issue_keywords:
                if keyword in comment_lower:
                    keywords[keyword] += 1

        issues = [
            {'keyword': k, 'count': v, 'severity': 'high' if v >= min_count * 2 else 'medium'}
            for k, v in sorted(keywords.items(), key=lambda x: x[1], reverse=True)
            if v >= min_count
        ]

        return issues

    def export_feedback(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Export feedback data.

        Args:
            start_time: Start of export period
            end_time: End of export period

        Returns:
            Dictionary with all feedback data
        """
        signal_data = list(self._signal_feedback)
        trade_data = list(self._trade_annotations)

        if start_time:
            signal_data = [f for f in signal_data if f.timestamp >= start_time]
            trade_data = [a for a in trade_data if a.timestamp >= start_time]

        if end_time:
            signal_data = [f for f in signal_data if f.timestamp <= end_time]
            trade_data = [a for a in trade_data if a.timestamp <= end_time]

        return {
            'export_time': datetime.now(timezone.utc).isoformat(),
            'signal_feedback': [f.to_dict() for f in signal_data],
            'trade_annotations': [a.to_dict() for a in trade_data],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            'total_signal_feedback': len(self._signal_feedback),
            'total_trade_annotations': len(self._trade_annotations),
            'models_tracked': len(self._model_ratings),
            'symbols_tracked': len(self._symbol_ratings),
        }
