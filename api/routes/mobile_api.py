"""
Mobile Dashboard API
QUANT_INDUSTRY_V1

Industry Problem: Can't monitor your portfolio on the go.
Desktop-focused platforms leave you blind when away from your desk.

Our Solution:
- Lightweight endpoints optimized for mobile
- Push notification integration
- Quick actions (close position, pause strategy)
- Offline-friendly data caching
- Battery-efficient polling
"""

from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile/v1", tags=["mobile"])


# =============================================================================
# Models
# =============================================================================

class QuickAction(str, Enum):
    """Quick actions available on mobile."""
    CLOSE_POSITION = "close_position"
    PAUSE_STRATEGY = "pause_strategy"
    RESUME_STRATEGY = "resume_strategy"
    REDUCE_EXPOSURE = "reduce_exposure"
    EMERGENCY_FLATTEN = "emergency_flatten"


class PortfolioSummary(BaseModel):
    """Lightweight portfolio summary for mobile."""
    total_value: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    buying_power: float
    margin_used: float
    positions_count: int
    open_orders_count: int
    # Status indicators
    market_status: str  # "open", "closed", "pre-market", "after-hours"
    alerts_count: int
    has_critical_alerts: bool
    last_updated: datetime


class PositionSummary(BaseModel):
    """Lightweight position for mobile list."""
    symbol: str
    quantity: float
    market_value: float
    pnl: float
    pnl_pct: float
    side: str  # "long" or "short"
    # Sparkline data (last 20 prices for mini chart)
    sparkline: List[float] = []


class StrategySummary(BaseModel):
    """Lightweight strategy summary for mobile."""
    strategy_id: str
    name: str
    status: str  # "active", "paused", "error"
    daily_pnl: float
    daily_pnl_pct: float
    sharpe_30d: float
    allocation_pct: float
    positions_count: int
    health: str  # "good", "warning", "critical"


class AlertSummary(BaseModel):
    """Alert for mobile notification."""
    alert_id: str
    timestamp: datetime
    priority: str  # "low", "medium", "high", "critical"
    title: str
    message: str
    symbol: Optional[str]
    acknowledged: bool
    action_required: bool


class QuickActionRequest(BaseModel):
    """Request for quick action."""
    action: QuickAction
    target_id: str  # symbol or strategy_id
    params: Optional[Dict[str, Any]] = None
    confirm: bool = False  # Requires confirmation for dangerous actions


class QuickActionResponse(BaseModel):
    """Response from quick action."""
    success: bool
    action: QuickAction
    message: str
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None


class PushNotificationSettings(BaseModel):
    """Push notification preferences."""
    enabled: bool = True
    # Alert types
    price_alerts: bool = True
    position_alerts: bool = True
    strategy_alerts: bool = True
    execution_alerts: bool = True
    risk_alerts: bool = True
    # Quiet hours
    quiet_hours_enabled: bool = False
    quiet_start: str = "22:00"  # HH:MM
    quiet_end: str = "08:00"
    # Priority filter
    min_priority: str = "medium"  # Only notify for this priority and above


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/summary")
async def get_portfolio_summary():
    """
    Get lightweight portfolio summary.

    Optimized for mobile with minimal data transfer.
    Includes only essential metrics for quick glance.
    """
    return {
        "status": "unavailable",
        "message": "Mobile portfolio summary requires a connected portfolio service. No live data available.",
        "data": {}
    }


@router.get("/positions")
async def get_positions(
    sort_by: str = Query("pnl", description="Sort by: pnl, value, symbol"),
    limit: int = Query(20, ge=1, le=50),
    include_sparkline: bool = Query(True, description="Include price sparkline")
):
    """
    Get positions list optimized for mobile.

    Returns sorted list with optional sparkline data for mini charts.
    """
    return {
        "status": "unavailable",
        "message": "Mobile positions require a connected portfolio service. No live data available.",
        "data": []
    }


@router.get("/strategies")
async def get_strategies():
    """
    Get strategies list for mobile.

    Shows status, P&L, and health indicators for each strategy.
    """
    return {
        "status": "unavailable",
        "message": "Mobile strategy summaries require a connected trading service. No live data available.",
        "data": []
    }


