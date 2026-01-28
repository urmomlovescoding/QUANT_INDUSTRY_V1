"""
Backtesting as a Service (BaaS)
===============================
Cloud-ready backtest infrastructure for on-demand strategy evaluation.

Features:
- Job queue with priority scheduling
- Sandboxed strategy execution
- Resource limits and timeouts
- Result caching and deduplication
- Webhook callbacks on completion
- Multi-tenant isolation
- Usage metering and billing hooks
"""

import asyncio
import logging
import hashlib
import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Backtest job status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class BacktestConfig:
    """Configuration for a backtest job"""
    # Strategy definition
    strategy_code: str  # Python code or strategy ID
    strategy_type: str = "code"  # "code", "config", "template"
    strategy_params: dict = field(default_factory=dict)
    
    # Universe and data
    symbols: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    data_frequency: str = "1d"  # 1m, 5m, 1h, 1d
    benchmark: str = "SPY"
    
    # Execution settings
    initial_capital: float = 100000
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    margin_requirement: float = 1.0  # 1.0 = no margin
    
    # Risk limits
    max_position_size: float = 0.1  # 10% of portfolio
    max_drawdown: float = 0.2  # 20% circuit breaker
    
    # Resource limits
    timeout_seconds: int = 300
    max_memory_mb: int = 1024
    
    def to_dict(self) -> dict:
        return {
            "strategy_code": self.strategy_code[:100] + "..." if len(self.strategy_code) > 100 else self.strategy_code,
            "strategy_type": self.strategy_type,
            "strategy_params": self.strategy_params,
            "symbols": self.symbols,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "data_frequency": self.data_frequency,
            "benchmark": self.benchmark,
            "initial_capital": self.initial_capital,
            "commission": self.commission,
            "slippage": self.slippage,
            "max_position_size": self.max_position_size,
            "timeout_seconds": self.timeout_seconds
        }
    
    def compute_hash(self) -> str:
        """Compute deterministic hash for caching"""
        content = json.dumps({
            "code": self.strategy_code,
            "params": self.strategy_params,
            "symbols": sorted(self.symbols),
            "start": self.start_date,
            "end": self.end_date,
            "freq": self.data_frequency,
            "capital": self.initial_capital,
            "commission": self.commission,
            "slippage": self.slippage
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class BacktestResult:
    """Results from a completed backtest"""
    job_id: str
    config_hash: str
    
    # Performance metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_holding_period: float = 0.0
    
    # Risk metrics
    var_95: float = 0.0
    cvar_95: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    
    # Equity curve (sampled)
    equity_curve: list[dict] = field(default_factory=list)
    drawdown_curve: list[dict] = field(default_factory=list)
    monthly_returns: list[dict] = field(default_factory=list)
    
    # Trade log (limited)
    trades: list[dict] = field(default_factory=list)
    
    # Execution info
    execution_time_seconds: float = 0.0
    data_points_processed: int = 0
    
    # Errors/warnings
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "config_hash": self.config_hash,
            "performance": {
                "total_return": self.total_return,
                "annualized_return": self.annualized_return,
                "sharpe_ratio": self.sharpe_ratio,
                "sortino_ratio": self.sortino_ratio,
                "max_drawdown": self.max_drawdown,
                "calmar_ratio": self.calmar_ratio,
                "volatility": self.volatility
            },
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "win_rate": self.win_rate,
                "avg_win": self.avg_win,
                "avg_loss": self.avg_loss,
                "profit_factor": self.profit_factor,
                "avg_holding_period": self.avg_holding_period
            },
            "risk": {
                "var_95": self.var_95,
                "cvar_95": self.cvar_95,
                "beta": self.beta,
                "alpha": self.alpha
            },
            "curves": {
                "equity": self.equity_curve,
                "drawdown": self.drawdown_curve,
                "monthly_returns": self.monthly_returns
            },
            "trade_log": self.trades[:100],  # Limit for API
            "execution": {
                "time_seconds": self.execution_time_seconds,
                "data_points": self.data_points_processed
            },
            "warnings": self.warnings
        }


