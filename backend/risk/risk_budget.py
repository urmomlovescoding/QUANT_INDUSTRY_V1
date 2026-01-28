"""
QUANT INDUSTRY - Risk Budget Enforcement
Defines and enforces risk budgets per strategy and factor.
Provides alerts, auto-scaling, and utilization tracking.
"""

import logging
import math
import os
import sqlite3
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskBudget:
    """Risk budget for a strategy or factor."""
    name: str
    budget_type: str        # "strategy" or "factor"
    max_var_pct: float      # max VaR as % of portfolio
    max_drawdown_pct: float
    max_position_pct: float
    max_gross_exposure_pct: float
    current_utilization: float = 0.0  # 0-100 scale

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "budget_type": self.budget_type,
            "max_var_pct": self.max_var_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_position_pct": self.max_position_pct,
            "max_gross_exposure_pct": self.max_gross_exposure_pct,
            "current_utilization": round(self.current_utilization, 1),
        }


@dataclass
class BudgetAlert:
    """Alert when budget limit is approached or breached."""
    budget_name: str
    metric: str            # "var", "drawdown", "position", "exposure"
    current_value: float
    limit_value: float
    utilization_pct: float
    severity: str          # "info", "warning", "critical"
    message: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_name": self.budget_name,
            "metric": self.metric,
            "current_value": round(self.current_value, 2),
            "limit_value": round(self.limit_value, 2),
            "utilization_pct": round(self.utilization_pct, 1),
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp,
        }


@dataclass
class ScaleRecommendation:
    """Recommendation to scale positions to stay within budget."""
    strategy: str
    current_exposure_pct: float
    recommended_exposure_pct: float
    scale_factor: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "current_exposure_pct": round(self.current_exposure_pct, 2),
            "recommended_exposure_pct": round(self.recommended_exposure_pct, 2),
            "scale_factor": round(self.scale_factor, 3),
            "reason": self.reason,
        }


# Default budgets
DEFAULT_BUDGETS: Dict[str, Dict[str, Any]] = {
    "momentum": {
        "budget_type": "strategy",
        "max_var_pct": 2.0,
        "max_drawdown_pct": 5.0,
        "max_position_pct": 10.0,
        "max_gross_exposure_pct": 30.0,
    },
    "mean_reversion": {
        "budget_type": "strategy",
        "max_var_pct": 1.5,
        "max_drawdown_pct": 4.0,
        "max_position_pct": 8.0,
        "max_gross_exposure_pct": 25.0,
    },
    "trend_following": {
        "budget_type": "strategy",
        "max_var_pct": 2.5,
        "max_drawdown_pct": 7.0,
        "max_position_pct": 12.0,
        "max_gross_exposure_pct": 35.0,
    },
    "market_factor": {
        "budget_type": "factor",
        "max_var_pct": 3.0,
        "max_drawdown_pct": 10.0,
        "max_position_pct": 15.0,
        "max_gross_exposure_pct": 50.0,
    },
    "sector_factor": {
        "budget_type": "factor",
        "max_var_pct": 1.5,
        "max_drawdown_pct": 5.0,
        "max_position_pct": 10.0,
        "max_gross_exposure_pct": 40.0,
    },
    "volatility_factor": {
        "budget_type": "factor",
        "max_var_pct": 1.0,
        "max_drawdown_pct": 3.0,
        "max_position_pct": 8.0,
        "max_gross_exposure_pct": 20.0,
    },
}


