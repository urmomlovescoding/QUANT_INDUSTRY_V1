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

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
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

@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary():
    """
    Get lightweight portfolio summary.
    
    Optimized for mobile with minimal data transfer.
    Includes only essential metrics for quick glance.
    """
    # Mock data - would pull from actual portfolio service
    return PortfolioSummary(
        total_value=1_234_567.89,
        daily_pnl=12_345.67,
        daily_pnl_pct=0.0101,
        total_pnl=234_567.89,
        total_pnl_pct=0.234,
        buying_power=500_000.00,
        margin_used=234_567.89,
        positions_count=15,
        open_orders_count=3,
        market_status="open",
        alerts_count=2,
        has_critical_alerts=False,
        last_updated=datetime.now()
    )


@router.get("/positions", response_model=List[PositionSummary])
async def get_positions(
    sort_by: str = Query("pnl", description="Sort by: pnl, value, symbol"),
    limit: int = Query(20, ge=1, le=50),
    include_sparkline: bool = Query(True, description="Include price sparkline")
):
    """
    Get positions list optimized for mobile.
    
    Returns sorted list with optional sparkline data for mini charts.
    """
    # Mock data
    positions = [
        PositionSummary(
            symbol="AAPL",
            quantity=100,
            market_value=15000,
            pnl=500,
            pnl_pct=0.0345,
            side="long",
            sparkline=[148, 149, 150, 149, 151, 152, 150, 151, 152, 153] if include_sparkline else []
        ),
        PositionSummary(
            symbol="GOOGL",
            quantity=50,
            market_value=7000,
            pnl=-200,
            pnl_pct=-0.0278,
            side="long",
            sparkline=[138, 139, 140, 139, 138, 137, 139, 138, 137, 136] if include_sparkline else []
        ),
    ]
    
    # Sort
    if sort_by == "pnl":
        positions.sort(key=lambda p: p.pnl, reverse=True)
    elif sort_by == "value":
        positions.sort(key=lambda p: p.market_value, reverse=True)
    elif sort_by == "symbol":
        positions.sort(key=lambda p: p.symbol)
        
    return positions[:limit]


@router.get("/strategies", response_model=List[StrategySummary])
async def get_strategies():
    """
    Get strategies list for mobile.
    
    Shows status, P&L, and health indicators for each strategy.
    """
    # Mock data
    return [
        StrategySummary(
            strategy_id="momentum_1",
            name="Cross-Asset Momentum",
            status="active",
            daily_pnl=5000,
            daily_pnl_pct=0.02,
            sharpe_30d=1.8,
            allocation_pct=0.30,
            positions_count=8,
            health="good"
        ),
        StrategySummary(
            strategy_id="mean_rev_1",
            name="Mean Reversion",
            status="active",
            daily_pnl=-1000,
            daily_pnl_pct=-0.005,
            sharpe_30d=0.9,
            allocation_pct=0.20,
            positions_count=5,
            health="warning"
        ),
    ]


@router.get("/alerts", response_model=List[AlertSummary])
async def get_alerts(
    unacknowledged_only: bool = Query(False),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get recent alerts for mobile.
    
    Returns alerts sorted by priority and recency.
    """
    # Mock data
    alerts = [
        AlertSummary(
            alert_id="alert_1",
            timestamp=datetime.now() - timedelta(minutes=5),
            priority="high",
            title="Position approaching limit",
            message="AAPL position at 90% of max allocation",
            symbol="AAPL",
            acknowledged=False,
            action_required=True
        ),
        AlertSummary(
            alert_id="alert_2",
            timestamp=datetime.now() - timedelta(hours=1),
            priority="medium",
            title="Strategy underperforming",
            message="Mean Reversion strategy Sharpe dropped below 1.0",
            symbol=None,
            acknowledged=False,
            action_required=False
        ),
    ]
    
    if unacknowledged_only:
        alerts = [a for a in alerts if not a.acknowledged]
        
    if priority:
        alerts = [a for a in alerts if a.priority == priority]
        
    return alerts[:limit]


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
    # Mock data
    watchlist = [
        {
            "symbol": "TSLA",
            "price": 250.50,
            "change": 5.25,
            "change_pct": 0.0214,
            "sparkline": [245, 246, 248, 247, 249, 250, 251, 250, 251, 250] if include_sparkline else []
        },
        {
            "symbol": "NVDA",
            "price": 450.00,
            "change": -10.00,
            "change_pct": -0.0217,
            "sparkline": [460, 458, 455, 453, 450, 452, 449, 450, 451, 450] if include_sparkline else []
        }
    ]
    return watchlist


@router.get("/market-status")
async def get_market_status():
    """Get current market status and key indices."""
    return {
        "status": "open",
        "next_event": "close",
        "next_event_time": "16:00 ET",
        "indices": {
            "SPY": {"price": 450.25, "change_pct": 0.0085},
            "QQQ": {"price": 380.50, "change_pct": 0.0120},
            "IWM": {"price": 195.75, "change_pct": 0.0045},
            "VIX": {"price": 15.25, "change": -0.50}
        }
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
    import numpy as np
    
    # Generate mock data based on timeframe
    points = {
        "1D": 78,    # 5-min bars for 1 day
        "1W": 168,   # Hourly bars for 1 week
        "1M": 30,    # Daily bars for 1 month
        "3M": 90,
        "1Y": 252,
        "ALL": 504
    }.get(timeframe, 78)
    
    base_price = 150.0
    data = []
    
    for i in range(points):
        noise = np.random.randn() * 0.02
        base_price *= (1 + noise)
        data.append({
            "t": i,  # Would be actual timestamp
            "o": base_price * 0.999,
            "h": base_price * 1.005,
            "l": base_price * 0.995,
            "c": base_price,
            "v": np.random.randint(100000, 1000000)
        })
        
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "interval": interval,
        "data": data
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
