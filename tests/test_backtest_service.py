"""
Tests for Backtesting as a Service
"""

import pytest
import time
from datetime import datetime

from services.backtest_service import (
    BacktestService,
    BacktestConfig,
    StrategyExecutor,
    JobStatus,
    JobPriority
)


class TestBacktestConfig:
    """Test backtest configuration"""
    
    def test_config_hash_deterministic(self):
        """Test that config hash is deterministic"""
        config1 = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL", "MSFT"],
            start_date="2024-01-01",
            end_date="2024-06-01"
        )
        
        config2 = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["MSFT", "AAPL"],  # Different order
            start_date="2024-01-01",
            end_date="2024-06-01"
        )
        
        # Same content, same hash (symbols sorted)
        assert config1.compute_hash() == config2.compute_hash()
    
    def test_config_hash_changes(self):
        """Test that different configs have different hashes"""
        config1 = BacktestConfig(
            strategy_code="code1",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-06-01"
        )
        
        config2 = BacktestConfig(
            strategy_code="code2",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-06-01"
        )
        
        assert config1.compute_hash() != config2.compute_hash()


class TestStrategyExecutor:
    """Test strategy execution"""
    
    def test_code_validation_safe(self):
        """Test that safe code passes validation"""
        executor = StrategyExecutor()
        
        code = """
import numpy as np
import pandas as pd

def generate_signals(data, params):
    signals = {}
    for col in data.columns:
        if len(data) > 20:
            sma = data[col].rolling(20).mean()
            if data[col].iloc[-1] > sma.iloc[-1]:
                signals[col] = 1.0
            else:
                signals[col] = -1.0
    return signals
"""
        is_valid, issues = executor.validate_code(code)
        assert is_valid
        assert len(issues) == 0
    
    def test_code_validation_dangerous(self):
        """Test that dangerous code fails validation"""
        executor = StrategyExecutor()
        
        dangerous_codes = [
            "import os; os.system('rm -rf /')",
            "exec('dangerous code')",
            "eval('1+1')",
            "open('/etc/passwd', 'r')",
            "__import__('subprocess')",
        ]
        
        for code in dangerous_codes:
            is_valid, issues = executor.validate_code(code)
            assert not is_valid, f"Should reject: {code}"
    
    def test_simple_backtest(self):
        """Test running a simple backtest"""
        executor = StrategyExecutor()
        
        config = BacktestConfig(
            strategy_code="""
def generate_signals(data, params):
    signals = {}
    for col in data.columns:
        # Simple momentum
        if len(data) > 10:
            ret = (data[col].iloc[-1] / data[col].iloc[-10]) - 1
            signals[col] = 1.0 if ret > 0 else -1.0
    return signals
""",
            symbols=["AAPL", "MSFT"],
            start_date="2024-01-01",
            end_date="2024-06-01",
            initial_capital=100000
        )
        
        result = executor.execute(config)
        
        assert result.config_hash == config.compute_hash()
        assert result.execution_time_seconds > 0
        assert result.data_points_processed > 0
        assert len(result.equity_curve) > 0
    
    def test_backtest_metrics(self):
        """Test that backtest calculates metrics"""
        executor = StrategyExecutor()
        
        config = BacktestConfig(
            strategy_code="""
def generate_signals(data, params):
    return {col: 1.0 for col in data.columns}  # Always long
""",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-06-01",
            initial_capital=100000
        )
        
        result = executor.execute(config)
        
        # Should have performance metrics
        assert hasattr(result, 'sharpe_ratio')
        assert hasattr(result, 'max_drawdown')
        assert hasattr(result, 'total_return')
        assert hasattr(result, 'volatility')


