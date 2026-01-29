"""
Decision Intelligence API Routes
================================
API endpoints for the Decision Intelligence platform.

These endpoints expose the AI Control Plane, Decision Trace,
Exit Value Learning, Shadow Mode, and Self-Improvement capabilities.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/decision-intelligence", tags=["decision-intelligence"])

# Try to import decision intelligence modules
try:
    from decision_intelligence import (
        get_control_plane,
        get_decision_trace,
        get_exit_value_learner,
        get_shadow_manager,
        get_self_improvement_orchestrator,
        ControlPlaneMode,
    )
    DECISION_INTEL_AVAILABLE = True
    logger.info("Decision Intelligence modules loaded")
except ImportError as e:
    DECISION_INTEL_AVAILABLE = False
    logger.warning(f"Decision Intelligence modules not available: {e}")


# ==================== REQUEST MODELS ====================

class KillSwitchRequest(BaseModel):
    reason: str


class TriggerImprovementRequest(BaseModel):
    component_name: str


class ExitRecommendationRequest(BaseModel):
    regime: str
    time_in_trade_minutes: float
    unrealized_pnl_pct: float
    current_volatility: float
    avg_volatility: float
    direction: str


# ==================== CONTROL PLANE ROUTES ====================

@router.get("/control-plane/status")
async def get_control_plane_status():
    """Get AI Control Plane status."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False, "message": "Decision Intelligence not loaded"}
    
    control_plane = get_control_plane()
    return control_plane.get_status()


@router.get("/control-plane/health")
async def get_control_plane_health():
    """Get health of all registered components."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False}
    
    control_plane = get_control_plane()
    return control_plane.check_health()


@router.post("/control-plane/kill-switch")
async def engage_kill_switch(request: KillSwitchRequest):
    """Engage the global kill switch."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    control_plane = get_control_plane()
    control_plane.engage_kill_switch(request.reason)
    
    return {"status": "engaged", "reason": request.reason}


@router.post("/control-plane/kill-switch/release")
async def release_kill_switch(request: KillSwitchRequest):
    """Release the kill switch (requires explicit reason)."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    control_plane = get_control_plane()
    control_plane.release_kill_switch(request.reason)
    
    return {"status": "released", "reason": request.reason}


# ==================== DECISION TRACE ROUTES ====================

@router.get("/trace/stats")
async def get_trace_stats():
    """Get decision trace statistics."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False}
    
    trace = get_decision_trace()
    return trace.get_stats()


@router.get("/trace/path/{context_id}")
async def get_decision_path(context_id: str):
    """Get the full decision path for a context."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    trace = get_decision_trace()
    return trace.get_decision_path(context_id)


@router.get("/trace/failure-patterns")
async def get_failure_patterns(days: int = Query(default=30, ge=1, le=365)):
    """Analyze patterns in failing decisions."""
    if not DECISION_INTEL_AVAILABLE:
        return []
    
    trace = get_decision_trace()
    return trace.analyze_failure_patterns(lookback_days=days)


@router.get("/trace/success-patterns")
async def get_success_patterns(days: int = Query(default=30, ge=1, le=365)):
    """Analyze patterns in successful decisions."""
    if not DECISION_INTEL_AVAILABLE:
        return []
    
    trace = get_decision_trace()
    return trace.analyze_success_patterns(lookback_days=days)


@router.get("/trace/query")
async def query_decisions(
    symbol: Optional[str] = None,
    regime: Optional[str] = None,
    outcome: Optional[str] = None,
    component: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Query decision nodes with filters."""
    if not DECISION_INTEL_AVAILABLE:
        return []
    
    trace = get_decision_trace()
    nodes = trace.query_decisions(
        symbol=symbol,
        regime=regime,
        outcome=outcome,
        component=component,
        limit=limit,
    )
    return [n.to_dict() for n in nodes]


# ==================== EXIT VALUE LEARNING ROUTES ====================

