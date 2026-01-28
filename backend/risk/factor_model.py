"""
QUANT INDUSTRY - Multi-Factor Risk Model
Decomposes portfolio returns into factor exposures and tracks factor drift.

Factors:
  - Market Beta: Sensitivity to broad market (SPY)
  - Sector: GICS sector tilts relative to benchmark
  - Momentum: Exposure to momentum factor (winners vs losers)
  - Volatility: Exposure to low-vol vs high-vol names
  - Size: Exposure to small-cap vs large-cap
"""

import logging
import math
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factor definitions
# ---------------------------------------------------------------------------

FACTOR_NAMES = ["market", "sector", "momentum", "volatility", "size"]

# Market-cap buckets (approximate, in $B)
LARGE_CAP_SYMBOLS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "BRK.B",
    "JPM", "JNJ", "V", "UNH", "XOM", "MA", "PG", "HD", "CVX", "LLY",
    "MRK", "ABBV", "PEP", "KO", "AVGO", "COST", "WMT", "CSCO", "CRM",
    "ADBE", "ORCL", "NFLX", "AMD", "INTC", "QCOM",
}

SMALL_CAP_SYMBOLS = {
    "PLTR", "COIN", "SQ", "RIVN", "SOFI", "LCID", "DKNG", "MARA",
    "RIOT", "UPST", "AFRM", "RBLX", "U", "CRWD", "SNOW",
}

# Momentum scores (simplified: recent 6-month performance bucket)
HIGH_MOMENTUM = {
    "NVDA", "META", "AVGO", "LLY", "NFLX", "PLTR", "AMD", "CRM",
    "PANW", "CRWD", "NOW", "ANET", "GE",
}

LOW_MOMENTUM = {
    "PFE", "BMY", "INTC", "BA", "VZ", "T", "WBA", "PYPL",
}

# Volatility buckets (annualized vol)
HIGH_VOL_SYMBOLS = {
    "TSLA", "COIN", "RIVN", "SQ", "PLTR", "AMD", "NVDA", "MARA",
    "RIOT", "LCID", "DKNG", "SOFI",
}

LOW_VOL_SYMBOLS = {
    "JNJ", "PG", "KO", "PEP", "WMT", "COST", "UNH", "D",
    "SO", "DUK", "NEE", "AEP",
}


@dataclass
class FactorExposure:
    """Single factor exposure for a position or portfolio."""
    factor: str
    exposure: float        # beta / loading
    contribution: float    # contribution to total return (bps)
    pct_of_risk: float     # percentage of portfolio risk explained

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor": self.factor,
            "exposure": round(self.exposure, 4),
            "contribution_bps": round(self.contribution, 2),
            "pct_of_risk": round(self.pct_of_risk, 2),
        }


@dataclass
class FactorSnapshot:
    """Point-in-time factor decomposition of the portfolio."""
    timestamp: str
    total_return_bps: float
    factors: List[FactorExposure]
    residual_bps: float    # alpha / idiosyncratic
    r_squared: float       # how much of return is explained by factors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_return_bps": round(self.total_return_bps, 2),
            "factors": [f.to_dict() for f in self.factors],
            "residual_bps": round(self.residual_bps, 2),
            "r_squared": round(self.r_squared, 4),
        }


