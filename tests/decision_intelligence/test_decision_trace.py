"""
Tests for Decision Trace
"""

import pytest
from datetime import datetime, timedelta
import sys
import os
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.decision_trace import (
    DecisionTrace,
    TraceNode as DecisionNode,
    TraceEdge as DecisionEdge,
    NodeType,
    get_decision_trace,
)


@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    import uuid
    test_db = tmp_path / f"test_trace_{uuid.uuid4().hex[:8]}.db"
    # Monkeypatch the default db_path
    original_init = DecisionTrace.__init__
    def patched_init(self, db_path=None):
        original_init(self, db_path=test_db)
    monkeypatch.setattr(DecisionTrace, "__init__", patched_init)
    yield
    # Cleanup happens automatically when tmp_path is cleaned


class TestDecisionNode:
    """Test DecisionNode dataclass."""
    
    def test_create_node(self):
        """Should create decision node."""
        node = DecisionNode(
            node_id="test_1",
            node_type=NodeType.SIGNAL,
            timestamp=datetime.now(),
            component="regime_detector",
            decision="BULL_REGIME",
            reason="Strong momentum detected",
            data={"price": 100.0, "regime": "bull"},
        )
        
        assert node.node_id == "test_1"
        assert node.component == "regime_detector"
        assert node.decision == "BULL_REGIME"
    
    def test_node_to_dict(self):
        """Should convert to dictionary."""
        node = DecisionNode(
            node_id="test_2",
            node_type=NodeType.SIGNAL,
            timestamp=datetime.now(),
            component="signal_generator",
            decision="LONG_SIGNAL",
            reason="ICT setup detected",
            data={"signal": "LONG"},
        )
        
        d = node.to_dict()
        assert d["node_id"] == "test_2"
        assert d["component"] == "signal_generator"
        assert "timestamp" in d


class TestDecisionTraceBasics:
    """Test basic decision trace functionality."""
    
    def test_singleton(self):
        """Should be a singleton via get_decision_trace()."""
        trace1 = get_decision_trace()
        trace2 = get_decision_trace()
        assert trace1 is trace2
    
    def test_add_decision(self):
        """Should add decision nodes."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        node_id = trace.add_decision(
            context_id="ctx_test",
            component="test_component",
            decision="TEST_DECISION",
            inputs={"x": 1},
            outputs={"y": 2},
            confidence=0.9,
        )
        
        assert node_id is not None
        assert trace.graph.has_node(node_id)
    
    def test_add_edge(self):
        """Should connect decision nodes."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        node1 = trace.add_decision(
            context_id="ctx_edge",
            component="component_1",
            decision="DECISION_1",
        )
        
        node2 = trace.add_decision(
            context_id="ctx_edge",
            component="component_2",
            decision="DECISION_2",
        )
        
        trace.add_edge(
            from_node=node1,
            to_node=node2,
            relationship="triggers",
            weight=1.0,
        )
        
        assert trace.graph.has_edge(node1, node2)


class TestDecisionPath:
    """Test decision path retrieval."""
    
    def test_get_decision_path(self):
        """Should retrieve full decision path."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        # Create a decision chain
        ctx = "ctx_path_test"
        
        n1 = trace.add_decision(ctx, "regime", "BULL")
        n2 = trace.add_decision(ctx, "signal", "LONG")
        n3 = trace.add_decision(ctx, "risk", "APPROVED")
        n4 = trace.add_decision(ctx, "execution", "FILLED")
        
        trace.add_edge(n1, n2, "triggers")
        trace.add_edge(n2, n3, "triggers")
        trace.add_edge(n3, n4, "triggers")
        
        path = trace.get_decision_path(ctx)
        
        assert len(path) == 4
        # Path should be in order
        components = [n["component"] for n in path]
        assert "regime" in components
        assert "execution" in components
    
    def test_empty_path(self):
        """Should handle missing context."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        path = trace.get_decision_path("nonexistent")
        assert path == []


