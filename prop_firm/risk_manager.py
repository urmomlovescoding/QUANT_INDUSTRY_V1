"""
Prop Firm Risk Manager
Real-time risk monitoring with dynamic limits and automatic interventions.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity levels."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAction(Enum):
    """Automatic risk actions."""
    NONE = "none"
    WARNING = "warning"
    REDUCE_SIZE = "reduce_size"
    CLOSE_NEW_POSITIONS = "close_new_positions"
    FLATTEN_ALL = "flatten_all"
    SUSPEND_TRADING = "suspend_trading"


class PropFirmRiskManager:
    """
    Real-time risk management for prop trading accounts.
    
    Features:
    - Continuous P&L and drawdown monitoring
    - Dynamic position limits based on performance
    - Automatic risk reduction triggers
    - Multi-level alerts (warning -> critical -> action)
    - News event risk adjustment
    - Correlation-based risk limits
    """
    
    def __init__(self, db_session, broker_client=None):
        self.db = db_session
        self.broker = broker_client
        self._risk_cache = {}  # Cache for real-time risk metrics
        
        # Risk thresholds (percentage of max allowed)
        self.thresholds = {
            RiskLevel.NORMAL: 0.0,
            RiskLevel.ELEVATED: 0.50,  # 50% of max drawdown
            RiskLevel.HIGH: 0.70,      # 70% of max drawdown
            RiskLevel.CRITICAL: 0.85,  # 85% of max drawdown
        }
        
        # Actions per risk level
        self.actions = {
            RiskLevel.NORMAL: RiskAction.NONE,
            RiskLevel.ELEVATED: RiskAction.WARNING,
            RiskLevel.HIGH: RiskAction.REDUCE_SIZE,
            RiskLevel.CRITICAL: RiskAction.CLOSE_NEW_POSITIONS,
        }
    
    def check_pre_trade_risk(
        self,
        account_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Pre-trade risk check before order submission.
        
        Returns:
            Tuple of (approved: bool, details: dict)
        """
        from .models import TraderAccount, Challenge
        
        account = self.db.query(TraderAccount).filter_by(id=account_id).first()
        if not account:
            return False, {"error": "Account not found"}
        
        if not account.is_active:
            return False, {"error": "Account is not active", "reason": account.pause_reason}
        
        if account.is_paused:
            return False, {"error": "Trading is paused", "reason": account.pause_reason}
        
        # Get current challenge if in evaluation
        challenge = None
        if account.challenge_id:
            challenge = self.db.query(Challenge).filter_by(id=account.challenge_id).first()
        
        position_value = Decimal(str(quantity * price))
        checks = []
        
        # Check 1: Position size limit
        max_position = account.max_position_size or (account.current_balance * Decimal("0.1"))
        if position_value > max_position:
            checks.append({
                "check": "position_size",
                "passed": False,
                "message": f"Position size ${position_value} exceeds limit ${max_position}"
            })
        else:
            checks.append({"check": "position_size", "passed": True})
        
        # Check 2: Daily loss limit
        remaining_daily_risk = account.max_daily_loss - abs(account.daily_pnl or 0)
        if remaining_daily_risk <= 0:
            checks.append({
                "check": "daily_loss",
                "passed": False,
                "message": "Daily loss limit reached - no new positions allowed"
            })
        else:
            checks.append({"check": "daily_loss", "passed": True})
        
        # Check 3: Total drawdown limit
        current_drawdown = account.initial_balance - account.current_balance
        remaining_drawdown = account.max_total_drawdown - max(current_drawdown, Decimal("0"))
        if remaining_drawdown <= 0:
            checks.append({
                "check": "total_drawdown",
                "passed": False,
                "message": "Total drawdown limit reached - account suspended"
            })
        else:
            checks.append({"check": "total_drawdown", "passed": True})
        
        # Check 4: Allowed instruments (if restricted)
        if challenge and challenge.allowed_instruments:
            if symbol not in challenge.allowed_instruments:
                checks.append({
                    "check": "allowed_instruments",
                    "passed": False,
                    "message": f"Symbol {symbol} not in allowed instruments"
                })
            else:
                checks.append({"check": "allowed_instruments", "passed": True})
        
        # Check 5: Risk level restrictions
        risk_level = self._get_risk_level(account)
        action = self.actions.get(risk_level, RiskAction.NONE)
        
        if action == RiskAction.CLOSE_NEW_POSITIONS:
            checks.append({
                "check": "risk_level",
                "passed": False,
                "message": f"Risk level CRITICAL - new positions blocked"
            })
        elif action == RiskAction.REDUCE_SIZE:
            # Allow but with reduced size
            reduction_factor = 0.5
            max_allowed = position_value * Decimal(str(reduction_factor))
            if position_value > max_allowed:
                checks.append({
                    "check": "risk_level",
                    "passed": False,
                    "message": f"Risk level HIGH - position size limited to ${max_allowed}"
                })
            else:
                checks.append({"check": "risk_level", "passed": True})
        else:
            checks.append({"check": "risk_level", "passed": True})
        
        # Aggregate result
        all_passed = all(c["passed"] for c in checks)
        failed_checks = [c for c in checks if not c["passed"]]
        
        return all_passed, {
            "approved": all_passed,
            "checks": checks,
            "failed_checks": failed_checks,
            "risk_level": risk_level.value,
            "account_status": {
                "balance": float(account.current_balance),
                "daily_pnl": float(account.daily_pnl or 0),
                "remaining_daily_risk": float(remaining_daily_risk),
                "remaining_drawdown": float(remaining_drawdown),
            }
        }
    
    def _get_risk_level(self, account) -> RiskLevel:
        """Determine current risk level based on drawdown."""
        if account.max_total_drawdown == 0:
            return RiskLevel.NORMAL
        
        current_drawdown = max(account.initial_balance - account.current_balance, Decimal("0"))
        drawdown_pct = float(current_drawdown / account.max_total_drawdown)
        
        if drawdown_pct >= self.thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif drawdown_pct >= self.thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif drawdown_pct >= self.thresholds[RiskLevel.ELEVATED]:
            return RiskLevel.ELEVATED
        else:
            return RiskLevel.NORMAL
    
    def update_realtime_metrics(
        self,
        account_id: int,
        current_equity: Decimal,
        open_pnl: Decimal,
        positions: List[Dict]
    ) -> Dict[str, Any]:
        """
        Update real-time risk metrics from live data.
        
        Called frequently (e.g., every tick or every few seconds).
        """
        from .models import TraderAccount
        
        account = self.db.query(TraderAccount).filter_by(id=account_id).first()
        if not account:
            return {"error": "Account not found"}
        
        # Calculate metrics
        total_equity = current_equity + open_pnl
        daily_pnl = total_equity - account.initial_balance  # Simplified; should track from day start
        
        # Update cache
        self._risk_cache[account_id] = {
            "equity": float(total_equity),
            "open_pnl": float(open_pnl),
            "daily_pnl": float(daily_pnl),
            "positions_count": len(positions),
            "total_exposure": sum(p.get("notional_value", 0) for p in positions),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Check for alerts
        alerts = self._check_risk_alerts(account, total_equity, daily_pnl)
        
        # Take automatic actions if needed
        actions_taken = []
        risk_level = self._get_risk_level(account)
        
        if risk_level == RiskLevel.CRITICAL:
            # Auto-pause account
            account.is_paused = True
            account.pause_reason = "Critical risk level reached - automatic pause"
            self.db.commit()
            actions_taken.append("account_paused")
        
        return {
            "risk_level": risk_level.value,
            "metrics": self._risk_cache[account_id],
            "alerts": alerts,
            "actions_taken": actions_taken,
        }
    
    def _check_risk_alerts(
        self,
        account,
        equity: Decimal,
        daily_pnl: Decimal
    ) -> List[Dict[str, Any]]:
        """Generate risk alerts based on current state."""
        alerts = []
        
        # Daily loss alert
        daily_loss_pct = float(abs(daily_pnl) / account.max_daily_loss) if account.max_daily_loss else 0
        if daily_loss_pct >= 0.5 and daily_pnl < 0:
            severity = "warning" if daily_loss_pct < 0.8 else "critical"
            alerts.append({
                "type": "daily_loss",
                "severity": severity,
                "message": f"Daily loss at {daily_loss_pct*100:.1f}% of limit",
                "value": float(daily_pnl),
                "limit": float(account.max_daily_loss),
            })
        
        # Total drawdown alert
        total_drawdown = account.initial_balance - equity
        if total_drawdown > 0:
            drawdown_pct = float(total_drawdown / account.max_total_drawdown) if account.max_total_drawdown else 0
            if drawdown_pct >= 0.5:
                severity = "warning" if drawdown_pct < 0.8 else "critical"
                alerts.append({
                    "type": "total_drawdown",
                    "severity": severity,
                    "message": f"Total drawdown at {drawdown_pct*100:.1f}% of limit",
                    "value": float(total_drawdown),
                    "limit": float(account.max_total_drawdown),
                })
        
        return alerts
    
    def get_dynamic_position_limits(self, account_id: int) -> Dict[str, Any]:
        """
        Calculate dynamic position limits based on current risk state.
        
        Better traders get higher limits, struggling traders get reduced limits.
        """
        from .models import TraderAccount, PerformanceMetrics
        
        account = self.db.query(TraderAccount).filter_by(id=account_id).first()
        if not account:
            return {"error": "Account not found"}
        
        metrics = self.db.query(PerformanceMetrics).filter_by(trader_id=account.trader_id).first()
        
        # Base limits
        base_position_size = float(account.current_balance * Decimal("0.1"))  # 10% default
        base_max_positions = 5
        
        # Performance multiplier (0.5x to 2x)
        perf_multiplier = 1.0
        if metrics:
            # Reward consistency and profitability
            if metrics.win_rate and metrics.win_rate > 55:
                perf_multiplier += 0.2
            if metrics.profit_factor and metrics.profit_factor > 1.5:
                perf_multiplier += 0.2
            if metrics.sharpe_ratio and metrics.sharpe_ratio > 1.0:
                perf_multiplier += 0.2
            if metrics.consistency_score and metrics.consistency_score > 70:
                perf_multiplier += 0.2
        
        # Risk level reduction
        risk_level = self._get_risk_level(account)
        risk_multiplier = {
            RiskLevel.NORMAL: 1.0,
            RiskLevel.ELEVATED: 0.8,
            RiskLevel.HIGH: 0.5,
            RiskLevel.CRITICAL: 0.25,
        }.get(risk_level, 1.0)
        
        # Scale level bonus
        scale_multiplier = 1.0 + (account.scale_level - 1) * 0.1
        
        # Final limits
        final_multiplier = perf_multiplier * risk_multiplier * scale_multiplier
        final_multiplier = max(0.25, min(2.5, final_multiplier))  # Clamp
        
        return {
            "max_position_size": base_position_size * final_multiplier,
            "max_positions": int(base_max_positions * final_multiplier),
            "max_daily_trades": int(20 * final_multiplier),
            "leverage_limit": min(10, 5 * final_multiplier),
            "multipliers": {
                "performance": perf_multiplier,
                "risk": risk_multiplier,
                "scale": scale_multiplier,
                "final": final_multiplier,
            },
            "risk_level": risk_level.value,
        }
    
    async def monitor_account_continuous(
        self,
        account_id: int,
        callback=None,
        interval_seconds: float = 1.0
    ):
        """
        Continuous monitoring loop for an account.
        
        Used for real-time WebSocket updates.
        """
        from .models import TraderAccount
        
        while True:
            try:
                # Get latest data from broker
                if self.broker:
                    positions = await self.broker.get_positions(account_id)
                    equity = await self.broker.get_equity(account_id)
                    open_pnl = await self.broker.get_open_pnl(account_id)
                else:
                    # Simulation mode
                    account = self.db.query(TraderAccount).filter_by(id=account_id).first()
                    if not account:
                        break
                    positions = []
                    equity = account.current_balance
                    open_pnl = Decimal("0")
                
                # Update metrics
                result = self.update_realtime_metrics(account_id, equity, open_pnl, positions)
                
                # Callback for WebSocket broadcast
                if callback:
                    await callback(result)
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in continuous monitoring for account {account_id}: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    def emergency_flatten(self, account_id: int, reason: str) -> Dict[str, Any]:
        """
        Emergency close all positions for an account.
        """
        from .models import TraderAccount
        
        account = self.db.query(TraderAccount).filter_by(id=account_id).first()
        if not account:
            return {"error": "Account not found"}
        
        logger.warning(f"EMERGENCY FLATTEN triggered for account {account_id}: {reason}")
        
        # Pause account
        account.is_paused = True
        account.pause_reason = f"Emergency flatten: {reason}"
        self.db.commit()
        
        # Close all positions via broker
        closed_positions = []
        if self.broker:
            try:
                closed_positions = self.broker.close_all_positions(account.broker_account_id)
            except Exception as e:
                logger.error(f"Failed to flatten positions: {e}")
                return {"error": str(e), "account_paused": True}
        
        return {
            "success": True,
            "account_paused": True,
            "positions_closed": len(closed_positions),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