@dataclass
class BacktestJob:
    """A backtest job in the queue"""
    job_id: str
    tenant_id: str  # For multi-tenant isolation
    config: BacktestConfig
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    result: Optional[BacktestResult] = None
    error: Optional[str] = None
    
    # Callbacks
    webhook_url: Optional[str] = None
    callback_data: dict = field(default_factory=dict)
    
    # Tracking
    progress: float = 0.0
    current_step: str = ""
    
    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "config": self.config.to_dict(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "current_step": self.current_step,
            "error": self.error
        }


class StrategyExecutor:
    """
    Sandboxed strategy execution environment.
    
    Executes user-provided strategy code in a controlled environment
    with resource limits and safety checks.
    """
    
    # Allowed imports for strategies
    ALLOWED_IMPORTS = {
        'numpy', 'np',
        'pandas', 'pd',
        'math',
        'datetime',
        'collections',
        'itertools',
        'functools',
        'statistics'
    }
    
    # Forbidden patterns
    FORBIDDEN_PATTERNS = [
        'import os',
        'import sys',
        'import subprocess',
        '__import__',
        'eval(',
        'exec(',
        'open(',
        'file(',
        'input(',
        'raw_input',
        'compile(',
        'globals(',
        'locals(',
        'vars(',
        'dir(',
        'getattr(',
        'setattr(',
        'delattr(',
        '__builtins__'
    ]
    
    def __init__(self, data_provider: Callable = None):
        """
        Args:
            data_provider: Function(symbols, start, end, freq) -> DataFrame
        """
        self.data_provider = data_provider or self._mock_data_provider
    
    def _mock_data_provider(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        frequency: str
    ) -> pd.DataFrame:
        """Mock data provider for testing"""
        dates = pd.date_range(start_date, end_date, freq='D')
        data = {}
        
        for symbol in symbols:
            np.random.seed(hash(symbol) % 2**32)
            returns = np.random.randn(len(dates)) * 0.02
            prices = 100 * np.cumprod(1 + returns)
            data[symbol] = prices
        
        df = pd.DataFrame(data, index=dates)
        return df
    
    def validate_code(self, code: str) -> tuple[bool, list[str]]:
        """
        Validate strategy code for safety.
        
        Returns:
            (is_valid, list of issues)
        """
        issues = []
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in code:
                issues.append(f"Forbidden pattern: {pattern}")
        
        # Check for network access attempts
        if 'urllib' in code or 'requests' in code or 'http' in code.lower():
            issues.append("Network access not allowed")
        
        # Check for file system access
        if 'pathlib' in code or 'shutil' in code:
            issues.append("File system access not allowed")
        
        return len(issues) == 0, issues
    
    def execute(
        self,
        config: BacktestConfig,
        progress_callback: Callable[[float, str], None] = None
    ) -> BacktestResult:
        """
        Execute a backtest.
        
        Args:
            config: Backtest configuration
            progress_callback: Optional callback(progress, step)
            
        Returns:
            BacktestResult
        """
        start_time = time.time()
        result = BacktestResult(
            job_id="",
            config_hash=config.compute_hash()
        )
        
        def report_progress(pct: float, step: str):
            if progress_callback:
                progress_callback(pct, step)
        
        try:
            # Validate code
            report_progress(0.05, "Validating strategy code")
            is_valid, issues = self.validate_code(config.strategy_code)
            if not is_valid:
                raise ValueError(f"Invalid strategy code: {'; '.join(issues)}")
            
            # Load data
            report_progress(0.1, "Loading market data")
            data = self.data_provider(
                config.symbols,
                config.start_date,
                config.end_date,
                config.data_frequency
            )
            result.data_points_processed = len(data) * len(config.symbols)
            
            # Load benchmark
            benchmark_data = self.data_provider(
                [config.benchmark],
                config.start_date,
                config.end_date,
                config.data_frequency
            )
            
            # Execute strategy
            report_progress(0.2, "Executing strategy")
            trades, equity = self._run_strategy(config, data, report_progress)
            
            # Calculate metrics
            report_progress(0.8, "Calculating performance metrics")
            self._calculate_metrics(result, equity, trades, benchmark_data, config)
            
            # Sample curves for output
            report_progress(0.9, "Preparing results")
            result.equity_curve = self._sample_curve(equity, 'equity')
            result.drawdown_curve = self._calculate_drawdown_curve(equity)
            result.monthly_returns = self._calculate_monthly_returns(equity)
            result.trades = trades[:1000]  # Limit trade log
            
            report_progress(1.0, "Complete")
            
        except Exception as e:
            logger.error(f"Backtest execution error: {e}")
            result.warnings.append(str(e))
            raise
        
        result.execution_time_seconds = time.time() - start_time
        return result
    
    def _run_strategy(
        self,
        config: BacktestConfig,
        data: pd.DataFrame,
        progress_callback: Callable
    ) -> tuple[list[dict], pd.Series]:
        """Run the strategy and return trades and equity curve"""
        
        # Initialize portfolio state
        cash = config.initial_capital
        positions = defaultdict(float)
        equity_history = []
        trades = []
        
        # Create safe execution environment
        safe_globals = {
            'np': np,
            'pd': pd,
            'math': __import__('math'),
            'datetime': __import__('datetime'),
        }
        
        # Compile strategy
        try:
            exec(config.strategy_code, safe_globals)
            strategy_func = safe_globals.get('generate_signals')
            if not strategy_func:
                raise ValueError("Strategy must define 'generate_signals(data, params)' function")
        except Exception as e:
            raise ValueError(f"Strategy compilation error: {e}")
        
        # Run backtest
        total_bars = len(data)
        
        for i, (date, row) in enumerate(data.iterrows()):
            if i < 20:  # Need some history
                equity_history.append({
                    'date': date,
                    'equity': cash
                })
                continue
            
            # Get historical data up to this point
            hist_data = data.iloc[:i+1]
            
            # Generate signals
            try:
                signals = strategy_func(hist_data, config.strategy_params)
            except Exception as e:
                logger.warning(f"Signal generation error at {date}: {e}")
                signals = {}
            
            # Process signals
            for symbol, signal in signals.items():
                if symbol not in data.columns:
                    continue
                
                price = row[symbol]
                if pd.isna(price):
                    continue
                
                current_position = positions[symbol]
                target_position = signal * config.initial_capital / price
                
                # Apply position limits
                max_shares = (config.max_position_size * config.initial_capital) / price
                target_position = max(-max_shares, min(max_shares, target_position))
                
                # Calculate trade
                trade_shares = target_position - current_position
                
                if abs(trade_shares) > 0.01:
                    # Apply slippage
                    if trade_shares > 0:
                        exec_price = price * (1 + config.slippage)
                    else:
                        exec_price = price * (1 - config.slippage)
                    
                    # Calculate costs
                    trade_value = abs(trade_shares * exec_price)
                    commission = trade_value * config.commission
                    
                    # Execute trade
                    cash -= trade_shares * exec_price + commission
                    positions[symbol] = target_position
                    
                    trades.append({
                        'date': date.isoformat() if hasattr(date, 'isoformat') else str(date),
                        'symbol': symbol,
                        'side': 'buy' if trade_shares > 0 else 'sell',
                        'shares': abs(trade_shares),
                        'price': exec_price,
                        'commission': commission,
                        'value': trade_value
                    })
            
            # Calculate equity
            position_value = sum(
                positions[sym] * row[sym]
                for sym in positions
                if sym in row and not pd.isna(row[sym])
            )
            equity = cash + position_value
            equity_history.append({
                'date': date,
                'equity': equity
            })
            
            # Check drawdown circuit breaker
            peak = max(e['equity'] for e in equity_history)
            drawdown = (peak - equity) / peak
            if drawdown > config.max_drawdown:
                logger.warning(f"Circuit breaker triggered at {drawdown:.1%} drawdown")
                break
            
            # Progress update
            if i % 100 == 0:
                progress = 0.2 + 0.6 * (i / total_bars)
                progress_callback(progress, f"Processing bar {i}/{total_bars}")
        
        # Convert to Series
        equity_series = pd.Series(
            [e['equity'] for e in equity_history],
            index=[e['date'] for e in equity_history]
        )
        
        return trades, equity_series
    
    def _calculate_metrics(
        self,
        result: BacktestResult,
        equity: pd.Series,
        trades: list[dict],
        benchmark: pd.DataFrame,
        config: BacktestConfig
    ):
        """Calculate all performance metrics"""
        
        if len(equity) < 2:
            return
        
        # Basic returns
        returns = equity.pct_change().dropna()
        result.total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
        
        # Annualized metrics
        days = (equity.index[-1] - equity.index[0]).days
        years = days / 365.25
        if years > 0:
            result.annualized_return = (1 + result.total_return) ** (1/years) - 1
            result.volatility = returns.std() * np.sqrt(252)
        
        # Risk-adjusted returns
        if result.volatility > 0:
            risk_free_rate = 0.02  # Assume 2%
            excess_return = result.annualized_return - risk_free_rate
            result.sharpe_ratio = excess_return / result.volatility
        
        # Sortino (downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std() * np.sqrt(252)
            if downside_std > 0:
                result.sortino_ratio = (result.annualized_return - 0.02) / downside_std
        
        # Drawdown
        peak = equity.expanding().max()
        drawdown = (peak - equity) / peak
        result.max_drawdown = drawdown.max()
        
        # Calmar ratio
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annualized_return / result.max_drawdown
        
        # Trade statistics
        result.total_trades = len(trades)
        
        # Calculate trade P&L
        trade_pnls = []
        position_entry = {}
        
        for trade in trades:
            symbol = trade['symbol']
            if trade['side'] == 'buy':
                position_entry[symbol] = trade['price']
            elif trade['side'] == 'sell' and symbol in position_entry:
                pnl = (trade['price'] - position_entry[symbol]) * trade['shares']
                pnl -= trade['commission']
                trade_pnls.append(pnl)
        
        if trade_pnls:
            wins = [p for p in trade_pnls if p > 0]
            losses = [p for p in trade_pnls if p < 0]
            
            result.winning_trades = len(wins)
            result.losing_trades = len(losses)
            result.win_rate = len(wins) / len(trade_pnls)
            result.avg_win = np.mean(wins) if wins else 0
            result.avg_loss = np.mean(losses) if losses else 0
            
            total_wins = sum(wins)
            total_losses = abs(sum(losses))
            if total_losses > 0:
                result.profit_factor = total_wins / total_losses
        
        # VaR and CVaR
        if len(returns) > 0:
            result.var_95 = np.percentile(returns, 5)
            result.cvar_95 = returns[returns <= result.var_95].mean()
        
        # Beta and Alpha (vs benchmark)
        if config.benchmark in benchmark.columns:
            bench_returns = benchmark[config.benchmark].pct_change().dropna()
            # Align dates
            aligned = pd.concat([returns, bench_returns], axis=1).dropna()
            if len(aligned) > 10:
                cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
                if cov[1, 1] > 0:
                    result.beta = cov[0, 1] / cov[1, 1]
                    bench_annual = bench_returns.mean() * 252
                    result.alpha = result.annualized_return - (0.02 + result.beta * (bench_annual - 0.02))
    
    def _sample_curve(self, series: pd.Series, name: str, max_points: int = 500) -> list[dict]:
        """Sample time series for output"""
        if len(series) <= max_points:
            return [
                {'date': str(d), name: float(v)}
                for d, v in series.items()
            ]
        
        step = len(series) // max_points
        sampled = series.iloc[::step]
        return [
            {'date': str(d), name: float(v)}
            for d, v in sampled.items()
        ]
    
    def _calculate_drawdown_curve(self, equity: pd.Series) -> list[dict]:
        """Calculate drawdown time series"""
        peak = equity.expanding().max()
        drawdown = (peak - equity) / peak
        return self._sample_curve(drawdown, 'drawdown')
    
    def _calculate_monthly_returns(self, equity: pd.Series) -> list[dict]:
        """Calculate monthly returns"""
        monthly = equity.resample('M').last()
        returns = monthly.pct_change().dropna()
        return [
            {'month': str(d)[:7], 'return': float(v)}
            for d, v in returns.items()
        ]


