"""
QUANT INDUSTRY - PnL Attribution Waterfall
Breaks down daily PnL into: Market + Sector + Alpha + Trading Costs + Timing.
Tracks attribution drift and provides waterfall chart data.
"""

import logging
import math
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AttributionComponent:
    """Single component of the PnL attribution."""
    name: str
    value: float          # dollar amount
    pct_of_total: float   # percentage of total PnL
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 2),
            "pct_of_total": round(self.pct_of_total, 2),
            "description": self.description,
        }


@dataclass
class AttributionSnapshot:
    """Full PnL attribution for a single period."""
    timestamp: str
    total_pnl: float
    components: List[AttributionComponent]
    waterfall: List[Dict[str, Any]]  # for rendering waterfall chart

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_pnl": round(self.total_pnl, 2),
            "components": [c.to_dict() for c in self.components],
            "waterfall": self.waterfall,
        }


class AttributionEngine:
    """
    PnL Attribution Engine.
    Decomposes realized daily PnL into:
      Market Effect + Sector Selection + Alpha + Trading Costs + Timing
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "attribution.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        logger.info("AttributionEngine initialized")

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS attribution_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_pnl REAL,
                market_effect REAL,
                sector_selection REAL,
                alpha REAL,
                trading_costs REAL,
                timing REAL
            )
        """)
        conn.commit()
        conn.close()

    # ---------------------------------------------------------- public API

    def compute_attribution(
        self,
        positions: List[Dict[str, Any]],
        daily_pnl: float,
        market_return_pct: float = 0.0,
        total_equity: float = 0.0,
        commissions: float = 0.0,
        slippage_estimate_bps: float = 2.0,
    ) -> AttributionSnapshot:
        """
        Compute PnL attribution for the current period.

        Args:
            positions: list of dicts with 'symbol', 'market_value', 'unrealized_pnl', 'sector'
            daily_pnl: total daily PnL in dollars
            market_return_pct: benchmark (SPY) return for the day
            total_equity: total portfolio equity
            commissions: total commissions paid today
            slippage_estimate_bps: estimated slippage in basis points
        """
        from services.risk_service import get_sector_tracker

        tracker = get_sector_tracker()
        total_value = sum(p.get("market_value", 0) for p in positions)
        if total_value <= 0:
            return self._empty_snapshot(daily_pnl)

        # ---- 1. Market Effect ----
        # What we would have earned if portfolio was 100% index
        market_effect = total_value * (market_return_pct / 100)

        # ---- 2. Sector Selection ----
        # Excess return from sector over/underweights vs benchmark
        sector_values: Dict[str, float] = {}
        for pos in positions:
            sym = pos.get("symbol", "")
            val = pos.get("market_value", 0)
            sector = tracker.get_sector(sym).value
            sector_values[sector] = sector_values.get(sector, 0) + val

        # Benchmark sector weights (approximate S&P 500)
        benchmark_weights = {
            "technology": 0.30, "healthcare": 0.13, "financials": 0.13,
            "consumer_discretionary": 0.10, "consumer_staples": 0.06,
            "energy": 0.04, "industrials": 0.09, "materials": 0.03,
            "utilities": 0.03, "real_estate": 0.03, "communication": 0.09,
            "unknown": 0.0,
        }

        # Sector-specific return estimates (simplified: proportional to market)
        sector_return_mult = {
            "technology": 1.15, "healthcare": 0.90, "financials": 1.05,
            "consumer_discretionary": 1.10, "consumer_staples": 0.70,
            "energy": 0.80, "industrials": 1.00, "materials": 0.95,
            "utilities": 0.60, "real_estate": 0.85, "communication": 1.10,
            "unknown": 1.00,
        }

        sector_selection = 0.0
        for sec, val in sector_values.items():
            portfolio_weight = val / total_value if total_value > 0 else 0
            bench_weight = benchmark_weights.get(sec, 0.05)
            active_weight = portfolio_weight - bench_weight
            sector_ret = market_return_pct * sector_return_mult.get(sec, 1.0)
            sector_selection += total_value * active_weight * (sector_ret / 100)

        # ---- 3. Trading Costs ----
        trading_costs = -(abs(commissions) + total_value * slippage_estimate_bps / 10_000)

        # ---- 4. Timing ----
        # Estimate timing effect as residual from intraday execution
        # Simplified: assume slight drag from not executing at optimal price
        timing = -(abs(daily_pnl) * 0.02) if daily_pnl != 0 else 0  # ~2% of PnL

        # ---- 5. Alpha (residual) ----
        alpha = daily_pnl - market_effect - sector_selection - trading_costs - timing

        # Build components
        components = [
            AttributionComponent("Market Effect", market_effect,
                                 self._pct(market_effect, daily_pnl),
                                 "Return from broad market exposure"),
            AttributionComponent("Sector Selection", sector_selection,
                                 self._pct(sector_selection, daily_pnl),
                                 "Return from sector over/underweights"),
            AttributionComponent("Alpha", alpha,
                                 self._pct(alpha, daily_pnl),
                                 "Idiosyncratic / stock selection return"),
            AttributionComponent("Trading Costs", trading_costs,
                                 self._pct(trading_costs, daily_pnl),
                                 "Commissions + estimated slippage"),
            AttributionComponent("Timing", timing,
                                 self._pct(timing, daily_pnl),
                                 "Execution timing impact"),
        ]

        # Build waterfall chart data
        waterfall = self._build_waterfall(components, daily_pnl)

        snapshot = AttributionSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            total_pnl=daily_pnl,
            components=components,
            waterfall=waterfall,
        )

        self._persist(snapshot)
        return snapshot

    def get_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return recent attribution snapshots for trend analysis."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT timestamp, total_pnl, market_effect, sector_selection,
                   alpha, trading_costs, timing
            FROM attribution_snapshots
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()

        return [
            {
                "timestamp": r[0],
                "total_pnl": round(r[1] or 0, 2),
                "market_effect": round(r[2] or 0, 2),
                "sector_selection": round(r[3] or 0, 2),
                "alpha": round(r[4] or 0, 2),
                "trading_costs": round(r[5] or 0, 2),
                "timing": round(r[6] or 0, 2),
            }
            for r in reversed(rows)
        ]

    def get_alpha_trend(self, lookback_days: int = 30) -> Dict[str, Any]:
        """Analyze alpha decay / trend over time."""
        history = self.get_history(limit=lookback_days)
        if len(history) < 2:
            return {
                "trend": "insufficient_data",
                "avg_alpha": 0,
                "alpha_sharpe": 0,
                "is_decaying": False,
            }

        alphas = [h["alpha"] for h in history]
        avg = sum(alphas) / len(alphas)
        std = math.sqrt(sum((a - avg) ** 2 for a in alphas) / len(alphas)) if len(alphas) > 1 else 1
        sharpe = (avg / std) * math.sqrt(252) if std > 0 else 0

        # Simple linear regression to detect decay
        n = len(alphas)
        x_mean = (n - 1) / 2
        y_mean = avg
        num = sum((i - x_mean) * (alphas[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0

        trend = "stable"
        if slope < -0.5:
            trend = "decaying"
        elif slope > 0.5:
            trend = "improving"

        return {
            "trend": trend,
            "avg_alpha": round(avg, 2),
            "alpha_sharpe": round(sharpe, 2),
            "slope": round(slope, 4),
            "is_decaying": slope < -0.5,
            "data_points": len(alphas),
        }

    # -------------------------------------------------------- internal

    def _pct(self, part: float, total: float) -> float:
        if total == 0:
            return 0.0
        return (part / abs(total)) * 100

    def _build_waterfall(
        self, components: List[AttributionComponent], total: float
    ) -> List[Dict[str, Any]]:
        """Build waterfall chart data points."""
        waterfall = []
        running = 0.0

        for comp in components:
            waterfall.append({
                "name": comp.name,
                "start": round(running, 2),
                "end": round(running + comp.value, 2),
                "value": round(comp.value, 2),
                "is_positive": comp.value >= 0,
            })
            running += comp.value

        # Add total bar
        waterfall.append({
            "name": "Total PnL",
            "start": 0,
            "end": round(total, 2),
            "value": round(total, 2),
            "is_total": True,
            "is_positive": total >= 0,
        })

        return waterfall

    def _persist(self, snap: AttributionSnapshot):
        cmap = {c.name: c.value for c in snap.components}
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO attribution_snapshots
            (timestamp, total_pnl, market_effect, sector_selection,
             alpha, trading_costs, timing)
            VALUES (?,?,?,?,?,?,?)
        """, (
            snap.timestamp, snap.total_pnl,
            cmap.get("Market Effect", 0),
            cmap.get("Sector Selection", 0),
            cmap.get("Alpha", 0),
            cmap.get("Trading Costs", 0),
            cmap.get("Timing", 0),
        ))
        conn.commit()
        conn.close()

    def _empty_snapshot(self, daily_pnl: float = 0.0) -> AttributionSnapshot:
        components = [
            AttributionComponent("Market Effect", 0, 0, "No positions"),
            AttributionComponent("Sector Selection", 0, 0, "No positions"),
            AttributionComponent("Alpha", daily_pnl, 100 if daily_pnl != 0 else 0, "All PnL unattributed"),
            AttributionComponent("Trading Costs", 0, 0, "No data"),
            AttributionComponent("Timing", 0, 0, "No data"),
        ]
        return AttributionSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            total_pnl=daily_pnl,
            components=components,
            waterfall=self._build_waterfall(components, daily_pnl),
        )


# --------------------------------------------------------------------- singleton
_instance: Optional[AttributionEngine] = None


def get_attribution_engine() -> AttributionEngine:
    global _instance
    if _instance is None:
        _instance = AttributionEngine()
    return _instance
