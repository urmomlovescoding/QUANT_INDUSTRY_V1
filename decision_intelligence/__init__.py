"""
Decision Intelligence Package
==============================
Advanced intelligence layers for the QUANT_INDUSTRY_V1 platform.

This package transforms the trading application into a self-aware,
explainable, and self-improving decision intelligence platform.

Modules:
- ai_control_plane: Central coordinator for all AI components
- decision_trace: NetworkX-based causality graph for decisions
- exit_value_learning: RMDP for optimal exit timing
- shadow_mode: Unified shadow execution framework
- self_improvement: Automated drift detection → retraining loop

Usage:
    from decision_intelligence import (
        get_control_plane,
        get_decision_trace,
        get_exit_value_learner,
        get_shadow_manager,
        get_self_improvement_orchestrator,
    )
    
    # Get control plane in shadow mode (default)
    control_plane = get_control_plane()
    
    # Process a decision
    context = control_plane.create_context("AAPL")
    context = control_plane.process_decision(context, market_data)

All components start in SHADOW MODE by default for safety.
"""

from .ai_control_plane import (
    AIControlPlane,
    ControlPlaneMode,
    ComponentStatus,
    DecisionContext,
    get_control_plane,
    reset_control_plane,
)

from .decision_trace import (
    DecisionTrace,
    TraceNode,
    TraceEdge,
    NodeType,
    EdgeType,
    get_decision_trace,
)

from .exit_value_learning import (
    ExitValueLearner,
    ExitState,
    ExitAction,
    ExitReason,
    ExitRecommendation,
    ExitValueIntegration,
    get_exit_value_learner,
)

from .shadow_mode import (
    ShadowModeManager,
    ShadowComponent,
    ShadowDecision,
    ShadowStatus,
    PromotionCriteria,
    get_shadow_manager,
)

from .self_improvement import (
    SelfImprovementOrchestrator,
    ImprovementCycle,
    ImprovementPhase,
    TriggerType,
    ImprovementConfig,
    get_self_improvement_orchestrator,
)

__all__ = [
    # Control Plane
    "AIControlPlane",
    "ControlPlaneMode",
    "ComponentStatus",
    "DecisionContext",
    "get_control_plane",
    "reset_control_plane",
    
    # Decision Trace
    "DecisionTrace",
    "TraceNode",
    "TraceEdge",
    "NodeType",
    "EdgeType",
    "get_decision_trace",
    
    # Exit Value Learning
    "ExitValueLearner",
    "ExitState",
    "ExitAction",
    "ExitReason",
    "ExitRecommendation",
    "ExitValueIntegration",
    "get_exit_value_learner",
    
    # Shadow Mode
    "ShadowModeManager",
    "ShadowComponent",
    "ShadowDecision",
    "ShadowStatus",
    "PromotionCriteria",
    "get_shadow_manager",
    
    # Self Improvement
    "SelfImprovementOrchestrator",
    "ImprovementCycle",
    "ImprovementPhase",
    "TriggerType",
    "ImprovementConfig",
    "get_self_improvement_orchestrator",
]

__version__ = "1.0.0"
