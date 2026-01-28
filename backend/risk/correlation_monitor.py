"""
QUANT INDUSTRY - Enhanced Correlation Monitor
Rolling correlation matrix, regime change detection, and live diversification scoring.
"""

import logging
import math
import os
import sqlite3
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CorrelationRegime:
    """Describes a correlation regime period."""
    regime: str            # "low", "normal", "elevated", "crisis"
    avg_correlation: float
    start_date: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "avg_correlation": round(self.avg_correlation, 3),
            "start_date": self.start_date,
            "description": self.description,
        }


@dataclass
class DiversificationScore:
    """Live diversification assessment."""
    score: float             # 0-100 (higher = more diversified)
    grade: str               # A, B, C, D, F
    effective_positions: float  # effective number of uncorrelated bets
    concentration_risk: float
    correlation_risk: float
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "grade": self.grade,
            "effective_positions": round(self.effective_positions, 1),
            "concentration_risk": round(self.concentration_risk, 3),
            "correlation_risk": round(self.correlation_risk, 3),
            "recommendations": self.recommendations,
        }


class CorrelationMonitor:
    """
    Advanced correlation monitoring system.
    Tracks rolling correlations, detects regime changes,
    and provides live diversification scoring.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "correlation_monitor.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

        # Correlation regime thresholds
        self.regime_thresholds = {
            "low": 0.30,
            "normal": 0.50,
            "elevated": 0.70,
            "crisis": 1.0,
        }
        logger.info("CorrelationMonitor initialized")

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS correlation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                avg_correlation REAL,
                max_correlation REAL,
                min_correlation REAL,
                diversification_score REAL,
                effective_positions REAL,
                regime TEXT,
                matrix_json TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS correlation_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                pair TEXT,
                old_value REAL,
                new_value REAL,
                message TEXT
            )
        """)
        conn.commit()
        conn.close()

    # ---------------------------------------------------------- public API

    def compute_correlation_matrix(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute the full correlation matrix for current positions.
        Uses pre-computed correlations from risk_service with enhancements.
        """
        from services.risk_service import get_correlation_manager

        corr_mgr = get_correlation_manager()
        symbols = [p.get("symbol", "") for p in positions if p.get("symbol")]
        symbols = list(set(symbols))  # deduplicate

        if len(symbols) < 2:
            return {
                "symbols": symbols,
                "matrix": [[1.0]] if symbols else [],
                "avg_correlation": 0.0,
                "pairs": [],
            }

        # Build NxN correlation matrix
        n = len(symbols)
        matrix = [[0.0] * n for _ in range(n)]
        pairs = []
        all_corrs = []

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    corr = corr_mgr.get_correlation(symbols[i], symbols[j])
                    matrix[i][j] = round(corr, 3)
                    if i < j:
                        pairs.append({
                            "symbol1": symbols[i],
                            "symbol2": symbols[j],
                            "correlation": round(corr, 3),
                        })
                        all_corrs.append(corr)

        avg_corr = sum(all_corrs) / len(all_corrs) if all_corrs else 0
        max_corr = max(all_corrs) if all_corrs else 0
        min_corr = min(all_corrs) if all_corrs else 0

        # Sort pairs by absolute correlation (highest first)
        pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)

        result = {
            "symbols": symbols,
            "matrix": matrix,
            "avg_correlation": round(avg_corr, 3),
            "max_correlation": round(max_corr, 3),
            "min_correlation": round(min_corr, 3),
            "pairs": pairs,
            "high_correlation_pairs": [p for p in pairs if abs(p["correlation"]) >= 0.7],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Persist snapshot
        self._persist_snapshot(avg_corr, max_corr, min_corr, symbols, matrix)

        return result

    def detect_regime(
        self, positions: List[Dict[str, Any]]
    ) -> CorrelationRegime:
        """Detect the current correlation regime."""
        from services.risk_service import get_correlation_manager

        corr_mgr = get_correlation_manager()
        avg_corr = corr_mgr.calculate_portfolio_correlation(
            [{"symbol": p.get("symbol", ""), "market_value": p.get("market_value", 0)}
             for p in positions]
        )

        regime = "low"
        description = "Low correlation environment - good diversification benefit"

        if avg_corr >= self.regime_thresholds["elevated"]:
            regime = "crisis"
            description = "Crisis-level correlations - diversification benefits collapsed, consider hedging"
        elif avg_corr >= self.regime_thresholds["normal"]:
            regime = "elevated"
            description = "Elevated correlations - diversification weakening, monitor closely"
        elif avg_corr >= self.regime_thresholds["low"]:
            regime = "normal"
            description = "Normal correlation environment - standard diversification benefit"

        return CorrelationRegime(
            regime=regime,
            avg_correlation=avg_corr,
            start_date=datetime.utcnow().isoformat(),
            description=description,
        )

    def compute_diversification_score(
        self, positions: List[Dict[str, Any]]
    ) -> DiversificationScore:
        """
        Compute a live diversification score (0-100).
        Combines concentration risk and correlation risk.
        """
        if not positions:
            return DiversificationScore(
                score=0, grade="F", effective_positions=0,
                concentration_risk=1.0, correlation_risk=0.0,
                recommendations=["No positions in portfolio"],
            )

        from services.risk_service import get_correlation_manager

        total_value = sum(p.get("market_value", 0) for p in positions)
        if total_value <= 0:
            return DiversificationScore(
                score=0, grade="F", effective_positions=0,
                concentration_risk=1.0, correlation_risk=0.0,
                recommendations=["Portfolio has zero value"],
            )

        # 1. Concentration risk (Herfindahl index)
        weights = [p.get("market_value", 0) / total_value for p in positions]
        hhi = sum(w ** 2 for w in weights)
        # Effective number of positions = 1/HHI
        effective_n = 1.0 / hhi if hhi > 0 else len(positions)

        # Normalize HHI to 0-1 (0 = perfect diversification, 1 = single position)
        concentration_risk = hhi

        # 2. Correlation risk
        corr_mgr = get_correlation_manager()
        pos_dicts = [
            {"symbol": p.get("symbol", ""), "market_value": p.get("market_value", 0)}
            for p in positions
        ]
        avg_corr = corr_mgr.calculate_portfolio_correlation(pos_dicts)
        correlation_risk = max(0, avg_corr)

        # 3. Combined score
        # Weight: 40% concentration, 60% correlation (correlation is harder to fix)
        raw_score = (1 - concentration_risk * 0.4 - correlation_risk * 0.6) * 100
        score = max(0, min(100, raw_score))

        # Grade
        if score >= 80:
            grade = "A"
        elif score >= 65:
            grade = "B"
        elif score >= 50:
            grade = "C"
        elif score >= 35:
            grade = "D"
        else:
            grade = "F"

        # Recommendations
        recommendations = []
        if concentration_risk > 0.3:
            recommendations.append("Portfolio is concentrated - consider adding more positions")
        if correlation_risk > 0.6:
            recommendations.append("High average correlation - add uncorrelated assets")
        if effective_n < 5:
            recommendations.append(f"Only {effective_n:.1f} effective positions - increase diversification")
        if len(positions) < 5:
            recommendations.append("Consider holding at least 5-10 positions for adequate diversification")

        # Sector diversity check
        from services.risk_service import get_sector_tracker
        tracker = get_sector_tracker()
        sectors = set()
        for p in positions:
            sectors.add(tracker.get_sector(p.get("symbol", "")).value)
        if len(sectors) < 3:
            recommendations.append(f"Only {len(sectors)} sector(s) represented - diversify across sectors")

        if not recommendations:
            recommendations.append("Portfolio diversification is adequate")

        return DiversificationScore(
            score=score,
            grade=grade,
            effective_positions=effective_n,
            concentration_risk=concentration_risk,
            correlation_risk=correlation_risk,
            recommendations=recommendations,
        )

    def get_correlation_history(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Return historical correlation snapshots for trend analysis."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT timestamp, avg_correlation, max_correlation, min_correlation,
                   diversification_score, effective_positions, regime
            FROM correlation_snapshots
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()

        return [
            {
                "timestamp": r[0],
                "avg_correlation": round(r[1] or 0, 3),
                "max_correlation": round(r[2] or 0, 3),
                "min_correlation": round(r[3] or 0, 3),
                "diversification_score": round(r[4] or 0, 1),
                "effective_positions": round(r[5] or 0, 1),
                "regime": r[6] or "unknown",
            }
            for r in reversed(rows)
        ]

    def check_alerts(
        self, positions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for correlation-related alerts (spikes, regime changes)."""
        alerts = []

        # Get current state
        regime = self.detect_regime(positions)
        div_score = self.compute_diversification_score(positions)

        if regime.regime == "crisis":
            alerts.append({
                "type": "correlation_crisis",
                "severity": "critical",
                "message": f"Correlation regime is CRISIS (avg={regime.avg_correlation:.2f}). Diversification benefit collapsed.",
                "timestamp": datetime.utcnow().isoformat(),
            })
        elif regime.regime == "elevated":
            alerts.append({
                "type": "correlation_elevated",
                "severity": "warning",
                "message": f"Elevated correlations detected (avg={regime.avg_correlation:.2f}). Monitor for further deterioration.",
                "timestamp": datetime.utcnow().isoformat(),
            })

        if div_score.score < 35:
            alerts.append({
                "type": "low_diversification",
                "severity": "warning",
                "message": f"Diversification score is LOW ({div_score.score:.0f}/100, grade {div_score.grade}). {'; '.join(div_score.recommendations[:2])}",
                "timestamp": datetime.utcnow().isoformat(),
            })

        return alerts

    # -------------------------------------------------------- internal

    def _persist_snapshot(
        self, avg_corr: float, max_corr: float, min_corr: float,
        symbols: List[str], matrix: List[List[float]]
    ):
        # Compute diversification score components
        n = len(symbols)
        effective_n = n  # simplified
        if n > 0 and avg_corr < 1:
            effective_n = n / (1 + (n - 1) * max(0, avg_corr))

        regime = "low"
        if avg_corr >= 0.7:
            regime = "crisis"
        elif avg_corr >= 0.5:
            regime = "elevated"
        elif avg_corr >= 0.3:
            regime = "normal"

        div_score = max(0, (1 - avg_corr) * 100)

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO correlation_snapshots
            (timestamp, avg_correlation, max_correlation, min_correlation,
             diversification_score, effective_positions, regime, matrix_json)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            datetime.utcnow().isoformat(),
            avg_corr, max_corr, min_corr,
            div_score, effective_n, regime,
            json.dumps({"symbols": symbols, "matrix": matrix}),
        ))
        conn.commit()
        conn.close()


# --------------------------------------------------------------------- singleton
_instance: Optional[CorrelationMonitor] = None


def get_correlation_monitor() -> CorrelationMonitor:
    global _instance
    if _instance is None:
        _instance = CorrelationMonitor()
    return _instance