@router.get("/exit-learning/stats")
async def get_exit_learner_stats():
    """Get exit value learner statistics."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False}
    
    learner = get_exit_value_learner()
    return learner.get_stats()


@router.post("/exit-learning/recommend/{position_id}")
async def get_exit_recommendation(position_id: str, request: ExitRecommendationRequest):
    """Get exit recommendation for a position."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    learner = get_exit_value_learner()
    
    state = learner.discretize_state(
        regime=request.regime,
        time_in_trade_minutes=request.time_in_trade_minutes,
        unrealized_pnl_pct=request.unrealized_pnl_pct,
        current_volatility=request.current_volatility,
        avg_volatility=request.avg_volatility,
        direction=request.direction,
    )
    
    recommendation = learner.recommend_action(
        state=state,
        unrealized_pnl=request.unrealized_pnl_pct,
    )
    
    return recommendation.to_dict()


@router.get("/exit-learning/value-surface/{regime}")
async def get_value_surface(regime: str, direction: str = "LONG"):
    """Get the Q-value surface for a regime."""
    if not DECISION_INTEL_AVAILABLE:
        return []
    
    learner = get_exit_value_learner()
    return learner.get_value_surface(regime, direction)


@router.get("/exit-learning/optimal-exits")
async def get_optimal_exits_by_regime():
    """Get optimal exit points by regime."""
    if not DECISION_INTEL_AVAILABLE:
        return {}
    
    learner = get_exit_value_learner()
    return learner.get_optimal_exits_by_regime()


# ==================== SHADOW MODE ROUTES ====================

@router.get("/shadow/components")
async def list_shadow_components(status: Optional[str] = None):
    """List all shadow components."""
    if not DECISION_INTEL_AVAILABLE:
        return []
    
    from decision_intelligence import ShadowStatus
    
    manager = get_shadow_manager()
    
    if status:
        try:
            status_enum = ShadowStatus(status)
            components = manager.list_components(status=status_enum)
        except ValueError:
            components = manager.list_components()
    else:
        components = manager.list_components()
    
    return [c.to_dict() for c in components]


@router.get("/shadow/report/{component_id}")
async def get_shadow_report(component_id: str):
    """Get comprehensive report for a shadow component."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    manager = get_shadow_manager()
    report = manager.get_shadow_report(component_id)
    
    if not report:
        raise HTTPException(status_code=404, detail=f"Component {component_id} not found")
    
    return report


@router.get("/shadow/comparison")
async def get_shadow_comparison():
    """Get summary of shadow vs live performance."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False}
    
    manager = get_shadow_manager()
    return manager.get_comparison_summary()


@router.post("/shadow/promote/{component_id}")
async def promote_shadow_component(component_id: str):
    """Promote a shadow component to live."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    manager = get_shadow_manager()
    success = manager.promote_component(component_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Promotion failed - checks not passed")
    
    return {"status": "promoted", "component_id": component_id}


# ==================== SELF-IMPROVEMENT ROUTES ====================

@router.get("/self-improvement/status")
async def get_self_improvement_status():
    """Get self-improvement orchestrator status."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False}
    
    orchestrator = get_self_improvement_orchestrator()
    return orchestrator.get_status()


@router.get("/self-improvement/history")
async def get_improvement_history(limit: int = Query(default=10, ge=1, le=100)):
    """Get recent improvement cycle history."""
    if not DECISION_INTEL_AVAILABLE:
        return []
    
    orchestrator = get_self_improvement_orchestrator()
    return orchestrator.get_improvement_history(limit=limit)


@router.post("/self-improvement/trigger")
async def trigger_improvement(request: TriggerImprovementRequest):
    """Manually trigger an improvement cycle."""
    if not DECISION_INTEL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Intelligence not available")
    
    from decision_intelligence import TriggerType
    
    orchestrator = get_self_improvement_orchestrator()
    
    try:
        cycle = orchestrator.trigger_improvement(
            component_name=request.component_name,
            trigger=TriggerType.MANUAL,
        )
        return {"status": "triggered", "cycle": cycle.to_dict()}
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/self-improvement/check-drift")
async def check_for_drift():
    """Check for drift and potentially trigger improvement."""
    if not DECISION_INTEL_AVAILABLE:
        return {"available": False}
    
    orchestrator = get_self_improvement_orchestrator()
    cycle = orchestrator.monitor_and_trigger()
    
    if cycle:
        return {"drift_detected": True, "cycle": cycle.to_dict()}
    else:
        return {"drift_detected": False, "message": "No drift detected"}