class RiskBudgetManager:
    """
    Manages risk budgets across strategies and factors.
    Monitors utilization, generates alerts, and recommends position scaling.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "risk_budgets.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._budgets: Dict[str, RiskBudget] = {}
        self._init_db()
        self._load_budgets()
        logger.info("RiskBudgetManager initialized")

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS risk_budgets (
                name TEXT PRIMARY KEY,
                budget_type TEXT NOT NULL,
                max_var_pct REAL,
                max_drawdown_pct REAL,
                max_position_pct REAL,
                max_gross_exposure_pct REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS budget_utilization_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                budget_name TEXT NOT NULL,
                utilization_pct REAL,
                var_used REAL,
                drawdown_used REAL,
                exposure_used REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS budget_alerts_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                budget_name TEXT NOT NULL,
                metric TEXT,
                severity TEXT,
                message TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _load_budgets(self):
        """Load budgets from DB or initialize from defaults."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name, budget_type, max_var_pct, max_drawdown_pct, max_position_pct, max_gross_exposure_pct FROM risk_budgets")
        rows = c.fetchall()
        conn.close()

        if rows:
            for r in rows:
                self._budgets[r[0]] = RiskBudget(
                    name=r[0], budget_type=r[1],
                    max_var_pct=r[2], max_drawdown_pct=r[3],
                    max_position_pct=r[4], max_gross_exposure_pct=r[5],
                )
        else:
            # Initialize from defaults
            for name, cfg in DEFAULT_BUDGETS.items():
                budget = RiskBudget(name=name, **cfg)
                self._budgets[name] = budget
            self._save_all_budgets()

    def _save_all_budgets(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for b in self._budgets.values():
            c.execute("""
                INSERT OR REPLACE INTO risk_budgets
                (name, budget_type, max_var_pct, max_drawdown_pct, max_position_pct, max_gross_exposure_pct)
                VALUES (?,?,?,?,?,?)
            """, (b.name, b.budget_type, b.max_var_pct, b.max_drawdown_pct, b.max_position_pct, b.max_gross_exposure_pct))
        conn.commit()
        conn.close()

    # ---------------------------------------------------------- public API

    def get_all_budgets(self) -> List[Dict[str, Any]]:
        """Return all risk budgets with current utilization."""
        return [b.to_dict() for b in self._budgets.values()]

    def get_budget(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific budget."""
        b = self._budgets.get(name)
        return b.to_dict() if b else None

    def update_budget(self, name: str, **kwargs) -> bool:
        """Update budget limits."""
        if name not in self._budgets:
            return False
        b = self._budgets[name]
        for k, v in kwargs.items():
            if hasattr(b, k) and k != "name":
                setattr(b, k, v)
        self._save_all_budgets()
        return True

    def check_budgets(
        self,
        positions: List[Dict[str, Any]],
        total_equity: float,
        current_drawdown_pct: float = 0.0,
        var_95_pct: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Check all budgets against current portfolio state.

        Returns:
            Dict with budget utilizations, alerts, and scaling recommendations.
        """
        alerts: List[BudgetAlert] = []
        scale_recs: List[ScaleRecommendation] = []
        utilizations: Dict[str, Dict[str, Any]] = {}

        # Group positions by strategy
        strategy_exposure: Dict[str, float] = {}
        for pos in positions:
            strat = pos.get("strategy", "unknown")
            val = pos.get("market_value", 0)
            strategy_exposure[strat] = strategy_exposure.get(strat, 0) + val

        for name, budget in self._budgets.items():
            exposure = strategy_exposure.get(name, 0)
            exposure_pct = (exposure / total_equity * 100) if total_equity > 0 else 0

            # Calculate utilization for each metric
            metrics = {}

            # Exposure utilization
            exp_util = (exposure_pct / budget.max_gross_exposure_pct * 100) if budget.max_gross_exposure_pct > 0 else 0
            metrics["exposure"] = {
                "current": exposure_pct,
                "limit": budget.max_gross_exposure_pct,
                "utilization": min(exp_util, 200),
            }

            # VaR utilization (proportional allocation)
            n_budgets = max(len(self._budgets), 1)
            allocated_var = var_95_pct / n_budgets  # simple equal allocation
            var_util = (allocated_var / budget.max_var_pct * 100) if budget.max_var_pct > 0 else 0
            metrics["var"] = {
                "current": allocated_var,
                "limit": budget.max_var_pct,
                "utilization": min(var_util, 200),
            }

            # Drawdown utilization
            dd_util = (current_drawdown_pct / budget.max_drawdown_pct * 100) if budget.max_drawdown_pct > 0 else 0
            metrics["drawdown"] = {
                "current": current_drawdown_pct,
                "limit": budget.max_drawdown_pct,
                "utilization": min(dd_util, 200),
            }

            # Overall utilization = max of individual utilizations
            overall_util = max(
                exp_util, var_util, dd_util
            )
            budget.current_utilization = min(overall_util, 200)

            utilizations[name] = {
                "budget": budget.to_dict(),
                "metrics": metrics,
                "overall_utilization": round(overall_util, 1),
            }

            # Generate alerts
            for metric_name, metric_data in metrics.items():
                util = metric_data["utilization"]
                if util >= 100:
                    alerts.append(BudgetAlert(
                        budget_name=name,
                        metric=metric_name,
                        current_value=metric_data["current"],
                        limit_value=metric_data["limit"],
                        utilization_pct=util,
                        severity="critical",
                        message=f"{name}: {metric_name} budget BREACHED ({util:.0f}% utilized)",
                    ))
                elif util >= 80:
                    alerts.append(BudgetAlert(
                        budget_name=name,
                        metric=metric_name,
                        current_value=metric_data["current"],
                        limit_value=metric_data["limit"],
                        utilization_pct=util,
                        severity="warning",
                        message=f"{name}: {metric_name} approaching limit ({util:.0f}% utilized)",
                    ))

            # Generate scaling recommendations if over budget
            if overall_util > 90 and exposure_pct > 0:
                target_exposure = budget.max_gross_exposure_pct * 0.85  # target 85% utilization
                scale = target_exposure / exposure_pct if exposure_pct > 0 else 1.0
                scale = min(scale, 1.0)  # only scale down, never up

                if scale < 1.0:
                    scale_recs.append(ScaleRecommendation(
                        strategy=name,
                        current_exposure_pct=exposure_pct,
                        recommended_exposure_pct=target_exposure,
                        scale_factor=scale,
                        reason=f"Budget utilization at {overall_util:.0f}%, recommend scaling to {target_exposure:.1f}%",
                    ))

        # Persist utilization snapshot
        self._persist_utilization(utilizations)

        return {
            "utilizations": utilizations,
            "alerts": [a.to_dict() for a in alerts],
            "scale_recommendations": [s.to_dict() for s in scale_recs],
            "total_budgets": len(self._budgets),
            "budgets_over_limit": sum(1 for u in utilizations.values() if u["overall_utilization"] >= 100),
            "budgets_approaching": sum(1 for u in utilizations.values() if 80 <= u["overall_utilization"] < 100),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_utilization_history(self, budget_name: str = None, limit: int = 60) -> List[Dict[str, Any]]:
        """Return utilization history for trending."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if budget_name:
            c.execute("""
                SELECT timestamp, budget_name, utilization_pct, var_used, drawdown_used, exposure_used
                FROM budget_utilization_history
                WHERE budget_name = ?
                ORDER BY id DESC LIMIT ?
            """, (budget_name, limit))
        else:
            c.execute("""
                SELECT timestamp, budget_name, utilization_pct, var_used, drawdown_used, exposure_used
                FROM budget_utilization_history
                ORDER BY id DESC LIMIT ?
            """, (limit,))
        rows = c.fetchall()
        conn.close()

        return [
            {
                "timestamp": r[0],
                "budget_name": r[1],
                "utilization_pct": round(r[2] or 0, 1),
                "var_used": round(r[3] or 0, 2),
                "drawdown_used": round(r[4] or 0, 2),
                "exposure_used": round(r[5] or 0, 2),
            }
            for r in reversed(rows)
        ]

    # -------------------------------------------------------- internal

    def _persist_utilization(self, utilizations: Dict[str, Dict[str, Any]]):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        ts = datetime.utcnow().isoformat()
        for name, data in utilizations.items():
            metrics = data.get("metrics", {})
            c.execute("""
                INSERT INTO budget_utilization_history
                (timestamp, budget_name, utilization_pct, var_used, drawdown_used, exposure_used)
                VALUES (?,?,?,?,?,?)
            """, (
                ts, name, data.get("overall_utilization", 0),
                metrics.get("var", {}).get("current", 0),
                metrics.get("drawdown", {}).get("current", 0),
                metrics.get("exposure", {}).get("current", 0),
            ))
        conn.commit()
        conn.close()


# --------------------------------------------------------------------- singleton
_instance: Optional[RiskBudgetManager] = None


def get_risk_budget_manager() -> RiskBudgetManager:
    global _instance
    if _instance is None:
        _instance = RiskBudgetManager()
    return _instance