class FactorRiskModel:
    """
    Multi-factor risk model for portfolio decomposition.

    Decomposes portfolio returns / risk into:
      Market + Sector + Momentum + Volatility + Size + Residual(Alpha)
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "risk_factors.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        logger.info("FactorRiskModel initialized")

    # ------------------------------------------------------------------ DB
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS factor_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_return_bps REAL,
                market_exposure REAL,
                market_contribution REAL,
                sector_exposure REAL,
                sector_contribution REAL,
                momentum_exposure REAL,
                momentum_contribution REAL,
                volatility_exposure REAL,
                volatility_contribution REAL,
                size_exposure REAL,
                size_contribution REAL,
                residual_bps REAL,
                r_squared REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS factor_drift (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                factor TEXT NOT NULL,
                exposure_30d REAL,
                exposure_7d REAL,
                drift REAL
            )
        """)
        conn.commit()
        conn.close()

    # ------------------------------------------------------ core analytics

    def _get_symbol_factor_scores(self, symbol: str) -> Dict[str, float]:
        """Return factor scores for a single symbol (heuristic-based)."""
        sym = symbol.upper()
        scores: Dict[str, float] = {}

        # Market beta estimate
        if sym in {"SPY", "IVV", "VOO"}:
            scores["market"] = 1.0
        elif sym in HIGH_VOL_SYMBOLS:
            scores["market"] = 1.3
        elif sym in LOW_VOL_SYMBOLS:
            scores["market"] = 0.65
        else:
            scores["market"] = 1.0

        # Momentum
        if sym in HIGH_MOMENTUM:
            scores["momentum"] = 1.0
        elif sym in LOW_MOMENTUM:
            scores["momentum"] = -1.0
        else:
            scores["momentum"] = 0.0

        # Volatility factor (positive = high vol tilt)
        if sym in HIGH_VOL_SYMBOLS:
            scores["volatility"] = 1.0
        elif sym in LOW_VOL_SYMBOLS:
            scores["volatility"] = -1.0
        else:
            scores["volatility"] = 0.0

        # Size factor (positive = small cap tilt)
        if sym in SMALL_CAP_SYMBOLS:
            scores["size"] = 1.0
        elif sym in LARGE_CAP_SYMBOLS:
            scores["size"] = -0.5
        else:
            scores["size"] = 0.0

        # Sector factor is computed at portfolio level
        scores["sector"] = 0.0

        return scores

    def _compute_sector_tilt(
        self, positions: List[Dict[str, Any]], total_value: float
    ) -> float:
        """Compute sector concentration tilt vs equal-weight benchmark."""
        from services.risk_service import get_sector_tracker

        tracker = get_sector_tracker()
        sector_weights: Dict[str, float] = {}

        for pos in positions:
            sym = pos.get("symbol", "")
            val = pos.get("market_value", 0)
            if total_value <= 0 or val <= 0:
                continue
            sector = tracker.get_sector(sym).value
            sector_weights[sector] = sector_weights.get(sector, 0) + val / total_value

        if not sector_weights:
            return 0.0

        # HHI-based tilt: deviation from equal weight
        n = max(len(sector_weights), 1)
        equal = 1.0 / n
        tilt = sum((w - equal) ** 2 for w in sector_weights.values())
        return math.sqrt(tilt) * 10  # scale for readability

    def decompose(
        self,
        positions: List[Dict[str, Any]],
        daily_pnl: float = 0.0,
        market_return_bps: float = 0.0,
    ) -> FactorSnapshot:
        """
        Decompose current portfolio into factor exposures.

        Args:
            positions: list of dicts with 'symbol', 'market_value', 'unrealized_pnl'
            daily_pnl: total portfolio daily P&L in dollars
            market_return_bps: today's SPY return in basis points
        """
        total_value = sum(p.get("market_value", 0) for p in positions)
        if total_value <= 0:
            return self._empty_snapshot()

        total_return_bps = (daily_pnl / total_value) * 10_000 if total_value else 0.0

        # Weighted-average factor exposures
        weighted: Dict[str, float] = {f: 0.0 for f in FACTOR_NAMES}

        for pos in positions:
            sym = pos.get("symbol", "")
            val = pos.get("market_value", 0)
            w = val / total_value if total_value else 0

            scores = self._get_symbol_factor_scores(sym)
            for factor in FACTOR_NAMES:
                if factor != "sector":
                    weighted[factor] += w * scores.get(factor, 0.0)

        # Sector tilt computed separately
        weighted["sector"] = self._compute_sector_tilt(positions, total_value)

        # Estimate factor contributions to PnL
        factor_return_estimates = {
            "market": weighted["market"] * market_return_bps,
            "sector": weighted["sector"] * market_return_bps * 0.3,
            "momentum": weighted["momentum"] * 2.0,     # avg daily momentum premium ~2bps
            "volatility": weighted["volatility"] * -1.5,  # vol factor typically -1.5bps/day
            "size": weighted["size"] * 1.0,               # size premium ~1bps/day
        }

        explained = sum(factor_return_estimates.values())
        residual = total_return_bps - explained
        total_var = sum(v ** 2 for v in factor_return_estimates.values()) + residual ** 2
        r_sq = 1.0 - (residual ** 2 / total_var) if total_var > 0 else 0.0

        factors = []
        for f in FACTOR_NAMES:
            contrib = factor_return_estimates[f]
            pct_risk = (contrib ** 2 / total_var * 100) if total_var > 0 else 0.0
            factors.append(FactorExposure(
                factor=f,
                exposure=weighted[f],
                contribution=contrib,
                pct_of_risk=pct_risk,
            ))

        snapshot = FactorSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            total_return_bps=total_return_bps,
            factors=factors,
            residual_bps=residual,
            r_squared=max(0, min(1, r_sq)),
        )

        self._persist_snapshot(snapshot)
        return snapshot

    def get_factor_drift(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """Return factor exposure drift over time."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
        c.execute("""
            SELECT timestamp,
                   market_exposure, sector_exposure, momentum_exposure,
                   volatility_exposure, size_exposure
            FROM factor_snapshots
            WHERE timestamp >= ?
            ORDER BY timestamp
        """, (cutoff,))
        rows = c.fetchall()
        conn.close()

        if len(rows) < 2:
            return []

        result = []
        for row in rows:
            result.append({
                "timestamp": row[0],
                "market": round(row[1] or 0, 4),
                "sector": round(row[2] or 0, 4),
                "momentum": round(row[3] or 0, 4),
                "volatility": round(row[4] or 0, 4),
                "size": round(row[5] or 0, 4),
            })
        return result

    def get_history(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Return recent factor snapshots."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT timestamp, total_return_bps,
                   market_contribution, sector_contribution,
                   momentum_contribution, volatility_contribution,
                   size_contribution, residual_bps, r_squared
            FROM factor_snapshots
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()

        return [
            {
                "timestamp": r[0],
                "total_return_bps": round(r[1] or 0, 2),
                "market": round(r[2] or 0, 2),
                "sector": round(r[3] or 0, 2),
                "momentum": round(r[4] or 0, 2),
                "volatility": round(r[5] or 0, 2),
                "size": round(r[6] or 0, 2),
                "residual": round(r[7] or 0, 2),
                "r_squared": round(r[8] or 0, 4),
            }
            for r in reversed(rows)
        ]

    # --------------------------------------------------------- persistence
    def _persist_snapshot(self, snap: FactorSnapshot):
        fmap = {f.factor: f for f in snap.factors}
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO factor_snapshots
            (timestamp, total_return_bps,
             market_exposure, market_contribution,
             sector_exposure, sector_contribution,
             momentum_exposure, momentum_contribution,
             volatility_exposure, volatility_contribution,
             size_exposure, size_contribution,
             residual_bps, r_squared)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snap.timestamp, snap.total_return_bps,
            fmap.get("market", FactorExposure("market", 0, 0, 0)).exposure,
            fmap.get("market", FactorExposure("market", 0, 0, 0)).contribution,
            fmap.get("sector", FactorExposure("sector", 0, 0, 0)).exposure,
            fmap.get("sector", FactorExposure("sector", 0, 0, 0)).contribution,
            fmap.get("momentum", FactorExposure("momentum", 0, 0, 0)).exposure,
            fmap.get("momentum", FactorExposure("momentum", 0, 0, 0)).contribution,
            fmap.get("volatility", FactorExposure("volatility", 0, 0, 0)).exposure,
            fmap.get("volatility", FactorExposure("volatility", 0, 0, 0)).contribution,
            fmap.get("size", FactorExposure("size", 0, 0, 0)).exposure,
            fmap.get("size", FactorExposure("size", 0, 0, 0)).contribution,
            snap.residual_bps, snap.r_squared,
        ))
        conn.commit()
        conn.close()

    def _empty_snapshot(self) -> FactorSnapshot:
        return FactorSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            total_return_bps=0.0,
            factors=[
                FactorExposure(f, 0.0, 0.0, 0.0) for f in FACTOR_NAMES
            ],
            residual_bps=0.0,
            r_squared=0.0,
        )


# --------------------------------------------------------------------- singleton
_instance: Optional[FactorRiskModel] = None


def get_factor_model() -> FactorRiskModel:
    global _instance
    if _instance is None:
        _instance = FactorRiskModel()
    return _instance
