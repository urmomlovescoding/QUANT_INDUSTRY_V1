"""
QUANT INDUSTRY - Scenario Analysis Engine
Historical replay, custom stress tests, and correlation breakdown scenarios.

Supports:
  - Historical scenario replay (March 2020 crash, Aug 2015, 2008 GFC)
  - Custom stress tests (VIX spikes, rate shocks, sector drawdowns)
  - Correlation breakdown (what-if correlations go to 1)
  - Persisted scenario results for comparison
"""

import logging
import math
import os
import sqlite3
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Historical scenario definitions
# ---------------------------------------------------------------------------

HISTORICAL_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "covid_crash_2020": {
        "name": "COVID Crash (Mar 2020)",
        "description": "Market-wide selloff driven by pandemic fears. SPY fell ~34% from peak.",
        "market_shock_pct": -34.0,
        "vix_level": 82.69,
        "duration_days": 23,
        "sector_shocks": {
            "technology": -28.0,
            "healthcare": -20.0,
            "financials": -40.0,
            "consumer_discretionary": -38.0,
            "consumer_staples": -18.0,
            "energy": -55.0,
            "industrials": -38.0,
            "materials": -30.0,
            "utilities": -25.0,
            "real_estate": -30.0,
            "communication": -25.0,
            "unknown": -34.0,
        },
        "correlation_multiplier": 1.8,
    },
    "gfc_2008": {
        "name": "Global Financial Crisis (2008)",
        "description": "Banking sector collapse, credit freeze. SPY fell ~57% from peak over 17 months.",
        "market_shock_pct": -57.0,
        "vix_level": 80.86,
        "duration_days": 355,
        "sector_shocks": {
            "technology": -45.0,
            "healthcare": -30.0,
            "financials": -75.0,
            "consumer_discretionary": -55.0,
            "consumer_staples": -25.0,
            "energy": -50.0,
            "industrials": -50.0,
            "materials": -55.0,
            "utilities": -35.0,
            "real_estate": -65.0,
            "communication": -40.0,
            "unknown": -57.0,
        },
        "correlation_multiplier": 2.0,
    },
    "china_devalue_2015": {
        "name": "China Devaluation (Aug 2015)",
        "description": "China devalues yuan, global growth fears. SPY fell ~12% in 6 days.",
        "market_shock_pct": -12.0,
        "vix_level": 53.29,
        "duration_days": 6,
        "sector_shocks": {
            "technology": -10.0,
            "healthcare": -8.0,
            "financials": -14.0,
            "consumer_discretionary": -13.0,
            "consumer_staples": -6.0,
            "energy": -18.0,
            "industrials": -15.0,
            "materials": -20.0,
            "utilities": -5.0,
            "real_estate": -8.0,
            "communication": -10.0,
            "unknown": -12.0,
        },
        "correlation_multiplier": 1.5,
    },
    "volmageddon_2018": {
        "name": "Volmageddon (Feb 2018)",
        "description": "VIX spike crushed short-vol products. SPY fell ~10% in 2 weeks.",
        "market_shock_pct": -10.0,
        "vix_level": 50.30,
        "duration_days": 9,
        "sector_shocks": {
            "technology": -9.0,
            "healthcare": -8.0,
            "financials": -12.0,
            "consumer_discretionary": -10.0,
            "consumer_staples": -7.0,
            "energy": -11.0,
            "industrials": -11.0,
            "materials": -10.0,
            "utilities": -6.0,
            "real_estate": -9.0,
            "communication": -9.0,
            "unknown": -10.0,
        },
        "correlation_multiplier": 1.6,
    },
    "rate_hike_2022": {
        "name": "Rate Hike Selloff (2022)",
        "description": "Fed aggressive tightening. SPY fell ~25% with growth/tech leading losses.",
        "market_shock_pct": -25.0,
        "vix_level": 36.45,
        "duration_days": 190,
        "sector_shocks": {
            "technology": -33.0,
            "healthcare": -10.0,
            "financials": -18.0,
            "consumer_discretionary": -35.0,
            "consumer_staples": -5.0,
            "energy": 25.0,
            "industrials": -15.0,
            "materials": -12.0,
            "utilities": -3.0,
            "real_estate": -28.0,
            "communication": -40.0,
            "unknown": -25.0,
        },
        "correlation_multiplier": 1.3,
    },
}


