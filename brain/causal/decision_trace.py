"""
Decision Trace - Decision Explanation and Audit Trail

This module provides explainability for trading decisions,
creating an audit trail of why each decision was made.

Key Features:
- Decision attribution
- Feature contribution analysis
- Natural language explanations
- Audit trail storage
- Counterfactual explanations

Usage:
    from brain.causal.decision_trace import DecisionTracer

    tracer = DecisionTracer()
    explanation = tracer.explain_decision(signal, features, model)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureContribution:
    """Contribution of a feature to a decision."""
    feature_name: str
    value: float
    contribution: float  # Contribution to signal
    importance_rank: int
    direction: str  # 'positive', 'negative', 'neutral'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature_name': self.feature_name,
            'value': self.value,
            'contribution': self.contribution,
            'importance_rank': self.importance_rank,
            'direction': self.direction,
        }


@dataclass
class DecisionExplanation:
    """Complete explanation for a trading decision."""
    timestamp: datetime
    decision_id: str
    signal: float
    signal_type: str  # 'buy', 'sell', 'hold'
    confidence: float
    feature_contributions: List[FeatureContribution]
    top_reasons: List[str]
    counterfactuals: List[Dict[str, Any]]
    model_name: str
    market_context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'decision_id': self.decision_id,
            'signal': self.signal,
            'signal_type': self.signal_type,
            'confidence': self.confidence,
            'feature_contributions': [f.to_dict() for f in self.feature_contributions],
            'top_reasons': self.top_reasons,
            'counterfactuals': self.counterfactuals,
            'model_name': self.model_name,
            'market_context': self.market_context,
        }

    def get_natural_language_explanation(self) -> str:
        """Generate natural language explanation."""
        if not self.top_reasons:
            return f"Signal: {self.signal:.3f} ({self.signal_type})"

        explanation_parts = [
            f"Decision: {self.signal_type.upper()} with confidence {self.confidence:.1%}",
            "",
            "Key factors:",
        ]

        for i, reason in enumerate(self.top_reasons[:5], 1):
            explanation_parts.append(f"  {i}. {reason}")

        if self.counterfactuals:
            explanation_parts.append("")
            explanation_parts.append("Alternative scenarios:")
            for cf in self.counterfactuals[:2]:
                explanation_parts.append(f"  - {cf.get('description', 'N/A')}")

        return "\n".join(explanation_parts)


@dataclass
class AuditRecord:
    """Audit record for regulatory compliance."""
    decision_id: str
    timestamp: datetime
    symbol: str
    decision_type: str
    signal_value: float
    executed: bool
    model_version: str
    feature_hash: str
    explanation_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision_id': self.decision_id,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'decision_type': self.decision_type,
            'signal_value': self.signal_value,
            'executed': self.executed,
            'model_version': self.model_version,
            'feature_hash': self.feature_hash,
            'explanation_summary': self.explanation_summary,
        }


class DecisionTracer:
    """
    Traces and explains trading decisions for transparency.

    Provides feature attribution, counterfactual analysis,
    and audit trails for regulatory compliance.

    Example:
        tracer = DecisionTracer()

        # Explain a decision
        explanation = tracer.explain_decision(
            signal=0.75,
            features={'momentum': 0.8, 'volatility': 0.3},
            feature_importance={'momentum': 0.6, 'volatility': 0.4}
        )

        # Get natural language explanation
        print(explanation.get_natural_language_explanation())

        # Store audit record
        tracer.record_audit(explanation, symbol='AAPL', executed=True)
    """

    def __init__(self, max_history: int = 10000):
        self._explanations: deque = deque(maxlen=max_history)
        self._audit_trail: deque = deque(maxlen=max_history)
        self._decision_counter = 0

        logger.info("DecisionTracer initialized")

    def explain_decision(
        self,
        signal: float,
        features: Dict[str, float],
        feature_importance: Optional[Dict[str, float]] = None,
        model_name: str = "unknown",
        market_context: Optional[Dict[str, Any]] = None,
    ) -> DecisionExplanation:
        """
        Generate explanation for a trading decision.

        Args:
            signal: Trading signal value
            features: Feature values used
            feature_importance: Feature importance scores
            model_name: Name of the model
            market_context: Additional market context

        Returns:
            DecisionExplanation with full explanation
        """
        self._decision_counter += 1
        decision_id = f"DEC-{datetime.now().strftime('%Y%m%d')}-{self._decision_counter:06d}"

        # Determine signal type
        if signal > 0.3:
            signal_type = 'buy'
        elif signal < -0.3:
            signal_type = 'sell'
        else:
            signal_type = 'hold'

        # Compute confidence
        confidence = min(1.0, abs(signal))

        # Compute feature contributions
        contributions = self._compute_contributions(
            features, feature_importance, signal
        )

        # Generate reasons
        top_reasons = self._generate_reasons(contributions, signal_type)

        # Generate counterfactuals
        counterfactuals = self._generate_counterfactuals(
            features, feature_importance, signal, signal_type
        )

        explanation = DecisionExplanation(
            timestamp=datetime.now(timezone.utc),
            decision_id=decision_id,
            signal=signal,
            signal_type=signal_type,
            confidence=confidence,
            feature_contributions=contributions,
            top_reasons=top_reasons,
            counterfactuals=counterfactuals,
            model_name=model_name,
            market_context=market_context or {},
        )

        self._explanations.append(explanation)

        return explanation

    def _compute_contributions(
        self,
        features: Dict[str, float],
        feature_importance: Optional[Dict[str, float]],
        signal: float,
    ) -> List[FeatureContribution]:
        """Compute feature contributions to signal."""
        if feature_importance is None:
            # Equal importance
            feature_importance = {k: 1.0 / len(features) for k in features}

        contributions = []
        total_importance = sum(feature_importance.values())

        for i, (name, value) in enumerate(features.items()):
            importance = feature_importance.get(name, 0.0) / total_importance
            contribution = value * importance * np.sign(signal)

            if contribution > 0.01:
                direction = 'positive'
            elif contribution < -0.01:
                direction = 'negative'
            else:
                direction = 'neutral'

            contributions.append(FeatureContribution(
                feature_name=name,
                value=value,
                contribution=contribution,
                importance_rank=0,  # Set later
                direction=direction,
            ))

        # Sort by absolute contribution and set ranks
        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        for i, c in enumerate(contributions):
            c.importance_rank = i + 1

        return contributions

    def _generate_reasons(
        self,
        contributions: List[FeatureContribution],
        signal_type: str,
    ) -> List[str]:
        """Generate natural language reasons."""
        reasons = []

        for c in contributions[:5]:
            if c.direction == 'positive':
                if signal_type == 'buy':
                    reasons.append(
                        f"Strong {c.feature_name} ({c.value:.2f}) supports buying"
                    )
                else:
                    reasons.append(
                        f"Strong {c.feature_name} ({c.value:.2f}) suggests upside potential"
                    )
            elif c.direction == 'negative':
                if signal_type == 'sell':
                    reasons.append(
                        f"Weak {c.feature_name} ({c.value:.2f}) supports selling"
                    )
                else:
                    reasons.append(
                        f"Weak {c.feature_name} ({c.value:.2f}) presents risk"
                    )
            else:
                reasons.append(
                    f"Neutral {c.feature_name} ({c.value:.2f}) has minimal impact"
                )

        return reasons

    def _generate_counterfactuals(
        self,
        features: Dict[str, float],
        feature_importance: Optional[Dict[str, float]],
        signal: float,
        signal_type: str,
    ) -> List[Dict[str, Any]]:
        """Generate counterfactual explanations."""
        counterfactuals = []

        if feature_importance is None:
            return counterfactuals

        # Sort features by importance
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for feat_name, importance in sorted_features[:3]:
            if feat_name not in features:
                continue

            current_value = features[feat_name]

            # What if this feature was different?
            if signal_type == 'buy':
                alt_value = current_value * 0.5
                description = (
                    f"If {feat_name} were {alt_value:.2f} instead of {current_value:.2f}, "
                    f"signal would likely be weaker"
                )
            else:
                alt_value = current_value * 1.5
                description = (
                    f"If {feat_name} were {alt_value:.2f} instead of {current_value:.2f}, "
                    f"signal might be more positive"
                )

            counterfactuals.append({
                'feature': feat_name,
                'actual_value': current_value,
                'counterfactual_value': alt_value,
                'description': description,
                'importance': importance,
            })

        return counterfactuals

    def record_audit(
        self,
        explanation: DecisionExplanation,
        symbol: str,
        executed: bool,
        model_version: str = "1.0",
    ) -> AuditRecord:
        """
        Record decision for audit trail.

        Args:
            explanation: Decision explanation
            symbol: Trading symbol
            executed: Whether trade was executed
            model_version: Model version

        Returns:
            AuditRecord for compliance
        """
        import hashlib

        # Create feature hash for reproducibility
        feature_str = str(sorted(explanation.market_context.items()))
        feature_hash = hashlib.md5(feature_str.encode()).hexdigest()[:16]

        # Create summary
        summary = f"{explanation.signal_type.upper()} signal ({explanation.signal:.3f})"
        if explanation.top_reasons:
            summary += f" - {explanation.top_reasons[0]}"

        record = AuditRecord(
            decision_id=explanation.decision_id,
            timestamp=explanation.timestamp,
            symbol=symbol,
            decision_type=explanation.signal_type,
            signal_value=explanation.signal,
            executed=executed,
            model_version=model_version,
            feature_hash=feature_hash,
            explanation_summary=summary,
        )

        self._audit_trail.append(record)

        return record

    def get_explanation(self, decision_id: str) -> Optional[DecisionExplanation]:
        """Retrieve explanation by decision ID."""
        for exp in self._explanations:
            if exp.decision_id == decision_id:
                return exp
        return None

    def get_audit_trail(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """
        Get audit trail with optional filters.

        Args:
            symbol: Filter by symbol
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum records to return

        Returns:
            List of AuditRecords
        """
        records = list(self._audit_trail)

        if symbol:
            records = [r for r in records if r.symbol == symbol]

        if start_time:
            records = [r for r in records if r.timestamp >= start_time]

        if end_time:
            records = [r for r in records if r.timestamp <= end_time]

        return records[-limit:]

    def get_decision_summary(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get summary of decisions in time period.

        Args:
            hours: Lookback period in hours

        Returns:
            Summary statistics
        """
        cutoff = datetime.now(timezone.utc) - pd.Timedelta(hours=hours)

        recent = [e for e in self._explanations if e.timestamp >= cutoff]

        if not recent:
            return {
                'period_hours': hours,
                'total_decisions': 0,
            }

        buy_count = sum(1 for e in recent if e.signal_type == 'buy')
        sell_count = sum(1 for e in recent if e.signal_type == 'sell')
        hold_count = sum(1 for e in recent if e.signal_type == 'hold')

        avg_confidence = np.mean([e.confidence for e in recent])

        # Top contributing features
        all_contributions = []
        for e in recent:
            all_contributions.extend(e.feature_contributions)

        feature_impact = {}
        for c in all_contributions:
            if c.feature_name not in feature_impact:
                feature_impact[c.feature_name] = []
            feature_impact[c.feature_name].append(abs(c.contribution))

        top_features = sorted(
            [(k, np.mean(v)) for k, v in feature_impact.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            'period_hours': hours,
            'total_decisions': len(recent),
            'buy_signals': buy_count,
            'sell_signals': sell_count,
            'hold_signals': hold_count,
            'avg_confidence': avg_confidence,
            'top_features': dict(top_features),
        }

    def export_audit_report(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """
        Export audit report for compliance.

        Args:
            start_time: Report start time
            end_time: Report end time

        Returns:
            Complete audit report
        """
        records = self.get_audit_trail(
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )

        return {
            'report_generated': datetime.now(timezone.utc).isoformat(),
            'period_start': start_time.isoformat(),
            'period_end': end_time.isoformat(),
            'total_decisions': len(records),
            'decisions_executed': sum(1 for r in records if r.executed),
            'decisions_not_executed': sum(1 for r in records if not r.executed),
            'records': [r.to_dict() for r in records],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics."""
        return {
            'total_explanations': len(self._explanations),
            'total_audit_records': len(self._audit_trail),
            'decisions_today': self._decision_counter,
        }
