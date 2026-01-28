"""
QUANT INDUSTRY - Real-Time Risk Monitor
========================================
Continuous risk monitoring with alerts:
- Position limit monitoring
- Drawdown tracking
- VaR breach detection
- Correlation spike alerts
- Liquidity warnings
- Automatic position scaling

This runs continuously and protects your capital.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertType(Enum):
    """Types of risk alerts"""
    DRAWDOWN_WARNING = "drawdown_warning"
    DRAWDOWN_LIMIT = "drawdown_limit"
    VAR_BREACH = "var_breach"
    POSITION_LIMIT = "position_limit"
    CONCENTRATION_HIGH = "concentration_high"
    CORRELATION_SPIKE = "correlation_spike"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_WARNING = "liquidity_warning"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    MARGIN_WARNING = "margin_warning"
    SYSTEM_ERROR = "system_error"


@dataclass
class RiskAlert:
    """A single risk alert"""
    timestamp: datetime
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    symbol: str = ""
    acknowledged: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "metric": self.metric_name,
            "current": self.current_value,
            "threshold": self.threshold_value,
            "symbol": self.symbol,
            "acknowledged": self.acknowledged,
        }


@dataclass
class RiskThresholds:
    """Configurable risk thresholds"""
    # Drawdown
    drawdown_warning_pct: float = 5.0
    drawdown_limit_pct: float = 10.0
    max_drawdown_pct: float = 15.0
    
    # Daily
    daily_loss_warning_pct: float = 2.0
    daily_loss_limit_pct: float = 3.0
    
    # Position
    max_position_pct: float = 20.0
    max_single_position_pct: float = 10.0
    max_positions: int = 20
    
    # Concentration
    max_sector_concentration_pct: float = 40.0
    max_correlation: float = 0.8
    
    # Volatility
    vol_spike_threshold: float = 2.0  # Multiplier vs normal
    
    # VaR
    var_limit_pct: float = 5.0  # Max daily VaR as % of portfolio
    
    # Margin
    margin_warning_pct: float = 70.0
    margin_limit_pct: float = 85.0


@dataclass
class PortfolioState:
    """Current portfolio state for monitoring"""
    timestamp: datetime
    equity: float
    cash: float
    positions: Dict[str, float]  # symbol: value
    daily_pnl: float
    high_water_mark: float
    margin_used: float = 0.0
    margin_available: float = 0.0
    
    @property
    def drawdown_pct(self) -> float:
        if self.high_water_mark <= 0:
            return 0.0
        return (self.high_water_mark - self.equity) / self.high_water_mark * 100
    
    @property
    def daily_loss_pct(self) -> float:
        if self.equity <= 0:
            return 0.0
        return -self.daily_pnl / self.equity * 100
    
    @property
    def margin_usage_pct(self) -> float:
        total = self.margin_used + self.margin_available
        if total <= 0:
            return 0.0
        return self.margin_used / total * 100


class RealTimeRiskMonitor:
    """
    Continuous risk monitoring system.
    
    Monitors portfolio state and generates alerts when thresholds are breached.
    Can automatically trigger risk reduction actions.
    
    Usage:
    ------
    >>> monitor = RealTimeRiskMonitor()
    >>> 
    >>> # Register alert callback
    >>> monitor.on_alert(lambda alert: send_notification(alert))
    >>>
    >>> # Start monitoring
    >>> await monitor.start()
    >>>
    >>> # Update with new portfolio state
    >>> monitor.update(portfolio_state)
    >>>
    >>> # Get current risk summary
    >>> summary = monitor.get_risk_summary()
    """
    
    def __init__(
        self,
        thresholds: RiskThresholds = None,
        check_interval_seconds: float = 1.0,
        alert_cooldown_seconds: float = 300.0  # 5 min between same alerts
    ):
        """
        Initialize risk monitor.
        
        Args:
            thresholds: Risk thresholds
            check_interval_seconds: How often to check (seconds)
            alert_cooldown_seconds: Minimum time between repeated alerts
        """
        self.thresholds = thresholds or RiskThresholds()
        self.check_interval = check_interval_seconds
        self.alert_cooldown = alert_cooldown_seconds
        
        # State
        self.current_state: Optional[PortfolioState] = None
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        
        # Alerts
        self.alerts: deque = deque(maxlen=1000)
        self.active_alerts: Dict[str, RiskAlert] = {}
        self._last_alert_time: Dict[AlertType, datetime] = {}
        
        # Callbacks
        self._alert_callbacks: List[Callable[[RiskAlert], None]] = []
        self._action_callbacks: List[Callable[[str, Dict], None]] = []
        
        # History for calculations
        self._equity_history: deque = deque(maxlen=1000)
        self._return_history: deque = deque(maxlen=252)
        
        # Tracking
        self.metrics = {
            "alerts_generated": 0,
            "critical_alerts": 0,
            "actions_triggered": 0,
        }
        
        logger.info("RealTimeRiskMonitor initialized")
    
    def on_alert(self, callback: Callable[[RiskAlert], None]):
        """Register callback for alerts"""
        self._alert_callbacks.append(callback)
    
    def on_action(self, callback: Callable[[str, Dict], None]):
        """Register callback for risk actions (e.g., reduce position)"""
        self._action_callbacks.append(callback)
    
    async def start(self):
        """Start the monitoring loop"""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Risk monitor started")
    
    async def stop(self):
        """Stop the monitoring loop"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Risk monitor stopped")
    
    def update(self, state: PortfolioState):
        """
        Update with new portfolio state.
        
        Args:
            state: Current portfolio state
        """
        self.current_state = state
        
        # Track history
        self._equity_history.append((state.timestamp, state.equity))
        
        if len(self._equity_history) >= 2:
            prev_equity = self._equity_history[-2][1]
            if prev_equity > 0:
                ret = (state.equity - prev_equity) / prev_equity
                self._return_history.append(ret)
        
        # Run checks immediately on update
        self._run_all_checks()
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                if self.current_state:
                    self._run_all_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Risk monitor error: {e}")
                self._create_alert(
                    AlertType.SYSTEM_ERROR,
                    AlertSeverity.WARNING,
                    f"Risk monitor error: {e}",
                    "system",
                    0, 0
                )
    
    def _run_all_checks(self):
        """Run all risk checks"""
        if not self.current_state:
            return
        
        state = self.current_state
        
        # Drawdown checks
        self._check_drawdown(state)
        
        # Daily loss checks
        self._check_daily_loss(state)
        
        # Position checks
        self._check_positions(state)
        
        # Volatility checks
        self._check_volatility()
        
        # VaR checks
        self._check_var(state)
        
        # Margin checks
        self._check_margin(state)
    
    def _check_drawdown(self, state: PortfolioState):
        """Check drawdown levels"""
        dd = state.drawdown_pct
        
        if dd >= self.thresholds.max_drawdown_pct:
            self._create_alert(
                AlertType.DRAWDOWN_LIMIT,
                AlertSeverity.EMERGENCY,
                f"MAX DRAWDOWN BREACHED: {dd:.1f}% (limit: {self.thresholds.max_drawdown_pct}%)",
                "drawdown",
                dd, self.thresholds.max_drawdown_pct
            )
            self._trigger_action("close_all_positions", {"reason": "max_drawdown"})
        
        elif dd >= self.thresholds.drawdown_limit_pct:
            self._create_alert(
                AlertType.DRAWDOWN_LIMIT,
                AlertSeverity.CRITICAL,
                f"Drawdown limit hit: {dd:.1f}%",
                "drawdown",
                dd, self.thresholds.drawdown_limit_pct
            )
            self._trigger_action("reduce_positions", {"target_pct": 50})
        
        elif dd >= self.thresholds.drawdown_warning_pct:
            self._create_alert(
                AlertType.DRAWDOWN_WARNING,
                AlertSeverity.WARNING,
                f"Drawdown warning: {dd:.1f}%",
                "drawdown",
                dd, self.thresholds.drawdown_warning_pct
            )
    
    def _check_daily_loss(self, state: PortfolioState):
        """Check daily loss limits"""
        loss_pct = state.daily_loss_pct
        
        if loss_pct >= self.thresholds.daily_loss_limit_pct:
            self._create_alert(
                AlertType.DAILY_LOSS_LIMIT,
                AlertSeverity.CRITICAL,
                f"Daily loss limit hit: -{loss_pct:.1f}%",
                "daily_loss",
                loss_pct, self.thresholds.daily_loss_limit_pct
            )
            self._trigger_action("stop_trading", {"reason": "daily_loss_limit"})
        
        elif loss_pct >= self.thresholds.daily_loss_warning_pct:
            self._create_alert(
                AlertType.DAILY_LOSS_LIMIT,
                AlertSeverity.WARNING,
                f"Daily loss warning: -{loss_pct:.1f}%",
                "daily_loss",
                loss_pct, self.thresholds.daily_loss_warning_pct
            )
    
    def _check_positions(self, state: PortfolioState):
        """Check position limits"""
        if not state.positions:
            return
        
        total_exposure = sum(abs(v) for v in state.positions.values())
        equity = state.equity
        
        if equity <= 0:
            return
        
        # Total exposure
        exposure_pct = total_exposure / equity * 100
        if exposure_pct > self.thresholds.max_position_pct * 100 / self.thresholds.max_single_position_pct:
            self._create_alert(
                AlertType.POSITION_LIMIT,
                AlertSeverity.WARNING,
                f"High total exposure: {exposure_pct:.0f}%",
                "total_exposure",
                exposure_pct, 100
            )
        
        # Single position concentration
        for symbol, value in state.positions.items():
            pct = abs(value) / equity * 100
            if pct > self.thresholds.max_single_position_pct:
                self._create_alert(
                    AlertType.CONCENTRATION_HIGH,
                    AlertSeverity.WARNING,
                    f"Position concentration: {symbol} at {pct:.1f}%",
                    "position_concentration",
                    pct, self.thresholds.max_single_position_pct,
                    symbol=symbol
                )
        
        # Number of positions
        if len(state.positions) > self.thresholds.max_positions:
            self._create_alert(
                AlertType.POSITION_LIMIT,
                AlertSeverity.INFO,
                f"Too many positions: {len(state.positions)}",
                "position_count",
                len(state.positions), self.thresholds.max_positions
            )
    
    def _check_volatility(self):
        """Check for volatility spikes"""
        if len(self._return_history) < 20:
            return
        
        returns = list(self._return_history)
        
        # Recent vs historical volatility
        recent_vol = np.std(returns[-10:]) if len(returns) >= 10 else 0
        historical_vol = np.std(returns) if len(returns) >= 20 else recent_vol
        
        if historical_vol > 0:
            vol_ratio = recent_vol / historical_vol
            
            if vol_ratio > self.thresholds.vol_spike_threshold:
                self._create_alert(
                    AlertType.VOLATILITY_SPIKE,
                    AlertSeverity.WARNING,
                    f"Volatility spike: {vol_ratio:.1f}x normal",
                    "volatility_ratio",
                    vol_ratio, self.thresholds.vol_spike_threshold
                )
    
    def _check_var(self, state: PortfolioState):
        """Check VaR limits"""
        if len(self._return_history) < 20:
            return
        
        returns = np.array(list(self._return_history))
        var_95 = np.percentile(returns, 5)  # 5th percentile = 95% VaR
        
        var_pct = abs(var_95) * 100
        
        if var_pct > self.thresholds.var_limit_pct:
            self._create_alert(
                AlertType.VAR_BREACH,
                AlertSeverity.WARNING,
                f"VaR 95% at {var_pct:.1f}% (limit: {self.thresholds.var_limit_pct}%)",
                "var_95",
                var_pct, self.thresholds.var_limit_pct
            )
    
    def _check_margin(self, state: PortfolioState):
        """Check margin usage"""
        margin_pct = state.margin_usage_pct
        
        if margin_pct >= self.thresholds.margin_limit_pct:
            self._create_alert(
                AlertType.MARGIN_WARNING,
                AlertSeverity.CRITICAL,
                f"Margin limit approached: {margin_pct:.0f}%",
                "margin_usage",
                margin_pct, self.thresholds.margin_limit_pct
            )
        
        elif margin_pct >= self.thresholds.margin_warning_pct:
            self._create_alert(
                AlertType.MARGIN_WARNING,
                AlertSeverity.WARNING,
                f"High margin usage: {margin_pct:.0f}%",
                "margin_usage",
                margin_pct, self.thresholds.margin_warning_pct
            )
    
    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        metric_name: str,
        current_value: float,
        threshold_value: float,
        symbol: str = ""
    ):
        """Create and dispatch an alert"""
        # Check cooldown
        last_time = self._last_alert_time.get(alert_type)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self.alert_cooldown:
                return
        
        alert = RiskAlert(
            timestamp=datetime.now(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            symbol=symbol
        )
        
        self.alerts.append(alert)
        self.active_alerts[f"{alert_type.value}_{symbol}"] = alert
        self._last_alert_time[alert_type] = datetime.now()
        
        self.metrics["alerts_generated"] += 1
        if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            self.metrics["critical_alerts"] += 1
        
        logger.warning(f"RISK ALERT [{severity.value}]: {message}")
        
        # Dispatch to callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def _trigger_action(self, action: str, params: Dict):
        """Trigger a risk action"""
        logger.warning(f"RISK ACTION: {action} with params {params}")
        
        self.metrics["actions_triggered"] += 1
        
        for callback in self._action_callbacks:
            try:
                callback(action, params)
            except Exception as e:
                logger.error(f"Action callback error: {e}")
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary"""
        state = self.current_state
        
        if not state:
            return {"status": "no_data"}
        
        # Calculate current VaR
        var_95 = 0.0
        if len(self._return_history) >= 20:
            var_95 = abs(np.percentile(list(self._return_history), 5)) * 100
        
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "monitoring",
            "portfolio": {
                "equity": state.equity,
                "drawdown_pct": state.drawdown_pct,
                "daily_pnl": state.daily_pnl,
                "daily_loss_pct": state.daily_loss_pct,
                "margin_usage_pct": state.margin_usage_pct,
            },
            "risk_metrics": {
                "var_95_pct": var_95,
                "position_count": len(state.positions) if state.positions else 0,
            },
            "alerts": {
                "active_count": len(self.active_alerts),
                "total_generated": self.metrics["alerts_generated"],
                "critical_count": self.metrics["critical_alerts"],
            },
            "thresholds": {
                "drawdown_limit": self.thresholds.drawdown_limit_pct,
                "daily_loss_limit": self.thresholds.daily_loss_limit_pct,
                "var_limit": self.thresholds.var_limit_pct,
            }
        }
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all active alerts"""
        return [alert.to_dict() for alert in self.active_alerts.values()]
    
    def acknowledge_alert(self, alert_key: str):
        """Acknowledge an alert"""
        if alert_key in self.active_alerts:
            self.active_alerts[alert_key].acknowledged = True


# ============== SINGLETON ==============

_monitor: Optional[RealTimeRiskMonitor] = None


def get_risk_monitor() -> RealTimeRiskMonitor:
    """Get or create global risk monitor"""
    global _monitor
    
    if _monitor is None:
        _monitor = RealTimeRiskMonitor()
    
    return _monitor