@dataclass
class ScenarioResult:
    """Result of running a single scenario against the portfolio."""
    scenario_id: str
    scenario_name: str
    description: str
    timestamp: str
    portfolio_value_before: float
    portfolio_value_after: float
    total_pnl: float
    total_pnl_pct: float
    worst_position: str
    worst_position_pnl: float
    best_position: str
    best_position_pnl: float
    position_impacts: List[Dict[str, Any]]
    vix_level: float
    duration_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "description": self.description,
            "timestamp": self.timestamp,
            "portfolio_value_before": round(self.portfolio_value_before, 2),
            "portfolio_value_after": round(self.portfolio_value_after, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "worst_position": self.worst_position,
            "worst_position_pnl": round(self.worst_position_pnl, 2),
            "best_position": self.best_position,
            "best_position_pnl": round(self.best_position_pnl, 2),
            "position_impacts": self.position_impacts,
            "vix_level": self.vix_level,
            "duration_days": self.duration_days,
        }


class ScenarioEngine:
    """
    Scenario analysis engine for portfolio stress testing.
    Applies historical or custom shocks to current portfolio holdings.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "scenarios.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        logger.info("ScenarioEngine initialized")

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS scenario_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                portfolio_value_before REAL,
                portfolio_value_after REAL,
                total_pnl REAL,
                total_pnl_pct REAL,
                details TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS custom_scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                config TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ---------------------------------------------------------- public API

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """List all available scenarios (built-in + custom)."""
        scenarios = []
        for sid, s in HISTORICAL_SCENARIOS.items():
            scenarios.append({
                "id": sid,
                "name": s["name"],
                "description": s["description"],
                "type": "historical",
                "market_shock_pct": s["market_shock_pct"],
                "vix_level": s["vix_level"],
                "duration_days": s["duration_days"],
            })

        # Add custom scenarios from DB
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, name, description, config FROM custom_scenarios")
        for row in c.fetchall():
            cfg = json.loads(row[3])
            scenarios.append({
                "id": row[0],
                "name": row[1],
                "description": row[2] or "",
                "type": "custom",
                "market_shock_pct": cfg.get("market_shock_pct", 0),
                "vix_level": cfg.get("vix_level", 20),
                "duration_days": cfg.get("duration_days", 1),
            })
        conn.close()
        return scenarios

    def run_scenario(
        self,
        scenario_id: str,
        positions: List[Dict[str, Any]],
        total_equity: float,
    ) -> ScenarioResult:
        """
        Run a historical or custom scenario against the portfolio.

        Args:
            scenario_id: key from HISTORICAL_SCENARIOS or custom scenario id
            positions: list of position dicts with 'symbol', 'market_value', 'sector'
            total_equity: current total portfolio equity
        """
        scenario = self._get_scenario_config(scenario_id)
        if scenario is None:
            raise ValueError(f"Unknown scenario: {scenario_id}")

        return self._apply_scenario(scenario_id, scenario, positions, total_equity)

    def run_custom_stress(
        self,
        name: str,
        market_shock_pct: float = 0.0,
        vix_spike_pct: float = 0.0,
        rate_move_bps: float = 0.0,
        sector_overrides: Optional[Dict[str, float]] = None,
        correlation_to_one: bool = False,
        positions: List[Dict[str, Any]] = None,
        total_equity: float = 0.0,
    ) -> ScenarioResult:
        """
        Run a custom stress test.

        Args:
            name: descriptive name for the stress test
            market_shock_pct: market-wide percentage shock
            vix_spike_pct: VIX percentage increase
            rate_move_bps: interest rate move in basis points
            sector_overrides: per-sector shock overrides
            correlation_to_one: if True, assume all correlations go to 1
            positions: portfolio positions
            total_equity: current equity
        """
        positions = positions or []

        # Build effective sector shocks
        base_shock = market_shock_pct
        if vix_spike_pct > 0:
            # Empirical: 10% VIX spike ~= -1.5% market
            base_shock -= vix_spike_pct * 0.15

        if rate_move_bps != 0:
            # Empirical: +100bps rate move ~= -5% equities, growth harder hit
            rate_impact = -(rate_move_bps / 100) * 5.0
            base_shock += rate_impact

        sector_shocks = {}
        sectors = [
            "technology", "healthcare", "financials", "consumer_discretionary",
            "consumer_staples", "energy", "industrials", "materials",
            "utilities", "real_estate", "communication", "unknown",
        ]
        # Sensitivity multipliers for rate moves
        rate_sensitivity = {
            "technology": 1.4,
            "real_estate": 1.5,
            "utilities": 1.2,
            "consumer_discretionary": 1.2,
            "financials": 0.7,
            "energy": 0.5,
            "consumer_staples": 0.6,
            "healthcare": 0.8,
            "industrials": 1.0,
            "materials": 1.0,
            "communication": 1.3,
            "unknown": 1.0,
        }

        for sec in sectors:
            if sector_overrides and sec in sector_overrides:
                sector_shocks[sec] = sector_overrides[sec]
            else:
                mult = rate_sensitivity.get(sec, 1.0)
                sector_shocks[sec] = base_shock * mult

        corr_mult = 2.0 if correlation_to_one else 1.0

        scenario_config = {
            "name": name,
            "description": f"Custom stress: mkt={market_shock_pct}%, VIX+{vix_spike_pct}%, rates={rate_move_bps}bps",
            "market_shock_pct": base_shock,
            "vix_level": 20 * (1 + vix_spike_pct / 100),
            "duration_days": 1,
            "sector_shocks": sector_shocks,
            "correlation_multiplier": corr_mult,
        }

        return self._apply_scenario("custom", scenario_config, positions, total_equity)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent scenario run results."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT scenario_id, scenario_name, timestamp,
                   portfolio_value_before, portfolio_value_after,
                   total_pnl, total_pnl_pct
            FROM scenario_results
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()

        return [
            {
                "scenario_id": r[0],
                "scenario_name": r[1],
                "timestamp": r[2],
                "portfolio_value_before": round(r[3] or 0, 2),
                "portfolio_value_after": round(r[4] or 0, 2),
                "total_pnl": round(r[5] or 0, 2),
                "total_pnl_pct": round(r[6] or 0, 2),
            }
            for r in rows
        ]

    # -------------------------------------------------------- internal

    def _get_scenario_config(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        if scenario_id in HISTORICAL_SCENARIOS:
            return HISTORICAL_SCENARIOS[scenario_id]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT config FROM custom_scenarios WHERE id = ?", (scenario_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None

    def _apply_scenario(
        self,
        scenario_id: str,
        config: Dict[str, Any],
        positions: List[Dict[str, Any]],
        total_equity: float,
    ) -> ScenarioResult:
        """Apply scenario shocks to portfolio positions."""
        from services.risk_service import get_sector_tracker

        tracker = get_sector_tracker()
        sector_shocks = config.get("sector_shocks", {})
        market_shock = config.get("market_shock_pct", 0)
        corr_mult = config.get("correlation_multiplier", 1.0)

        position_impacts = []
        total_pnl = 0.0
        worst_sym, worst_pnl = "", 0.0
        best_sym, best_pnl = "", 0.0

        for pos in positions:
            sym = pos.get("symbol", "UNKNOWN")
            val = pos.get("market_value", 0)
            sector = tracker.get_sector(sym).value

            # Get the sector-specific shock, fall back to market shock
            shock_pct = sector_shocks.get(sector, market_shock)

            # Apply correlation multiplier for concentrated portfolios
            # Higher correlation means less diversification benefit
            effective_shock = shock_pct * min(corr_mult, 2.0) / max(corr_mult, 1.0)
            # Clamp to not exceed the raw shock magnitude too much
            if abs(effective_shock) > abs(shock_pct) * 1.5:
                effective_shock = shock_pct * 1.5 * (1 if shock_pct >= 0 else -1)

            pnl = val * (effective_shock / 100)
            total_pnl += pnl

            position_impacts.append({
                "symbol": sym,
                "market_value": round(val, 2),
                "sector": sector,
                "shock_pct": round(effective_shock, 2),
                "pnl": round(pnl, 2),
            })

            if pnl < worst_pnl:
                worst_pnl = pnl
                worst_sym = sym
            if pnl > best_pnl:
                best_pnl = pnl
                best_sym = sym

        portfolio_after = total_equity + total_pnl
        total_pnl_pct = (total_pnl / total_equity * 100) if total_equity > 0 else 0

        result = ScenarioResult(
            scenario_id=scenario_id,
            scenario_name=config.get("name", scenario_id),
            description=config.get("description", ""),
            timestamp=datetime.utcnow().isoformat(),
            portfolio_value_before=total_equity,
            portfolio_value_after=portfolio_after,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            worst_position=worst_sym,
            worst_position_pnl=worst_pnl,
            best_position=best_sym or worst_sym,
            best_position_pnl=best_pnl,
            position_impacts=position_impacts,
            vix_level=config.get("vix_level", 20),
            duration_days=config.get("duration_days", 1),
        )

        self._persist_result(result)
        return result

    def _persist_result(self, result: ScenarioResult):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO scenario_results
            (scenario_id, scenario_name, timestamp,
             portfolio_value_before, portfolio_value_after,
             total_pnl, total_pnl_pct, details)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            result.scenario_id, result.scenario_name, result.timestamp,
            result.portfolio_value_before, result.portfolio_value_after,
            result.total_pnl, result.total_pnl_pct,
            json.dumps(result.position_impacts),
        ))
        conn.commit()
        conn.close()


# --------------------------------------------------------------------- singleton
_instance: Optional[ScenarioEngine] = None


def get_scenario_engine() -> ScenarioEngine:
    global _instance
    if _instance is None:
        _instance = ScenarioEngine()
    return _instance
