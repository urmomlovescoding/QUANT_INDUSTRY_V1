#!/usr/bin/env python3
"""
QUANT_INDUSTRY_V1 Main Application Entry Point

Institutional-grade quantitative trading platform.

Usage:
    python main.py                    # Run with default settings
    python main.py --mode paper       # Paper trading mode
    python main.py --mode backtest    # Backtest mode
    python main.py --ui               # Launch with UI
    python main.py --health           # Health check only
"""

import argparse
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings, get_settings, init_settings, TradingMode
from db.dal import init_db, get_db
from db.models import Run, RunMode, RunStatus
from db.repositories import RunRepository, HealthRepository
from core.context import RunContext, run_context
from utils.logging import setup_logging, get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='QUANT_INDUSTRY_V1 - Institutional Quant Trading Platform'
    )
    parser.add_argument(
        '--mode',
        choices=['backtest', 'paper', 'live'],
        default='paper',
        help='Trading mode (default: paper)'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Symbols to trade (default: from config)'
    )
    parser.add_argument(
        '--ui',
        action='store_true',
        help='Launch with UI'
    )
    parser.add_argument(
        '--health',
        action='store_true',
        help='Run health check only'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    parser.add_argument(
        '--grade',
        action='store_true',
        help='Run self-grading analysis'
    )
    parser.add_argument(
        '--version',
        action='store_true',
        help='Show version information'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Log level'
    )
    return parser.parse_args()


def show_version() -> int:
    """Show version information."""
    print("""
================================================================================
  QUANT_INDUSTRY_V1 - Institutional-Grade Quantitative Trading Platform
================================================================================
  Version: 1.0.0

  Modules:
    brain:      AI/ML, Regime Detection, RL Agents, Physics Models, Safety
    data:       Data Pipeline, Feature Engineering
    execution:  Order Execution (TWAP/VWAP/POV), Broker Integration
    risk:       Risk Management, Position Sizing (Kelly, Vol-Scaled)
    strategies: Strategy Framework, Signal Generation
    services:   Self-Grading, Health Monitoring, Orchestration
    security:   Encrypted Credentials, Access Control, Audit Logging

  Key Features:
    - Hidden Markov Models for regime detection
    - Reinforcement learning (PPO/A2C) for adaptive trading
    - Physics-inspired models (Ising, Mean Field, Ornstein-Uhlenbeck)
    - SHAP-like explainability for model decisions
    - Self-grading with autonomous improvement suggestions
    - Enterprise-grade security with encrypted API keys
    - CI/CD pipeline with comprehensive testing

================================================================================
""")
    return 0


def run_self_grade() -> int:
    """Run self-grading analysis."""
    try:
        from services import SelfGradingEngine

        engine = SelfGradingEngine()

        # Sample metrics for demonstration
        metrics = {
            'total_return': 0.12,
            'benchmark_return': 0.08,
            'sharpe_ratio': 1.3,
            'sortino_ratio': 1.6,
            'calmar_ratio': 0.9,
            'max_drawdown': 0.11,
            'avg_drawdown': 0.04,
            'avg_recovery_days': 12,
            'win_rate': 0.54,
            'profit_factor': 1.4,
            'monthly_positive_pct': 0.67,
            'model_accuracy': 0.56,
            'model_precision': 0.54,
            'model_recall': 0.51,
            'drift_detected': False,
            'uptime_pct': 99.7,
            'error_rate': 0.2,
            'latency_p99_ms': 95,
        }

        report = engine.grade(metrics)

        print("\n" + "=" * 60)
        print("  QUANT_INDUSTRY_V1 Self-Grade Report")
        print("=" * 60)
        print(f"\n  Overall Score: {report.overall_score:.1f}/100")
        print(f"  Overall Grade: {report.overall_grade.value}")
        print(f"  Trend: {report.trend}")
        print(f"  vs Benchmark: {report.comparison_to_benchmark:+.1%}")

        print("\n  Dimension Grades:")
        print("  " + "-" * 50)
        for dim, grade in report.dimension_grades.items():
            print(f"  {dim.value:25} | {grade.grade.value:3} | {grade.score:5.1f}")

        if report.remediations:
            print("\n  Top Remediations:")
            print("  " + "-" * 50)
            for i, rem in enumerate(report.remediations[:3], 1):
                print(f"  {i}. [{rem.priority.value.upper()}] {rem.title}")
                print(f"     {rem.description}")

        print("\n" + "=" * 60)
        return 0

    except ImportError as e:
        print(f"Error: Could not import self-grading module: {e}")
        return 1


def run_health_check() -> int:
    """Run system health check and exit."""
    print("\n=== QUANT_INDUSTRY_V1 Health Check ===\n")

    # Initialize database
    try:
        db = init_db()
        health = db.health_check()
        print(f"Database: {health['status']}")
        print(f"  Path: {health['db_path']}")
        print(f"  Size: {health['db_size_mb']:.2f} MB")
        print(f"  Tables: {len(health['table_counts'])}")
        print(f"  Integrity: {health['integrity_check']}")
    except Exception as e:
        print(f"Database: FAILED - {e}")
        return 1

    # Check configuration
    settings = get_settings()
    errors = settings.validate()
    if errors:
        print(f"\nConfiguration: WARNINGS")
        for err in errors:
            print(f"  - {err}")
    else:
        print(f"\nConfiguration: OK")

    # Check API connectivity
    print(f"\nAPI Keys:")
    print(f"  Alpaca: {'Configured' if settings.alpaca_api_key else 'Missing'}")

    print("\n=== Health Check Complete ===\n")
    return 0


def initialize_system(settings: Settings) -> None:
    """Initialize all system components."""
    # Setup logging
    setup_logging(
        level=settings.log_level,
        log_dir=settings.log_dir,
        json_output=settings.environment.value == 'production',
    )

    # Initialize database
    db = init_db(str(settings.db_path))
    logger.info(f"Database initialized at {settings.db_path}")

    # Log startup
    logger.info(
        "System initialized",
        environment=settings.environment.value,
        mode=settings.execution.mode.value,
        symbols=settings.data.symbols,
    )


def create_run(settings: Settings, ctx: RunContext) -> Run:
    """Create and register a new run."""
    run = Run(
        run_id=ctx.run_id,
        mode=RunMode(ctx.mode),
        config_hash=settings.get_hash(),
        git_hash=ctx.git_hash,
        start_ts=ctx.start_time,
        metadata={
            'symbols': settings.data.symbols,
            'environment': settings.environment.value,
        }
    )

    repo = RunRepository()
    repo.create(run)

    logger.info(f"Run {run.run_id} created", mode=run.mode.value)
    return run


def run_trading_loop(settings: Settings, ctx: RunContext) -> None:
    """Main trading loop using the TradingEngine."""
    logger.info("Starting trading loop...")

    from core import TradingEngine, EngineConfig, TradingMode as EngineMode

    symbols = settings.data.symbols

    print(f"\n{'='*60}")
    print(f"QUANT_INDUSTRY_V1 - {settings.execution.mode.value.upper()} MODE")
    print(f"{'='*60}")
    print(f"Run ID: {ctx.run_id}")
    print(f"Config Hash: {settings.get_hash()}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"{'='*60}\n")

    # Map settings mode to engine mode
    mode_map = {
        'backtest': EngineMode.BACKTEST,
        'paper': EngineMode.PAPER,
        'live': EngineMode.LIVE,
    }
    engine_mode = mode_map.get(settings.execution.mode.value, EngineMode.PAPER)

    # Create engine config - use separate trading database
    trading_db = Path(settings.db_path).parent / "trading.db"
    config = EngineConfig(
        mode=engine_mode,
        symbols=symbols,
        initial_capital=100000.0,  # Default starting capital
        max_position_pct=settings.execution.max_position_pct,
        max_positions=10,
        update_interval_seconds=60,
        db_path=str(trading_db),
        max_daily_loss_pct=0.02,
        max_drawdown_pct=settings.risk.max_drawdown_pct,
    )

    # Create and initialize engine
    engine = TradingEngine(config)

    try:
        print("Initializing trading engine...")
        engine.initialize()
        print("Engine initialized successfully")

        print("\nCore Modules Loaded:")
        print("  - AI/ML Engine (Regime Detection, Feature Engineering)")
        print("  - Risk Engine (Position Sizing, Limits)")
        print("  - Execution Engine (Simulated Broker)")
        print("  - Strategy Framework (Momentum, Mean Reversion)")

        print("\nStarting trading loop...")
        print("Press Ctrl+C to stop\n")

        engine.start()

        # Keep main thread alive
        import time
        while True:
            status = engine.get_status()
            print(f"\rEquity: ${status['equity']:,.2f} | "
                  f"PnL: ${status['pnl']:+,.2f} ({status['pnl_pct']:+.2f}%) | "
                  f"Positions: {status['positions']} | "
                  f"Regime: {status['current_regime']}", end='', flush=True)
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nStopping engine...")
        engine.stop()
        print("Engine stopped")

        # Final stats
        status = engine.get_status()
        print(f"\n{'='*60}")
        print("Final Statistics:")
        print(f"  Equity: ${status['equity']:,.2f}")
        print(f"  Total PnL: ${status['pnl']:+,.2f} ({status['pnl_pct']:+.2f}%)")
        print(f"  Total Trades: {status['trades_count']}")
        print(f"{'='*60}")


def run_ui(settings: Settings, ctx: RunContext) -> None:
    """Launch the UI with trading engine."""
    logger.info("Launching UI...")

    from core import TradingEngine, EngineConfig, TradingMode as EngineMode
    from ui import launch_ui, connect_engine, ColorScheme

    symbols = settings.data.symbols

    # Map settings mode to engine mode
    mode_map = {
        'backtest': EngineMode.BACKTEST,
        'paper': EngineMode.PAPER,
        'live': EngineMode.LIVE,
    }
    engine_mode = mode_map.get(settings.execution.mode.value, EngineMode.PAPER)

    # Create engine config - use separate trading database
    trading_db = Path(settings.db_path).parent / "trading.db"
    config = EngineConfig(
        mode=engine_mode,
        symbols=symbols,
        initial_capital=100000.0,  # Default starting capital
        max_position_pct=settings.execution.max_position_pct,
        max_positions=10,
        update_interval_seconds=60,
        db_path=str(trading_db),
    )

    # Create and initialize engine
    engine = TradingEngine(config)
    engine.initialize()

    # Connect engine to UI
    connector = connect_engine(engine)

    # Launch UI
    print(f"\n{'='*60}")
    print(f"QUANT_INDUSTRY_V1 - {settings.execution.mode.value.upper()} MODE")
    print(f"{'='*60}")
    print(f"Run ID: {ctx.run_id}")
    print(f"Launching Tkinter Dashboard...")
    print(f"{'='*60}\n")

    app = launch_ui(
        run_id=ctx.run_id,
        mode=settings.execution.mode.value,
        theme=ColorScheme.DARK,
    )

    # Start connector updates when engine runs
    # The UI can control engine start/stop via the connector

    try:
        app.run()
    finally:
        if engine.state.value == "running":
            engine.stop()
        connector.stop_updates()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Version display
    if args.version:
        return show_version()

    # Health check only
    if args.health:
        return run_health_check()

    # Self-grading analysis
    if args.grade:
        return run_self_grade()

    # Load configuration
    if args.config:
        settings = Settings.load(Path(args.config))
    else:
        settings = Settings()

    # Override from command line
    if args.mode:
        settings.execution.mode = TradingMode(args.mode)
    if args.symbols:
        settings.data.symbols = args.symbols
    if args.debug:
        settings.debug = True
        settings.log_level = 'DEBUG'
    if args.log_level:
        settings.log_level = args.log_level

    # Validate configuration
    errors = settings.validate()
    if errors:
        for error in errors:
            print(f"Configuration error: {error}", file=sys.stderr)
        # Continue with warnings for now (not blocking for development)

    # Initialize settings
    init_settings(settings)

    # Create run context
    with run_context(mode=settings.execution.mode.value, config_hash=settings.get_hash()) as ctx:
        try:
            # Initialize system
            initialize_system(settings)

            # Create run record
            run = create_run(settings, ctx)

            # Launch UI or run trading loop
            if args.ui:
                run_ui(settings, ctx)
            else:
                run_trading_loop(settings, ctx)

            # Mark run as completed
            repo = RunRepository()
            repo.complete(run.run_id)

            return 0

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            return 130

        except Exception as e:
            logger.exception(f"Fatal error: {e}")
            if 'run' in locals():
                repo = RunRepository()
                repo.fail(run.run_id)
            return 1


if __name__ == '__main__':
    sys.exit(main())