class TestOutcomeTracking:
    """Test outcome tracking."""
    
    def test_record_outcome(self):
        """Should record outcome for decision."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        node_id = trace.add_decision(
            context_id="ctx_outcome",
            component="strategy",
            decision="ENTER_LONG",
        )
        
        trace.record_outcome(
            node_id=node_id,
            outcome="profit",
            realized_pnl=150.0,
            notes="Good trade",
        )
        
        node_data = trace.graph.nodes[node_id]
        assert node_data["outcome"] == "profit"
        assert node_data["realized_pnl"] == 150.0
    
    def test_outcome_distribution(self):
        """Should track outcome distribution."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        # Add some decisions with outcomes
        for i, outcome in enumerate(["profit", "profit", "loss", "profit"]):
            node_id = trace.add_decision(
                context_id=f"ctx_dist_{i}",
                component="strategy",
                decision="TRADE",
                outcome=outcome,
            )
        
        stats = trace.get_stats()
        assert stats["outcomes"]["profit"] == 3
        assert stats["outcomes"]["loss"] == 1


class TestPatternAnalysis:
    """Test pattern analysis."""
    
    def test_failure_patterns(self):
        """Should analyze failure patterns."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        # Add failing decisions with common characteristics
        for i in range(5):
            trace.add_decision(
                context_id=f"ctx_fail_{i}",
                component="momentum_strategy",
                decision="ENTER_LONG",
                metadata={
                    "regime": "volatile",
                    "confidence": 0.5 + i * 0.05,
                    "symbol": "TSLA",
                },
                outcome="loss",
            )
        
        patterns = trace.analyze_failure_patterns(lookback_days=30)
        
        # Should identify momentum_strategy as problematic
        assert len(patterns) > 0
        # Component should be identified
        assert any("momentum_strategy" in str(p) for p in patterns)
    
    def test_success_patterns(self):
        """Should analyze success patterns."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        # Add successful decisions
        for i in range(10):
            trace.add_decision(
                context_id=f"ctx_success_{i}",
                component="trend_strategy",
                decision="ENTER_LONG",
                metadata={
                    "regime": "trending_bull",
                    "confidence": 0.8 + i * 0.01,
                },
                outcome="profit",
            )
        
        patterns = trace.analyze_success_patterns(lookback_days=30)
        
        # Should identify trend_strategy as successful
        assert len(patterns) > 0


class TestQueries:
    """Test decision queries."""
    
    def test_query_by_symbol(self):
        """Should query by symbol."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        trace.add_decision("ctx_1", "s1", "D1", metadata={"symbol": "AAPL"})
        trace.add_decision("ctx_2", "s1", "D2", metadata={"symbol": "MSFT"})
        trace.add_decision("ctx_3", "s1", "D3", metadata={"symbol": "AAPL"})
        
        results = trace.query_decisions(symbol="AAPL")
        assert len(results) == 2
    
    def test_query_by_component(self):
        """Should query by component."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        trace.add_decision("ctx_a", "regime_detector", "BULL")
        trace.add_decision("ctx_b", "signal_gen", "LONG")
        trace.add_decision("ctx_c", "regime_detector", "BEAR")
        
        results = trace.query_decisions(component="regime_detector")
        assert len(results) == 2
    
    def test_query_by_outcome(self):
        """Should query by outcome."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        trace.add_decision("ctx_x", "s1", "D1", outcome="profit")
        trace.add_decision("ctx_y", "s1", "D2", outcome="loss")
        trace.add_decision("ctx_z", "s1", "D3", outcome="profit")
        
        profits = trace.query_decisions(outcome="profit")
        assert len(profits) == 2
        
        losses = trace.query_decisions(outcome="loss")
        assert len(losses) == 1


class TestStats:
    """Test statistics."""
    
    def test_get_stats(self):
        """Should return comprehensive stats."""
        trace = DecisionTrace()
        trace._reset_for_testing()
        
        trace.add_decision("ctx_1", "c1", "d1", outcome="profit")
        trace.add_decision("ctx_2", "c2", "d2", outcome="loss")
        
        stats = trace.get_stats()
        
        assert "total_nodes" in stats
        assert stats["total_nodes"] == 2
        assert "outcomes" in stats
        assert "components" in stats


# Helper for testing
def _add_reset_method():
    """Add reset method for testing."""
    def _reset_for_testing(self):
        import networkx as nx
        self._graph = nx.DiGraph()
        self._contexts = {}
        self._node_index = {}
    
    DecisionTrace._reset_for_testing = _reset_for_testing


_add_reset_method()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
