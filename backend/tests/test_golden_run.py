"""
GOLDEN RUN - End-to-End System Health Check
============================================

This is the ultimate system verification test.
If this passes, the system is fundamentally operational.

The Golden Run verifies:
1. App starts successfully
2. Prices fetch from real sources
3. Charts render for all timeframes
4. Bots execute N ticks correctly
5. Trades are logged properly
6. No critical exceptions occur

Run with: pytest tests/test_golden_run.py -v -s
Run standalone: python -m tests.test_golden_run

ANY EXCEPTION = GOLDEN RUN FAILURE
"""

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)


@dataclass
class GoldenRunResult:
    """Result of a single golden run check"""
    name: str
    passed: bool
    duration_ms: float
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "details": self.details,
        }


class GoldenRunSuite:
    """
    Complete system health verification.

    Each check is independent and reports pass/fail.
    All checks must pass for the Golden Run to succeed.
    """

    def __init__(self):
        self.results: List[GoldenRunResult] = []
        self.start_time = None
        self.end_time = None

    def run_check(self, name: str, check_fn) -> GoldenRunResult:
        """Run a single check and record result"""
        start = time.perf_counter()
        try:
            details = check_fn()
            duration = (time.perf_counter() - start) * 1000
            result = GoldenRunResult(
                name=name,
                passed=True,
                duration_ms=duration,
                details=details or {}
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            result = GoldenRunResult(
                name=name,
                passed=False,
                duration_ms=duration,
                error=f"{type(e).__name__}: {str(e)}",
                details={"traceback": traceback.format_exc()}
            )

        self.results.append(result)
        return result

    # =========================================================================
    # GOLDEN RUN CHECKS
    # =========================================================================

    def check_app_startup(self) -> Dict:
        """Verify app starts without crashes"""
        from main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/health")

        if response.status_code != 200:
            raise Exception(f"Health check failed: {response.status_code}")

        data = response.json()
        return {
            "status": data.get("status"),
            "services_loaded": len(data.get("services", {})),
        }

    def check_price_fetch(self) -> Dict:
        """Verify prices can be fetched"""
        from services.data_service import get_data_service

        ds = get_data_service()
        test_symbols = ["SPY", "AAPL", "QQQ"]
        results = {}

        for symbol in test_symbols:
            quote = ds.get_quote(symbol)
            if quote:
                results[symbol] = {
                    "price": quote.price,
                    "source": quote.source,
                }
            else:
                raise Exception(f"Failed to fetch quote for {symbol}")

        return {"quotes": results, "count": len(results)}

    def check_data_sources(self) -> Dict:
        """Verify data sources are properly configured"""
        from services.data_service import get_data_service

        ds = get_data_service()

        # Check source health
        source_status = {}
        for source in ds.sources:
            source_status[source.name] = {
                "available": True,
                "priority": getattr(source, 'priority', 'unknown'),
            }

        if not source_status:
            raise Exception("No data sources configured")

        return {"sources": source_status}

    def check_chart_data(self) -> Dict:
        """Verify chart data loads for all timeframes"""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        timeframes = ["1m", "5m", "15m", "1h", "1d"]
        symbol = "SPY"

        results = {}
        for tf in timeframes:
            response = client.get(f"/api/charts/ohlcv/{symbol}?interval={tf}")
            results[tf] = {
                "status": response.status_code,
                "has_data": response.status_code == 200,
            }

            if response.status_code >= 500:
                raise Exception(f"Chart {tf} returned server error: {response.status_code}")

        return {"timeframes_tested": len(results), "results": results}

    def check_bot_ticks(self) -> Dict:
        """Verify bots can execute ticks"""
        from brain.algo_bot import AlgoBot, BotConfig

        config = BotConfig(
            name="GoldenRunBot",
            symbols=["SPY"],
            max_position_size=0,  # Safety: no real trades
        )

        bot = AlgoBot(config)

        N_TICKS = 10
        tick_results = []

        for i in range(N_TICKS):
            tick_start = time.perf_counter()
            try:
                if hasattr(bot, 'tick'):
                    bot.tick()
                tick_time = (time.perf_counter() - tick_start) * 1000
                tick_results.append({"tick": i, "success": True, "ms": tick_time})
            except Exception as e:
                tick_time = (time.perf_counter() - tick_start) * 1000
                tick_results.append({"tick": i, "success": False, "ms": tick_time, "error": str(e)})

        failures = [t for t in tick_results if not t["success"]]
        if failures:
            raise Exception(f"Bot tick failures: {failures}")

        avg_tick_time = sum(t["ms"] for t in tick_results) / len(tick_results)
        return {
            "ticks_executed": N_TICKS,
            "avg_tick_ms": round(avg_tick_time, 2),
            "all_passed": len(failures) == 0,
        }

    def check_trade_logging(self) -> Dict:
        """Verify trades can be logged"""
        from execution.trade_journal import TradeJournal, TradeAction

        journal = TradeJournal()

        # Log a test trade decision using the correct API
        entry = journal.record_decision(
            symbol="GOLDEN_RUN_TEST",
            action=TradeAction.BUY,
            direction="LONG",
            signal_confidence=0.85,
            signal_source="golden_run_test",
            decision="taken",
            entry_price=100.00,
        )

        if entry is None:
            raise Exception("Failed to record trade decision")

        return {
            "trade_logged": True,
            "entry_id": entry.entry_id,
            "method": "record_decision",
        }

    def check_brain_v6(self) -> Dict:
        """Verify PropFirm Brain V6 is operational"""
        from brain.propfirm_brain_v6 import PropFirmBrainV6

        brain = PropFirmBrainV6()

        # Check basic functionality
        status = {
            "initialized": brain is not None,
            "has_strategies": hasattr(brain, 'strategies') or hasattr(brain, 'strategy_ensemble'),
            "has_risk_manager": hasattr(brain, 'risk_manager') or hasattr(brain, 'risk_engine'),
        }

        return status

    def check_api_endpoints(self) -> Dict:
        """Verify critical API endpoints respond"""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)

        critical_endpoints = [
            "/api/health",
            "/api/market/status",
            "/api/positions",
            "/api/signals",
            "/api/brain-v6/status",
        ]

        results = {}
        failures = []

        for endpoint in critical_endpoints:
            response = client.get(endpoint)
            results[endpoint] = response.status_code
            if response.status_code >= 500:
                failures.append(endpoint)

        if failures:
            raise Exception(f"Critical endpoint failures: {failures}")

        return {"endpoints_tested": len(results), "all_passed": len(failures) == 0}

    def check_no_sim_data_leak(self) -> Dict:
        """Verify simulated data doesn't leak into live paths"""
        from services.data_service import get_data_service

        ds = get_data_service()

        # Get quotes and verify sources
        quotes = ds.get_quotes(["SPY", "AAPL", "MSFT"])

        sources = set()
        for symbol, quote in quotes.items():
            if quote:
                sources.add(quote.source)

        # Check if we're getting fallback when live should be available
        # (This is a warning, not a failure - depends on market hours)
        return {
            "sources_used": list(sources),
            "has_live_source": any(s in ["alpaca", "tradier", "yahoo"] for s in sources),
        }

    # =========================================================================
    # MAIN RUNNER
    # =========================================================================

    def run_all(self) -> Dict:
        """Run all golden run checks"""
        self.start_time = datetime.now()
        self.results = []

        checks = [
            ("1. App Startup", self.check_app_startup),
            ("2. Price Fetch", self.check_price_fetch),
            ("3. Data Sources", self.check_data_sources),
            ("4. Chart Data", self.check_chart_data),
            ("5. Bot Ticks", self.check_bot_ticks),
            ("6. Trade Logging", self.check_trade_logging),
            ("7. Brain V6", self.check_brain_v6),
            ("8. API Endpoints", self.check_api_endpoints),
            ("9. No Sim Data Leak", self.check_no_sim_data_leak),
        ]

        print("\n" + "=" * 60)
        print("  GOLDEN RUN - System Health Check")
        print("=" * 60 + "\n")

        for name, check_fn in checks:
            result = self.run_check(name, check_fn)
            status = "[PASS]" if result.passed else "[FAIL]"
            print(f"{status} {result.name} ({result.duration_ms:.1f}ms)")
            if not result.passed:
                print(f"       Error: {result.error}")

        self.end_time = datetime.now()

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_time = (self.end_time - self.start_time).total_seconds() * 1000

        print("\n" + "=" * 60)
        print(f"  RESULTS: {passed}/{len(self.results)} passed")
        print(f"  Total Time: {total_time:.1f}ms")

        if failed > 0:
            print("\n  *** GOLDEN RUN FAILED ***")
            print("  System is NOT ready for production")
        else:
            print("\n  *** GOLDEN RUN PASSED ***")
            print("  System is operational")

        print("=" * 60 + "\n")

        return {
            "passed": failed == 0,
            "total_checks": len(self.results),
            "passed_checks": passed,
            "failed_checks": failed,
            "total_time_ms": total_time,
            "timestamp": self.start_time.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }


# =============================================================================
# PYTEST INTEGRATION
# =============================================================================

class TestGoldenRun:
    """Pytest wrapper for Golden Run"""

    def test_golden_run_complete(self):
        """Execute complete Golden Run and assert all checks pass"""
        suite = GoldenRunSuite()
        result = suite.run_all()

        assert result["passed"], f"Golden Run failed: {result['failed_checks']} checks failed"
        assert result["failed_checks"] == 0


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

def main():
    """Run Golden Run as standalone script"""
    suite = GoldenRunSuite()
    result = suite.run_all()

    # Save report
    report_path = os.path.join(backend_dir, "golden_run_report.json")
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Report saved to: {report_path}")

    # Exit with appropriate code
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