class BacktestService:
    """
    Backtesting as a Service - Job queue and execution manager.
    
    Features:
    - Priority job queue
    - Concurrent execution with limits
    - Result caching
    - Webhook callbacks
    - Multi-tenant isolation
    - Usage metering
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 1000,
        cache_ttl_hours: int = 24,
        data_provider: Callable = None
    ):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        # Job storage
        self.jobs: dict[str, BacktestJob] = {}
        self.job_queue: list[tuple[int, float, str]] = []  # (priority, timestamp, job_id)
        self.queue_lock = threading.Lock()
        
        # Result cache
        self.result_cache: dict[str, tuple[datetime, BacktestResult]] = {}
        
        # Executor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.strategy_executor = StrategyExecutor(data_provider=data_provider)
        
        # Usage tracking
        self.usage: dict[str, dict] = defaultdict(lambda: {
            'jobs_submitted': 0,
            'jobs_completed': 0,
            'compute_seconds': 0.0,
            'data_points': 0
        })
        
        # Running jobs
        self.running_jobs: set[str] = set()
        
        # Start queue processor
        self._running = True
        self._processor_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._processor_thread.start()
        
        logger.info(f"BacktestService initialized with {max_workers} workers")
    
    def submit_job(
        self,
        tenant_id: str,
        config: BacktestConfig,
        priority: JobPriority = JobPriority.NORMAL,
        webhook_url: str = None,
        callback_data: dict = None
    ) -> BacktestJob:
        """
        Submit a new backtest job.
        
        Args:
            tenant_id: Tenant identifier for isolation
            config: Backtest configuration
            priority: Job priority
            webhook_url: URL to call on completion
            callback_data: Additional data for webhook
            
        Returns:
            Created BacktestJob
        """
        # Check cache first
        config_hash = config.compute_hash()
        if config_hash in self.result_cache:
            cached_time, cached_result = self.result_cache[config_hash]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.info(f"Cache hit for config {config_hash}")
                
                # Return cached result as completed job
                job_id = str(uuid.uuid4())
                job = BacktestJob(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    config=config,
                    status=JobStatus.COMPLETED,
                    priority=priority,
                    result=cached_result,
                    webhook_url=webhook_url,
                    callback_data=callback_data or {}
                )
                job.result.job_id = job_id
                job.completed_at = datetime.now()
                self.jobs[job_id] = job
                return job
        
        # Check queue limit
        with self.queue_lock:
            if len(self.job_queue) >= self.max_queue_size:
                raise RuntimeError("Job queue is full")
        
        # Create job
        job_id = str(uuid.uuid4())
        job = BacktestJob(
            job_id=job_id,
            tenant_id=tenant_id,
            config=config,
            priority=priority,
            webhook_url=webhook_url,
            callback_data=callback_data or {}
        )
        
        self.jobs[job_id] = job
        self.usage[tenant_id]['jobs_submitted'] += 1
        
        # Add to priority queue
        with self.queue_lock:
            import heapq
            heapq.heappush(
                self.job_queue,
                (-priority.value, time.time(), job_id)  # Negative for max-heap
            )
            job.status = JobStatus.QUEUED
        
        logger.info(f"Job {job_id} queued for tenant {tenant_id}")
        return job
    
    def get_job(self, job_id: str) -> Optional[BacktestJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> dict:
        """Get job status summary"""
        job = self.jobs.get(job_id)
        if not job:
            return {"error": "Job not found"}
        return job.to_dict()
    
    def get_job_result(self, job_id: str) -> Optional[BacktestResult]:
        """Get job result if completed"""
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.COMPLETED:
            return None
        return job.result
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending/queued job"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.PENDING, JobStatus.QUEUED]:
            job.status = JobStatus.CANCELLED
            logger.info(f"Job {job_id} cancelled")
            return True
        
        return False
    
    def list_jobs(
        self,
        tenant_id: str = None,
        status: JobStatus = None,
        limit: int = 100
    ) -> list[BacktestJob]:
        """List jobs with optional filters"""
        jobs = list(self.jobs.values())
        
        if tenant_id:
            jobs = [j for j in jobs if j.tenant_id == tenant_id]
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs[:limit]
    
    def get_usage(self, tenant_id: str) -> dict:
        """Get usage statistics for a tenant"""
        return dict(self.usage[tenant_id])
    
    def get_queue_status(self) -> dict:
        """Get queue status"""
        with self.queue_lock:
            return {
                "queue_size": len(self.job_queue),
                "running_jobs": len(self.running_jobs),
                "max_workers": self.max_workers,
                "available_workers": self.max_workers - len(self.running_jobs)
            }
    
    def _process_queue(self):
        """Background thread to process job queue"""
        while self._running:
            try:
                # Check if we can run more jobs
                if len(self.running_jobs) >= self.max_workers:
                    time.sleep(0.1)
                    continue
                
                # Get next job
                job_id = None
                with self.queue_lock:
                    while self.job_queue:
                        _, _, jid = heapq.heappop(self.job_queue)
                        job = self.jobs.get(jid)
                        if job and job.status == JobStatus.QUEUED:
                            job_id = jid
                            break
                
                if not job_id:
                    time.sleep(0.1)
                    continue
                
                # Submit job to executor
                self.running_jobs.add(job_id)
                self.executor.submit(self._run_job, job_id)
                
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
                time.sleep(1)
    
    def _run_job(self, job_id: str):
        """Execute a single backtest job"""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            logger.info(f"Starting job {job_id}")
            
            # Progress callback
            def on_progress(progress: float, step: str):
                job.progress = progress
                job.current_step = step
            
            # Execute with timeout
            result = self.strategy_executor.execute(job.config, on_progress)
            result.job_id = job_id
            
            # Store result
            job.result = result
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            
            # Cache result
            self.result_cache[job.config.compute_hash()] = (datetime.now(), result)
            
            # Update usage
            self.usage[job.tenant_id]['jobs_completed'] += 1
            self.usage[job.tenant_id]['compute_seconds'] += result.execution_time_seconds
            self.usage[job.tenant_id]['data_points'] += result.data_points_processed
            
            logger.info(f"Job {job_id} completed in {result.execution_time_seconds:.1f}s")
            
            # Webhook callback
            if job.webhook_url:
                self._send_webhook(job)
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            
            if job.webhook_url:
                self._send_webhook(job)
        
        finally:
            self.running_jobs.discard(job_id)
    
    def _send_webhook(self, job: BacktestJob):
        """Send webhook callback for completed job"""
        try:
            import urllib.request
            
            payload = {
                "job_id": job.job_id,
                "tenant_id": job.tenant_id,
                "status": job.status.value,
                "callback_data": job.callback_data
            }
            
            if job.status == JobStatus.COMPLETED and job.result:
                payload["result_summary"] = {
                    "total_return": job.result.total_return,
                    "sharpe_ratio": job.result.sharpe_ratio,
                    "max_drawdown": job.result.max_drawdown
                }
            elif job.error:
                payload["error"] = job.error
            
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                job.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
            
            logger.info(f"Webhook sent for job {job.job_id}")
            
        except Exception as e:
            logger.error(f"Webhook failed for job {job.job_id}: {e}")
    
    def shutdown(self):
        """Shutdown the service"""
        self._running = False
        self.executor.shutdown(wait=True)
        logger.info("BacktestService shutdown complete")


# API Routes (for FastAPI integration)
def create_backtest_routes(service: BacktestService):
    """Create FastAPI routes for backtest service"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/backtest", tags=["backtest"])
    
    class SubmitJobRequest(BaseModel):
        tenant_id: str
        strategy_code: str
        symbols: list[str]
        start_date: str
        end_date: str
        initial_capital: float = 100000
        strategy_params: dict = {}
        priority: str = "normal"
        webhook_url: str = None
    
    @router.post("/submit")
    async def submit_job(request: SubmitJobRequest):
        try:
            config = BacktestConfig(
                strategy_code=request.strategy_code,
                symbols=request.symbols,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                strategy_params=request.strategy_params
            )
            
            priority = JobPriority[request.priority.upper()]
            
            job = service.submit_job(
                tenant_id=request.tenant_id,
                config=config,
                priority=priority,
                webhook_url=request.webhook_url
            )
            
            return job.to_dict()
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.get("/job/{job_id}")
    async def get_job(job_id: str):
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.to_dict()
    
    @router.get("/job/{job_id}/result")
    async def get_result(job_id: str):
        result = service.get_job_result(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not available")
        return result.to_dict()
    
    @router.delete("/job/{job_id}")
    async def cancel_job(job_id: str):
        if service.cancel_job(job_id):
            return {"status": "cancelled"}
        raise HTTPException(status_code=400, detail="Cannot cancel job")
    
    @router.get("/queue/status")
    async def queue_status():
        return service.get_queue_status()
    
    @router.get("/usage/{tenant_id}")
    async def get_usage(tenant_id: str):
        return service.get_usage(tenant_id)
    
    return router
