"""
Decision Trace with Causality Graph
====================================
P1: NetworkX-based decision tracing with causal analysis.

This creates a graph of:
- Decision nodes (what was decided)
- Outcome nodes (what happened)
- Causal edges (what caused what)

Enables:
- Root cause analysis of failures
- Pattern discovery in successful trades
- Systematic issue identification
- Counterfactual reasoning ("what if we had decided differently?")

SHADOW MODE: Always enabled. This is observability, not execution.

Rollback Plan: Delete this file, fall back to flat logging in TradeJournal.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import sqlite3

logger = logging.getLogger(__name__)

# Optional networkx import
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed - graph analysis disabled")


class NodeType(Enum):
    """Types of nodes in the decision graph."""
    CONTEXT = "context"           # Decision context (starting point)
    REGIME = "regime"             # Regime detection
    SIGNAL = "signal"             # Signal generation
    RISK = "risk"                 # Risk check
    EXECUTION = "execution"       # Execution decision
    TRADE = "trade"               # Trade action
    OUTCOME = "outcome"           # Trade outcome
    FEEDBACK = "feedback"         # Learning feedback
    ERROR = "error"               # Error/failure node


class EdgeType(Enum):
    """Types of edges (causal relationships)."""
    TRIGGERS = "triggers"         # A triggers B
    ENABLES = "enables"           # A enables B (necessary condition)
    BLOCKS = "blocks"             # A blocks B
    CAUSES = "causes"             # A causes B (outcome)
    LEARNS_FROM = "learns_from"   # A learns from B


@dataclass
class TraceNode:
    """A node in the decision trace graph."""
    node_id: str
    node_type: NodeType
    timestamp: datetime
    component: str
    decision: str
    reason: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    # For querying
    symbol: Optional[str] = None
    regime: Optional[str] = None
    outcome: Optional[str] = None
    pnl: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "decision": self.decision,
            "reason": self.reason,
            "data": self.data,
            "symbol": self.symbol,
            "regime": self.regime,
            "outcome": self.outcome,
            "pnl": self.pnl,
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> "TraceNode":
        return cls(
            node_id=d["node_id"],
            node_type=NodeType(d["node_type"]),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            component=d["component"],
            decision=d["decision"],
            reason=d["reason"],
            data=d.get("data", {}),
            symbol=d.get("symbol"),
            regime=d.get("regime"),
            outcome=d.get("outcome"),
            pnl=d.get("pnl"),
        )


@dataclass
class TraceEdge:
    """An edge (causal relationship) in the decision trace graph."""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    timestamp: datetime
    weight: float = 1.0  # Causal strength
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "timestamp": self.timestamp.isoformat(),
            "weight": self.weight,
            "metadata": self.metadata,
        }


@dataclass
class CausalPathway:
    """A causal pathway through the decision graph."""
    path_id: str
    nodes: List[str]  # Node IDs in order
    edges: List[str]  # Edge IDs in order
    total_weight: float
    outcome: str
    pnl: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "total_weight": self.total_weight,
            "outcome": self.outcome,
            "pnl": self.pnl,
        }


class DecisionTrace:
    """
    Decision trace with causality graph.
    
    Builds a directed graph of decisions and outcomes for:
    - Root cause analysis
    - Pattern discovery
    - System debugging
    - Learning optimization
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("decision_intelligence/decision_trace.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        # In-memory graph (if networkx available)
        if HAS_NETWORKX:
            self.graph = nx.DiGraph()
        else:
            self.graph = None
        
        # Node counter
        self._node_counter = 0
        self._edge_counter = 0
        
        logger.info("DecisionTrace initialized")
    
    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    component TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    data_json TEXT,
                    symbol TEXT,
                    regime TEXT,
                    outcome TEXT,
                    pnl REAL
                );
                
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    metadata_json TEXT,
                    FOREIGN KEY (source_id) REFERENCES nodes(node_id),
                    FOREIGN KEY (target_id) REFERENCES nodes(node_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_nodes_timestamp ON nodes(timestamp);
                CREATE INDEX IF NOT EXISTS idx_nodes_symbol ON nodes(symbol);
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_nodes_outcome ON nodes(outcome);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            """)
    
    # =========================================================================
    # NODE & EDGE CREATION
    # =========================================================================
    
    def add_node(self, node: TraceNode) -> str:
        """Add a node to the trace graph."""
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO nodes
                (node_id, node_type, timestamp, component, decision, reason,
                 data_json, symbol, regime, outcome, pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.node_id,
                node.node_type.value,
                node.timestamp.isoformat(),
                node.component,
                node.decision,
                node.reason,
                json.dumps(node.data),
                node.symbol,
                node.regime,
                node.outcome,
                node.pnl,
            ))
        
        # Add to in-memory graph
        if self.graph is not None:
            self.graph.add_node(
                node.node_id,
                **node.to_dict()
            )
        
        return node.node_id
    
    def add_decision(
        self,
        context_id: str = None,
        component: str = "unknown",
        decision: str = "unknown",
        inputs: Dict[str, Any] = None,
        outputs: Dict[str, Any] = None,
        confidence: float = None,
        symbol: str = None,
        regime: str = None,
        outcome: str = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Convenience method to add a decision node.
        
        This creates a TraceNode internally with auto-generated ID.
        """
        self._node_counter += 1
        timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        if context_id:
            node_id = f"{context_id}_{self._node_counter}_{timestamp_str}"
        else:
            node_id = f"decision_{self._node_counter}_{timestamp_str}"
        
        data = {}
        if inputs:
            data['inputs'] = inputs
        if outputs:
            data['outputs'] = outputs
        if confidence is not None:
            data['confidence'] = confidence
        if context_id:
            data['context_id'] = context_id
        if metadata:
            data.update(metadata)
            # Extract symbol from metadata if not provided directly
            if symbol is None and 'symbol' in metadata:
                symbol = metadata['symbol']
        
        node = TraceNode(
            node_id=node_id,
            node_type=NodeType.SIGNAL,
            timestamp=datetime.now(timezone.utc),
            component=component,
            decision=decision,
            reason=f"Decision from {component}",
            data=data,
            symbol=symbol,
            regime=regime,
            outcome=outcome,
        )
        
        return self.add_node(node)
    
    def _reset_for_testing(self) -> None:
        """Reset state for testing (clears graph, database, and counters)."""
        self._node_counter = 0
        self._edge_counter = 0
        if self.graph is not None:
            self.graph.clear()
        # Delete and recreate database for clean isolation
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except (PermissionError, OSError):
                # File might be locked, try clearing tables instead
                conn = sqlite3.connect(self.db_path, isolation_level=None)
                try:
                    conn.execute("DELETE FROM edges")
                    conn.execute("DELETE FROM nodes")
                finally:
                    conn.close()
                return
        # Reinitialize the database
        self._init_db()
    
    def add_edge(
        self, 
        edge_or_from: "TraceEdge | str" = None,
        to_node: str = None,
        relationship: str = "triggers",
        weight: float = 1.0,
        from_node: str = None,  # Alternative kwarg name
    ) -> str:
        """
        Add an edge to the trace graph.
        
        Can be called as:
        - add_edge(trace_edge_obj)
        - add_edge(from_node, to_node, relationship)
        - add_edge(from_node=x, to_node=y, relationship=z)
        """
        # Handle different calling conventions
        if isinstance(edge_or_from, TraceEdge):
            edge = edge_or_from
        elif isinstance(edge_or_from, str):
            # Called as add_edge(from_node, to_node, relationship)
            actual_from = edge_or_from
            actual_to = to_node
            actual_rel = relationship
            
            self._edge_counter += 1
            edge_id = f"edge_{self._edge_counter}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            
            # Map string relationship to EdgeType
            edge_type_map = {
                'triggers': EdgeType.TRIGGERS,
                'enables': EdgeType.ENABLES,
                'blocks': EdgeType.BLOCKS,
                'causes': EdgeType.CAUSES,
                'learns_from': EdgeType.LEARNS_FROM,
            }
            edge_type = edge_type_map.get(actual_rel, EdgeType.TRIGGERS)
            
            edge = TraceEdge(
                edge_id=edge_id,
                source_id=actual_from,
                target_id=actual_to,
                edge_type=edge_type,
                timestamp=datetime.now(timezone.utc),
                weight=weight,
            )
        else:
            # Called with keyword args only
            actual_from = from_node
            actual_to = to_node
            
            self._edge_counter += 1
            edge_id = f"edge_{self._edge_counter}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            
            edge_type_map = {
                'triggers': EdgeType.TRIGGERS,
                'enables': EdgeType.ENABLES,
                'blocks': EdgeType.BLOCKS,
                'causes': EdgeType.CAUSES,
                'learns_from': EdgeType.LEARNS_FROM,
            }
            edge_type = edge_type_map.get(relationship, EdgeType.TRIGGERS)
            
            edge = TraceEdge(
                edge_id=edge_id,
                source_id=actual_from,
                target_id=actual_to,
                edge_type=edge_type,
                timestamp=datetime.now(timezone.utc),
                weight=weight,
            )
        
        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO edges
                (edge_id, source_id, target_id, edge_type, timestamp, weight, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.edge_type.value,
                edge.timestamp.isoformat(),
                edge.weight,
                json.dumps(edge.metadata),
            ))
        
        # Add to in-memory graph
        if self.graph is not None:
            self.graph.add_edge(
                edge.source_id,
                edge.target_id,
                **edge.to_dict()
            )
        
        return edge.edge_id
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID."""
        self._node_counter += 1
        return f"n_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._node_counter}"
    
    def _generate_edge_id(self) -> str:
        """Generate unique edge ID."""
        self._edge_counter += 1
        return f"e_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._edge_counter}"
    
    def record_outcome(
        self,
        node_id: str,
        outcome: str,
        realized_pnl: float = None,
        notes: str = None,
    ) -> None:
        """
        Record an outcome for a decision node.
        
        Updates both the database and in-memory graph.
        """
        # Update database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE nodes SET outcome = ?, pnl = ? WHERE node_id = ?
            """, (outcome, realized_pnl, node_id))
        
        # Update in-memory graph
        if self.graph is not None and self.graph.has_node(node_id):
            self.graph.nodes[node_id]['outcome'] = outcome
            self.graph.nodes[node_id]['pnl'] = realized_pnl
            if realized_pnl is not None:
                self.graph.nodes[node_id]['realized_pnl'] = realized_pnl
            if notes:
                self.graph.nodes[node_id]['notes'] = notes
    
    # =========================================================================
    # CONTEXT LOGGING
    # =========================================================================
    
    def log_context(self, context: Any) -> str:
        """
        Log a DecisionContext from the control plane.
        
        Creates nodes for each decision in the context and links them.
        """
        context_id = context.context_id
        nodes_created = []
        
        # Create context root node
        root_node = TraceNode(
            node_id=f"{context_id}_root",
            node_type=NodeType.CONTEXT,
            timestamp=context.timestamp,
            component="control_plane",
            decision="CONTEXT_START",
            reason=f"Decision context for {context.symbol}",
            data={"context_id": context_id},
            symbol=context.symbol,
        )
        self.add_node(root_node)
        nodes_created.append(root_node.node_id)
        
        prev_node_id = root_node.node_id
        
        # Create nodes for each decision in the trace
        for i, decision in enumerate(context.decisions):
            node_type = self._infer_node_type(decision["component"])
            
            node = TraceNode(
                node_id=f"{context_id}_{i}",
                node_type=node_type,
                timestamp=datetime.fromisoformat(decision["timestamp"]),
                component=decision["component"],
                decision=decision["decision"],
                reason=decision["reason"],
                data=decision.get("data", {}),
                symbol=context.symbol,
                regime=context.regime,
            )
            self.add_node(node)
            nodes_created.append(node.node_id)
            
            # Create edge from previous node
            edge_type = self._infer_edge_type(decision["decision"])
            edge = TraceEdge(
                edge_id=self._generate_edge_id(),
                source_id=prev_node_id,
                target_id=node.node_id,
                edge_type=edge_type,
                timestamp=node.timestamp,
            )
            self.add_edge(edge)
            
            prev_node_id = node.node_id
        
        logger.debug(f"Logged context {context_id} with {len(nodes_created)} nodes")
        return context_id
    
    def _infer_node_type(self, component: str) -> NodeType:
        """Infer node type from component name."""
        mappings = {
            "regime_detector": NodeType.REGIME,
            "signal": NodeType.SIGNAL,
            "risk": NodeType.RISK,
            "risk_engine": NodeType.RISK,
            "kill_switch": NodeType.RISK,
            "control_plane": NodeType.EXECUTION,
            "execution": NodeType.EXECUTION,
        }
        
        for key, node_type in mappings.items():
            if key in component.lower():
                return node_type
        
        return NodeType.CONTEXT
    
    def _infer_edge_type(self, decision: str) -> EdgeType:
        """Infer edge type from decision."""
        if "BLOCKED" in decision or "REJECTED" in decision:
            return EdgeType.BLOCKS
        elif "ERROR" in decision:
            return EdgeType.BLOCKS
        else:
            return EdgeType.TRIGGERS
    
    # =========================================================================
    # OUTCOME LOGGING
    # =========================================================================
    
    def log_outcome(
        self,
        context_id: str,
        outcome: str,
        pnl: float,
        metadata: Dict = None,
    ) -> str:
        """
        Log the outcome of a decision context.
        
        Creates an outcome node and links it to the execution decision.
        """
        # Create outcome node
        outcome_node = TraceNode(
            node_id=f"{context_id}_outcome",
            node_type=NodeType.OUTCOME,
            timestamp=datetime.now(timezone.utc),
            component="outcome",
            decision=outcome.upper(),
            reason=f"PnL: ${pnl:.2f}",
            data=metadata or {},
            outcome=outcome,
            pnl=pnl,
        )
        self.add_node(outcome_node)
        
        # Find the last execution node for this context and link
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT node_id FROM nodes
                WHERE node_id LIKE ?
                ORDER BY timestamp DESC LIMIT 1
            """, (f"{context_id}_%",))
            row = cursor.fetchone()
            
            if row:
                last_node_id = row[0]
                edge = TraceEdge(
                    edge_id=self._generate_edge_id(),
                    source_id=last_node_id,
                    target_id=outcome_node.node_id,
                    edge_type=EdgeType.CAUSES,
                    timestamp=outcome_node.timestamp,
                )
                self.add_edge(edge)
        
        # Update all nodes in this context with outcome info
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE nodes SET outcome = ?, pnl = ?
                WHERE node_id LIKE ?
            """, (outcome, pnl, f"{context_id}_%"))
        
        logger.info(f"Logged outcome for {context_id}: {outcome}, PnL=${pnl:.2f}")
        return outcome_node.node_id
    
    # =========================================================================
    # CAUSAL ANALYSIS
    # =========================================================================
    
    def find_root_causes(
        self,
        outcome_node_id: str,
        max_depth: int = 10,
    ) -> List[TraceNode]:
        """
        Find root causes leading to an outcome.
        
        Traverses the graph backwards from outcome to find decision origins.
        """
        if not HAS_NETWORKX or self.graph is None:
            return self._find_root_causes_sql(outcome_node_id, max_depth)
        
        # Use networkx for efficient traversal
        root_causes = []
        
        try:
            # Get all predecessors (ancestors)
            ancestors = nx.ancestors(self.graph, outcome_node_id)
            
            # Find nodes with no incoming edges (roots)
            for node_id in ancestors:
                if self.graph.in_degree(node_id) == 0:
                    node_data = self.graph.nodes[node_id]
                    root_causes.append(TraceNode.from_dict(node_data))
        except nx.NetworkXError:
            pass
        
        return root_causes
    
    def _find_root_causes_sql(self, outcome_node_id: str, max_depth: int) -> List[TraceNode]:
        """SQL-based root cause finding (fallback)."""
        # Extract context ID
        if "_outcome" in outcome_node_id:
            context_id = outcome_node_id.replace("_outcome", "")
        else:
            context_id = outcome_node_id.rsplit("_", 1)[0]
        
        root_causes = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM nodes
                WHERE node_id LIKE ?
                ORDER BY timestamp ASC LIMIT 1
            """, (f"{context_id}%",))
            
            row = cursor.fetchone()
            if row:
                root_causes.append(TraceNode(
                    node_id=row[0],
                    node_type=NodeType(row[1]),
                    timestamp=datetime.fromisoformat(row[2]),
                    component=row[3],
                    decision=row[4],
                    reason=row[5],
                    data=json.loads(row[6]) if row[6] else {},
                    symbol=row[7],
                    regime=row[8],
                    outcome=row[9],
                    pnl=row[10],
                ))
        
        return root_causes
    
    def analyze_failure_patterns(
        self,
        lookback_days: int = 30,
        min_occurrences: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Analyze patterns in failing decisions.
        
        Groups failures by:
        - Component that failed
        - Regime when failure occurred
        - Decision that blocked execution
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        
        patterns = []
        
        with sqlite3.connect(self.db_path) as conn:
            # Group by component and decision for failures
            cursor = conn.execute("""
                SELECT component, decision, regime, COUNT(*) as count,
                       AVG(COALESCE(pnl, 0)) as avg_pnl
                FROM nodes
                WHERE timestamp > ?
                  AND (outcome = 'loss' OR decision LIKE '%BLOCKED%' OR decision LIKE '%REJECTED%')
                GROUP BY component, decision, regime
                HAVING COUNT(*) >= ?
                ORDER BY count DESC
            """, (cutoff, min_occurrences))
            
            for row in cursor.fetchall():
                patterns.append({
                    "component": row[0],
                    "decision": row[1],
                    "regime": row[2],
                    "occurrences": row[3],
                    "avg_pnl": row[4],
                    "pattern_type": "failure",
                })
        
        return patterns
    
    def analyze_success_patterns(
        self,
        lookback_days: int = 30,
        min_occurrences: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Analyze patterns in successful decisions.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        
        patterns = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT component, decision, regime, COUNT(*) as count,
                       AVG(COALESCE(pnl, 0)) as avg_pnl
                FROM nodes
                WHERE timestamp > ?
                  AND outcome = 'profit'
                GROUP BY component, decision, regime
                HAVING COUNT(*) >= ?
                ORDER BY avg_pnl DESC
            """, (cutoff, min_occurrences))
            
            for row in cursor.fetchall():
                patterns.append({
                    "component": row[0],
                    "decision": row[1],
                    "regime": row[2],
                    "occurrences": row[3],
                    "avg_pnl": row[4],
                    "pattern_type": "success",
                })
        
        return patterns
    
    def get_decision_path(self, context_id: str) -> List[Dict[str, Any]]:
        """Get the full decision path for a context."""
        path = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT node_id, node_type, timestamp, component, decision, reason, pnl
                FROM nodes
                WHERE node_id LIKE ?
                ORDER BY timestamp ASC
            """, (f"{context_id}%",))
            
            for row in cursor.fetchall():
                path.append({
                    "node_id": row[0],
                    "node_type": row[1],
                    "timestamp": row[2],
                    "component": row[3],
                    "decision": row[4],
                    "reason": row[5],
                    "pnl": row[6],
                })
        
        return path
    
    # =========================================================================
    # QUERY INTERFACE
    # =========================================================================
    
    def query_decisions(
        self,
        symbol: str = None,
        regime: str = None,
        outcome: str = None,
        component: str = None,
        since: datetime = None,
        limit: int = 100,
    ) -> List[TraceNode]:
        """
        Query decision nodes with filters.
        """
        query = "SELECT * FROM nodes WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if regime:
            query += " AND regime = ?"
            params.append(regime)
        
        if outcome:
            query += " AND outcome = ?"
            params.append(outcome)
        
        if component:
            query += " AND component = ?"
            params.append(component)
        
        if since:
            query += " AND timestamp > ?"
            params.append(since.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        nodes = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            
            for row in cursor.fetchall():
                nodes.append(TraceNode(
                    node_id=row[0],
                    node_type=NodeType(row[1]),
                    timestamp=datetime.fromisoformat(row[2]),
                    component=row[3],
                    decision=row[4],
                    reason=row[5],
                    data=json.loads(row[6]) if row[6] else {},
                    symbol=row[7],
                    regime=row[8],
                    outcome=row[9],
                    pnl=row[10],
                ))
        
        return nodes
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trace statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total nodes
            total_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            total_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            
            # Outcomes
            outcomes = {}
            cursor = conn.execute("""
                SELECT outcome, COUNT(*) FROM nodes
                WHERE outcome IS NOT NULL
                GROUP BY outcome
            """)
            for row in cursor.fetchall():
                outcomes[row[0]] = row[1]
            
            # Components
            components = {}
            cursor = conn.execute("""
                SELECT component, COUNT(*) FROM nodes
                GROUP BY component
            """)
            for row in cursor.fetchall():
                components[row[0]] = row[1]
        
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "outcomes": outcomes,
            "components": components,
            "graph_available": self.graph is not None,
        }


# =============================================================================
# BAYESIAN CAUSAL MODEL (P2 Enhancement)
# =============================================================================

class BayesianCausalModel:
    """
    Enhanced causal model using Bayesian network approach.
    
    Provides:
    - Probabilistic causal inference
    - Conditional probability estimation
    - Root cause probability scoring
    - Counterfactual reasoning support
    
    Uses simplified Bayesian network without Pyro dependency.
    """
    
    def __init__(self, decision_trace: 'DecisionTrace'):
        self.trace = decision_trace
        
        # Conditional probability tables (learned from data)
        self.cpt: Dict[str, Dict[str, float]] = {}
        
        # Node prior probabilities
        self.priors: Dict[str, float] = {}
        
        # Causal structure (parent -> children)
        self.causal_structure: Dict[str, Set[str]] = {}
        
        self._fitted = False
        
        logger.info("BayesianCausalModel initialized")
    
    def fit(self, lookback_days: int = 90) -> None:
        """
        Learn causal structure and probabilities from historical data.
        
        Estimates:
        - P(outcome | decision, regime, component)
        - P(decision | regime)
        - Causal graph structure
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        
        with sqlite3.connect(self.trace.db_path) as conn:
            # Get historical nodes
            cursor = conn.execute("""
                SELECT node_type, component, decision, regime, outcome
                FROM nodes
                WHERE timestamp > ? AND outcome IS NOT NULL
            """, (cutoff,))
            rows = cursor.fetchall()
        
        if len(rows) < 10:
            logger.warning("Insufficient data for Bayesian model fitting")
            return
        
        # Count occurrences for probability estimation
        outcome_counts: Dict[str, Dict[str, int]] = {}
        decision_counts: Dict[str, Dict[str, int]] = {}
        regime_counts: Dict[str, int] = {}
        total = len(rows)
        
        for node_type, component, decision, regime, outcome in rows:
            # Regime prior
            regime = regime or "unknown"
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            # P(outcome | component, decision)
            key = f"{component}:{decision}"
            if key not in outcome_counts:
                outcome_counts[key] = {}
            outcome = outcome or "unknown"
            outcome_counts[key][outcome] = outcome_counts[key].get(outcome, 0) + 1
            
            # P(decision | regime)
            if regime not in decision_counts:
                decision_counts[regime] = {}
            decision_counts[regime][decision] = decision_counts[regime].get(decision, 0) + 1
        
        # Calculate conditional probabilities
        # P(outcome | component:decision)
        for key, counts in outcome_counts.items():
            total_key = sum(counts.values())
            for outcome, count in counts.items():
                cpt_key = f"P(outcome={outcome}|{key})"
                self.cpt[cpt_key] = count / total_key
        
        # P(decision | regime)
        for regime, counts in decision_counts.items():
            total_regime = sum(counts.values())
            for decision, count in counts.items():
                cpt_key = f"P(decision={decision}|regime={regime})"
                self.cpt[cpt_key] = count / total_regime
        
        # Regime priors
        for regime, count in regime_counts.items():
            self.priors[f"regime={regime}"] = count / total
        
        # Build causal structure from edges
        with sqlite3.connect(self.trace.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT source_id, target_id FROM edges
            """)
            for source, target in cursor.fetchall():
                # Extract node types from IDs
                if source not in self.causal_structure:
                    self.causal_structure[source] = set()
                self.causal_structure[source].add(target)
        
        self._fitted = True
        logger.info(f"BayesianCausalModel fitted with {len(self.cpt)} probability entries")
    
    def infer_outcome_probability(
        self,
        component: str,
        decision: str,
        regime: str = None,
    ) -> Dict[str, float]:
        """
        Infer probability distribution over outcomes given evidence.
        
        P(outcome | component, decision, regime)
        """
        if not self._fitted:
            self.fit()
        
        probabilities = {}
        key = f"{component}:{decision}"
        
        # Get all outcomes for this key
        for cpt_key, prob in self.cpt.items():
            if key in cpt_key and cpt_key.startswith("P(outcome="):
                # Extract outcome
                outcome = cpt_key.split("outcome=")[1].split("|")[0]
                probabilities[outcome] = prob
        
        # Apply regime prior if available
        if regime:
            regime_prior = self.priors.get(f"regime={regime}", 0.5)
            for outcome in probabilities:
                probabilities[outcome] *= regime_prior
        
        # Normalize
        total = sum(probabilities.values()) or 1
        return {k: v / total for k, v in probabilities.items()}
    
    def compute_root_cause_probability(
        self,
        outcome_node_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Compute probability scores for potential root causes.
        
        Uses Bayesian inference to score how likely each upstream
        decision contributed to the outcome.
        """
        if not self._fitted:
            self.fit()
        
        # Get the outcome node
        with sqlite3.connect(self.trace.db_path) as conn:
            cursor = conn.execute("""
                SELECT outcome, pnl FROM nodes WHERE node_id = ?
            """, (outcome_node_id,))
            row = cursor.fetchone()
            
            if not row:
                return []
            
            target_outcome, pnl = row
        
        # Get all upstream nodes
        root_causes = self.trace.find_root_causes(outcome_node_id)
        
        scored_causes = []
        for node in root_causes:
            # Compute probability of this outcome given this node's decision
            key = f"{node.component}:{node.decision}"
            
            # P(outcome | decision)
            cpt_key = f"P(outcome={target_outcome}|{key})"
            prob = self.cpt.get(cpt_key, 0.5)  # Default to 0.5 if unknown
            
            # Apply regime adjustment
            if node.regime:
                regime_key = f"P(decision={node.decision}|regime={node.regime})"
                regime_prob = self.cpt.get(regime_key, 0.5)
                prob = prob * regime_prob
            
            scored_causes.append({
                'node_id': node.node_id,
                'component': node.component,
                'decision': node.decision,
                'regime': node.regime,
                'causal_probability': prob,
                'timestamp': node.timestamp.isoformat(),
            })
        
        # Sort by causal probability
        scored_causes.sort(key=lambda x: x['causal_probability'], reverse=True)
        
        return scored_causes
    
    def counterfactual_analysis(
        self,
        context_id: str,
        alternative_decision: str,
        at_component: str,
    ) -> Dict[str, float]:
        """
        Estimate counterfactual outcome: "What if we had decided differently?"
        
        Computes P(outcome | alternative_decision) - P(outcome | actual_decision)
        """
        if not self._fitted:
            self.fit()
        
        # Get actual decision path
        path = self.trace.get_decision_path(context_id)
        if not path:
            return {}
        
        # Find the node for the target component
        actual_decision = None
        regime = None
        for node in path:
            if node['component'] == at_component:
                actual_decision = node['decision']
                break
        
        if not actual_decision:
            return {}
        
        # Get actual outcome probabilities
        actual_probs = self.infer_outcome_probability(at_component, actual_decision, regime)
        
        # Get counterfactual outcome probabilities
        counter_probs = self.infer_outcome_probability(at_component, alternative_decision, regime)
        
        # Compute difference (counterfactual effect)
        effect = {}
        all_outcomes = set(actual_probs.keys()) | set(counter_probs.keys())
        
        for outcome in all_outcomes:
            actual = actual_probs.get(outcome, 0)
            counter = counter_probs.get(outcome, 0)
            effect[outcome] = {
                'actual_probability': actual,
                'counterfactual_probability': counter,
                'causal_effect': counter - actual,
            }
        
        return effect
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get summary of the Bayesian model."""
        return {
            'fitted': self._fitted,
            'num_probability_entries': len(self.cpt),
            'num_priors': len(self.priors),
            'causal_edges': sum(len(v) for v in self.causal_structure.values()),
            'top_priors': dict(sorted(
                self.priors.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
        }


# Add Bayesian model to DecisionTrace
def _get_bayesian_model(self) -> BayesianCausalModel:
    """Get or create Bayesian causal model."""
    if not hasattr(self, '_bayesian_model'):
        self._bayesian_model = BayesianCausalModel(self)
    return self._bayesian_model

DecisionTrace.get_bayesian_model = _get_bayesian_model


# =============================================================================
# SINGLETON
# =============================================================================

_decision_trace: Optional[DecisionTrace] = None


def get_decision_trace() -> DecisionTrace:
    """Get or create the DecisionTrace singleton."""
    global _decision_trace
    if _decision_trace is None:
        _decision_trace = DecisionTrace()
    return _decision_trace