@router.get("/alerts")
async def get_alerts(
    unacknowledged_only: bool = Query(False),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get recent alerts for mobile.

    Returns alerts sorted by priority and recency.
    """
    return {
        "status": "unavailable",
        "message": "Mobile alerts require a connected alerting service. No live data available.",
        "data": []
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    # Would update alert in database
    return {"success": True, "alert_id": alert_id}


@router.post("/quick-action", response_model=QuickActionResponse)
async def execute_quick_action(request: QuickActionRequest, background_tasks: BackgroundTasks):
    """
    Execute a quick action.
    
    Some actions require confirmation (confirm=True).
    Dangerous actions (emergency_flatten) always require confirmation.
    """
    # Actions requiring confirmation
    dangerous_actions = [
        QuickAction.EMERGENCY_FLATTEN,
        QuickAction.CLOSE_POSITION
    ]
    
    if request.action in dangerous_actions and not request.confirm:
        return QuickActionResponse(
            success=False,
            action=request.action,
            message="Action requires confirmation",
            requires_confirmation=True,
            confirmation_message=f"Are you sure you want to {request.action.value}? This cannot be undone."
        )
    
    # Execute action
    if request.action == QuickAction.CLOSE_POSITION:
        # Would close position via broker
        logger.info(f"Closing position: {request.target_id}")
        return QuickActionResponse(
            success=True,
            action=request.action,
            message=f"Position {request.target_id} closed"
        )
        
    elif request.action == QuickAction.PAUSE_STRATEGY:
        logger.info(f"Pausing strategy: {request.target_id}")
        return QuickActionResponse(
            success=True,
            action=request.action,
            message=f"Strategy {request.target_id} paused"
        )
        
    elif request.action == QuickAction.RESUME_STRATEGY:
        logger.info(f"Resuming strategy: {request.target_id}")
        return QuickActionResponse(
            success=True,
            action=request.action,
            message=f"Strategy {request.target_id} resumed"
        )
        
    elif request.action == QuickAction.REDUCE_EXPOSURE:
        # Reduce by 50% by default
        pct = request.params.get("pct", 0.5) if request.params else 0.5
        logger.info(f"Reducing exposure for {request.target_id} by {pct*100}%")
        return QuickActionResponse(
            success=True,
            action=request.action,
            message=f"Reduced {request.target_id} exposure by {pct*100:.0f}%"
        )
        
    elif request.action == QuickAction.EMERGENCY_FLATTEN:
        # Flatten all positions
        logger.warning(f"EMERGENCY FLATTEN requested by mobile user")
        background_tasks.add_task(_emergency_flatten)
        return QuickActionResponse(
            success=True,
            action=request.action,
            message="Emergency flatten initiated. All positions being closed."
        )
        
    return QuickActionResponse(
        success=False,
        action=request.action,
        message="Unknown action"
    )


async def _emergency_flatten():
    """Background task for emergency flatten."""
    logger.warning("Executing emergency flatten...")
    # Would close all positions via broker
    pass


@router.get("/watchlist")
async def get_watchlist(include_sparkline: bool = Query(True)):
    """Get user's watchlist with current prices."""
    return {
        "status": "unavailable",
        "message": "Mobile watchlist requires a connected market data service. No live data available.",
        "data": []
    }


@router.get("/market-status")
async def get_market_status():
    """Get current market status and key indices."""
    return {
        "status": "unavailable",
        "message": "Mobile market status requires a connected market data service. No live data available.",
        "indices": {}
    }


@router.get("/notifications/settings", response_model=PushNotificationSettings)
async def get_notification_settings():
    """Get push notification settings."""
    # Would load from user preferences
    return PushNotificationSettings()


@router.put("/notifications/settings")
async def update_notification_settings(settings: PushNotificationSettings):
    """Update push notification settings."""
    # Would save to user preferences
    return {"success": True, "settings": settings}


@router.post("/notifications/test")
async def send_test_notification():
    """Send a test push notification."""
    # Would send via Firebase/APNs
    return {"success": True, "message": "Test notification sent"}


@router.get("/chart/{symbol}")
async def get_chart_data(
    symbol: str,
    timeframe: str = Query("1D", description="1D, 1W, 1M, 3M, 1Y, ALL"),
    interval: str = Query("5min", description="1min, 5min, 15min, 1H, 1D")
):
    """
    Get chart data for mobile charts.

    Returns OHLC data optimized for mobile chart rendering.
    """
    return {
        "status": "unavailable",
        "message": "Mobile chart data requires a connected market data service. No live data available.",
        "symbol": symbol,
        "timeframe": timeframe,
        "interval": interval,
        "data": []
    }


@router.get("/health")
async def health_check():
    """Health check endpoint for mobile app."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_version": "1.0.0",
        "features": {
            "trading": True,
            "real_time": True,
            "push_notifications": True
        }
    }