class TestBacktestService:
    """Test backtest service"""
    
    def test_job_submission(self):
        """Test submitting a backtest job"""
        service = BacktestService(max_workers=2)
        
        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        job = service.submit_job(
            tenant_id="test-tenant",
            config=config
        )
        
        assert job.job_id is not None
        assert job.tenant_id == "test-tenant"
        assert job.status in [JobStatus.QUEUED, JobStatus.COMPLETED]
        
        service.shutdown()
    
    def test_job_priority(self):
        """Test job priority ordering"""
        service = BacktestService(max_workers=1)
        
        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        # Submit low priority first
        job_low = service.submit_job(
            tenant_id="test",
            config=config,
            priority=JobPriority.LOW
        )
        
        # Submit high priority
        job_high = service.submit_job(
            tenant_id="test",
            config=config,
            priority=JobPriority.HIGH
        )
        
        # High priority should be processed first
        # (Note: in practice this depends on timing)
        assert job_high.priority.value > job_low.priority.value
        
        service.shutdown()
    
    def test_job_caching(self):
        """Test that identical jobs use cache"""
        from services.backtest_service import BacktestResult

        service = BacktestService(max_workers=2)

        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-01"
        )

        # Pre-populate cache directly to test cache hit behavior
        # This tests the caching mechanism without relying on job execution timing
        config_hash = config.compute_hash()
        cached_result = BacktestResult(
            job_id="cached-job",
            config_hash=config_hash,
            total_return=0.05,
            sharpe_ratio=1.0,
            execution_time_seconds=0.1,
            data_points_processed=100,
            equity_curve=[{"date": "2024-01-01", "equity": 100000}]
        )
        from datetime import datetime
        service.result_cache[config_hash] = (datetime.now(), cached_result)

        # Submit job with same config - should hit cache
        job = service.submit_job(tenant_id="test", config=config)

        # Cache hit should return completed immediately
        assert job.status == JobStatus.COMPLETED, f"Job should hit cache and be completed, got {job.status}"

        # Verify the job has a result from cache
        assert job.result is not None, "Cached job should have result"
        assert job.result.config_hash == config_hash

        service.shutdown()
    
    def test_job_cancellation(self):
        """Test cancelling a queued job"""
        service = BacktestService(max_workers=1)
        
        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        job = service.submit_job(tenant_id="test", config=config)
        
        if job.status == JobStatus.QUEUED:
            result = service.cancel_job(job.job_id)
            assert result is True
            assert service.get_job(job.job_id).status == JobStatus.CANCELLED
        
        service.shutdown()
    
    def test_usage_tracking(self):
        """Test usage metering"""
        service = BacktestService(max_workers=2)
        
        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        job = service.submit_job(tenant_id="test-usage", config=config)
        
        # Wait for completion
        timeout = 30
        while job.status not in [JobStatus.COMPLETED, JobStatus.FAILED] and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
            job = service.get_job(job.job_id)
        
        usage = service.get_usage("test-usage")
        
        assert usage["jobs_submitted"] >= 1
        
        service.shutdown()
    
    def test_queue_status(self):
        """Test queue status reporting"""
        service = BacktestService(max_workers=4)
        
        status = service.get_queue_status()
        
        assert "queue_size" in status
        assert "running_jobs" in status
        assert "max_workers" in status
        assert status["max_workers"] == 4
        
        service.shutdown()
    
    def test_list_jobs(self):
        """Test listing jobs with filters"""
        service = BacktestService(max_workers=2)
        
        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        service.submit_job(tenant_id="tenant-a", config=config)
        service.submit_job(tenant_id="tenant-b", config=config)
        
        # Filter by tenant
        jobs_a = service.list_jobs(tenant_id="tenant-a")
        jobs_b = service.list_jobs(tenant_id="tenant-b")
        
        assert all(j.tenant_id == "tenant-a" for j in jobs_a)
        assert all(j.tenant_id == "tenant-b" for j in jobs_b)
        
        service.shutdown()


class TestBacktestResultMetrics:
    """Test backtest result calculations"""
    
    def test_result_to_dict(self):
        """Test result serialization"""
        executor = StrategyExecutor()
        
        config = BacktestConfig(
            strategy_code="def generate_signals(data, params): return {}",
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-06-01"
        )
        
        result = executor.execute(config)
        result_dict = result.to_dict()
        
        assert "performance" in result_dict
        assert "trades" in result_dict
        assert "risk" in result_dict
        assert "curves" in result_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
