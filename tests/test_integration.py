"""
Integration Tests - End-to-End Pipeline Testing
QUANT_INDUSTRY_V1

Tests the complete flow: Data → Signals → Risk → Execution → Portfolio
"""

import pytest
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDataToSignalPipeline:
    """Test data ingestion through signal generation."""
    
    @pytest.fixture
    def sample_market_data(self):
        """Generate realistic market data for testing."""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=252, freq='B')
        
        # Generate correlated returns for multiple assets
        n_assets = 5
        tickers = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META']
        
        # Correlation matrix
        corr = np.array([
            [1.0, 0.6, 0.7, 0.5, 0.4],
            [0.6, 1.0, 0.65, 0.55, 0.45],
            [0.7, 0.65, 1.0, 0.6, 0.5],
            [0.5, 0.55, 0.6, 1.0, 0.6],
            [0.4, 0.45, 0.5, 0.6, 1.0]
        ])
        
        # Cholesky decomposition for correlated returns
        L = np.linalg.cholesky(corr)
        uncorrelated = np.random.randn(len(dates), n_assets)
        correlated_returns = uncorrelated @ L.T * 0.02  # ~2% daily vol
        
        # Build price series
        prices = {}
        base_prices = [150, 140, 380, 180, 500]
        for i, ticker in enumerate(tickers):
            price_series = base_prices[i] * np.exp(np.cumsum(correlated_returns[:, i]))
            prices[ticker] = pd.DataFrame({
                'open': price_series * (1 + np.random.randn(len(dates)) * 0.005),
                'high': price_series * (1 + np.abs(np.random.randn(len(dates)) * 0.01)),
                'low': price_series * (1 - np.abs(np.random.randn(len(dates)) * 0.01)),
                'close': price_series,
                'volume': np.random.randint(1000000, 50000000, len(dates))
            }, index=dates)
        
        return prices
    
    @pytest.fixture
    def sample_order_book(self):
        """Generate sample order book data."""
        mid_price = 150.0
        levels = 10
        
        bids = []
        asks = []
        
        for i in range(levels):
            bid_price = mid_price - (i + 1) * 0.01
            ask_price = mid_price + (i + 1) * 0.01
            bid_size = np.random.randint(100, 10000)
            ask_size = np.random.randint(100, 10000)
            
            bids.append({'price': bid_price, 'size': bid_size})
            asks.append({'price': ask_price, 'size': ask_size})
        
        return {'bids': bids, 'asks': asks, 'timestamp': datetime.now()}
    
    def test_momentum_signal_generation(self, sample_market_data):
        """Test cross-asset momentum signal generation."""
        from alpha.cross_asset_momentum import CrossAssetMomentum
        
        # Combine into single DataFrame
        close_prices = pd.DataFrame({
            ticker: data['close'] 
            for ticker, data in sample_market_data.items()
        })
        
        momentum = CrossAssetMomentum(
            lookback_periods=[21, 63, 126],
            holding_period=21
        )
        
        signals = momentum.generate_signals(close_prices)
        
        # Verify signal properties
        assert signals is not None
        assert len(signals) > 0
        assert all(-1 <= s <= 1 for s in signals.values())
        
    def test_order_book_signals(self, sample_order_book):
        """Test order book imbalance signal generation."""
        from hft.order_book import OrderBook
        
        book = OrderBook(symbol='AAPL', levels=10)
        
        # Process order book
        for bid in sample_order_book['bids']:
            book.update_bid(bid['price'], bid['size'])
        for ask in sample_order_book['asks']:
            book.update_ask(ask['price'], ask['size'])
        
        # Get signals
        imbalance = book.get_imbalance()
        vpin = book.calculate_vpin(window=50)
        microprice = book.get_microprice()
        
        assert -1 <= imbalance <= 1
        assert microprice > 0
        

class TestRiskManagementPipeline:
    """Test risk calculations and monitoring."""
    
    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio for risk testing."""
        return {
            'AAPL': {'shares': 1000, 'avg_cost': 145.0, 'current_price': 150.0},
            'GOOGL': {'shares': 500, 'avg_cost': 135.0, 'current_price': 140.0},
            'MSFT': {'shares': 800, 'avg_cost': 370.0, 'current_price': 380.0},
            'AMZN': {'shares': 300, 'avg_cost': 175.0, 'current_price': 180.0},
            'META': {'shares': 200, 'avg_cost': 480.0, 'current_price': 500.0},
        }
    
    @pytest.fixture
    def historical_returns(self):
        """Generate historical returns for VaR calculation."""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=504, freq='B')
        
        returns = pd.DataFrame({
            'AAPL': np.random.randn(504) * 0.02,
            'GOOGL': np.random.randn(504) * 0.025,
            'MSFT': np.random.randn(504) * 0.018,
            'AMZN': np.random.randn(504) * 0.028,
            'META': np.random.randn(504) * 0.03,
        }, index=dates)
        
        return returns
    
    def test_monte_carlo_var(self, sample_portfolio, historical_returns):
        """Test Monte Carlo VaR calculation."""
        from risk.monte_carlo import MonteCarloRisk
        
        mc = MonteCarloRisk(n_simulations=10000, time_horizon=21)
        
        # Calculate portfolio value
        portfolio_value = sum(
            pos['shares'] * pos['current_price'] 
            for pos in sample_portfolio.values()
        )
        
        # Get weights
        weights = {
            ticker: (pos['shares'] * pos['current_price']) / portfolio_value
            for ticker, pos in sample_portfolio.items()
        }
        
        var_95, cvar_95 = mc.calculate_var(
            returns=historical_returns,
            weights=weights,
            confidence=0.95
        )
        
        assert var_95 < 0  # VaR should be negative (loss)
        assert cvar_95 <= var_95  # CVaR should be worse than VaR
        
    def test_tail_risk_detection(self, historical_returns):
        """Test tail risk detection system."""
        from risk.tail_risk import TailRiskDetector
        
        detector = TailRiskDetector(
            var_threshold=0.95,
            tail_threshold=3.0
        )
        
        # Inject a tail event
        returns_with_crash = historical_returns.copy()
        returns_with_crash.iloc[-1] = -0.15  # 15% crash
        
        tail_events = detector.detect_tail_events(returns_with_crash)
        
        assert len(tail_events) > 0
        assert tail_events[-1]['severity'] > 2.0
        
    def test_circuit_breaker_triggers(self, sample_portfolio):
        """Test circuit breaker functionality."""
        from core.circuit_breaker import CircuitBreaker
        
        breaker = CircuitBreaker(
            max_drawdown=0.10,
            max_daily_loss=0.05,
            max_position_loss=0.15
        )
        
        # Simulate losses
        portfolio_value = 1000000
        current_value = 920000  # 8% drawdown
        
        status = breaker.check_status(
            initial_value=portfolio_value,
            current_value=current_value,
            daily_pnl=-35000
        )
        
        assert status['state'] in ['GREEN', 'YELLOW', 'RED']
        

class TestExecutionPipeline:
    """Test order execution and slippage management."""
    
    @pytest.fixture
    def execution_context(self):
        """Create execution context."""
        return {
            'symbol': 'AAPL',
            'side': 'BUY',
            'quantity': 10000,
            'price': 150.0,
            'urgency': 0.5,
            'adv': 50000000,  # Average daily volume
            'volatility': 0.25
        }
    
    def test_vwap_execution(self, execution_context):
        """Test VWAP execution algorithm."""
        from execution.execution_algorithms import VWAPExecutor
        
        executor = VWAPExecutor(
            participation_rate=0.10,
            time_horizon_minutes=120
        )
        
        schedule = executor.generate_schedule(
            quantity=execution_context['quantity'],
            adv=execution_context['adv']
        )
        
        assert len(schedule) > 0
        assert sum(s['quantity'] for s in schedule) == execution_context['quantity']
        
    def test_twap_execution(self, execution_context):
        """Test TWAP execution algorithm."""
        from execution.execution_algorithms import TWAPExecutor
        
        executor = TWAPExecutor(
            num_slices=20,
            time_horizon_minutes=60
        )
        
        schedule = executor.generate_schedule(
            quantity=execution_context['quantity']
        )
        
        assert len(schedule) == 20
        assert all(s['quantity'] == execution_context['quantity'] // 20 for s in schedule[:-1])
        
    def test_implementation_shortfall(self, execution_context):
        """Test Implementation Shortfall algorithm."""
        from execution.execution_algorithms import ISExecutor
        
        executor = ISExecutor(
            risk_aversion=0.001,
            temporary_impact=0.1,
            permanent_impact=0.05
        )
        
        schedule = executor.generate_schedule(
            quantity=execution_context['quantity'],
            price=execution_context['price'],
            volatility=execution_context['volatility'],
            adv=execution_context['adv']
        )
        
        expected_cost = executor.estimate_cost(
            quantity=execution_context['quantity'],
            price=execution_context['price'],
            volatility=execution_context['volatility'],
            adv=execution_context['adv']
        )
        
        assert expected_cost > 0
        assert expected_cost < execution_context['quantity'] * execution_context['price'] * 0.01
        
    def test_position_sizing_kelly(self, execution_context):
        """Test Kelly criterion position sizing."""
        from execution.position_sizing import KellyPositionSizer
        
        sizer = KellyPositionSizer(
            max_position=0.25,
            kelly_fraction=0.5
        )
        
        position = sizer.calculate_position(
            win_rate=0.55,
            win_loss_ratio=1.5,
            portfolio_value=1000000,
            current_price=execution_context['price']
        )
        
        assert position['shares'] > 0
        assert position['dollars'] <= 250000  # Max 25% position


class TestPortfolioOptimization:
    """Test portfolio optimization algorithms."""
    
    @pytest.fixture
    def asset_data(self):
        """Generate asset data for optimization."""
        np.random.seed(42)
        
        # Expected returns (annualized)
        expected_returns = pd.Series({
            'AAPL': 0.12,
            'GOOGL': 0.15,
            'MSFT': 0.10,
            'AMZN': 0.18,
            'META': 0.20,
            'BND': 0.04,
            'GLD': 0.06
        })
        
        # Covariance matrix
        n_assets = len(expected_returns)
        random_matrix = np.random.randn(n_assets, n_assets)
        cov_matrix = random_matrix @ random_matrix.T / 100
        np.fill_diagonal(cov_matrix, np.diag(cov_matrix) * 2)
        
        cov_df = pd.DataFrame(
            cov_matrix,
            index=expected_returns.index,
            columns=expected_returns.index
        )
        
        return expected_returns, cov_df
    
    def test_mean_variance_optimization(self, asset_data):
        """Test Markowitz mean-variance optimization."""
        from portfolio.optimization import MeanVarianceOptimizer
        
        expected_returns, cov_matrix = asset_data
        
        optimizer = MeanVarianceOptimizer()
        
        weights = optimizer.optimize(
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            target_return=0.12
        )
        
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert all(w >= -0.01 for w in weights.values())  # Allow small negative for numerical
        
    def test_hierarchical_risk_parity(self, asset_data):
        """Test HRP optimization."""
        from portfolio.optimization import HierarchicalRiskParity
        
        expected_returns, cov_matrix = asset_data
        
        hrp = HierarchicalRiskParity()
        
        weights = hrp.optimize(cov_matrix=cov_matrix)
        
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert all(w >= 0 for w in weights.values())  # HRP produces long-only
        
    def test_black_litterman(self, asset_data):
        """Test Black-Litterman optimization."""
        from portfolio.optimization import BlackLitterman
        
        expected_returns, cov_matrix = asset_data
        
        bl = BlackLitterman(risk_aversion=2.5)
        
        # Define views
        views = {
            'AAPL': 0.15,  # Bullish on AAPL
            'META': 0.25   # Very bullish on META
        }
        view_confidence = {
            'AAPL': 0.8,
            'META': 0.6
        }
        
        weights = bl.optimize(
            market_weights={'AAPL': 0.2, 'GOOGL': 0.15, 'MSFT': 0.2, 
                          'AMZN': 0.15, 'META': 0.15, 'BND': 0.1, 'GLD': 0.05},
            cov_matrix=cov_matrix,
            views=views,
            view_confidence=view_confidence
        )
        
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestMLPipeline:
    """Test ML model pipeline."""
    
    @pytest.fixture
    def feature_data(self):
        """Generate feature data for ML testing."""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=252, freq='B')
        
        features = pd.DataFrame({
            'momentum_21d': np.random.randn(252),
            'momentum_63d': np.random.randn(252),
            'volatility_21d': np.abs(np.random.randn(252)) * 0.2,
            'rsi': np.random.uniform(20, 80, 252),
            'macd': np.random.randn(252) * 2,
            'volume_ratio': np.random.uniform(0.5, 2.0, 252),
            'spread': np.random.uniform(0.01, 0.05, 252),
        }, index=dates)
        
        # Target: next day return direction
        targets = (np.random.randn(252) > 0).astype(int)
        
        return features, targets
    
    def test_feature_store_pit_correctness(self, feature_data):
        """Test feature store point-in-time correctness."""
        from ml.feature_store import FeatureStore
        
        features, _ = feature_data
        
        store = FeatureStore()
        store.add_features('momentum', features[['momentum_21d', 'momentum_63d']])
        store.add_features('technical', features[['rsi', 'macd']])
        
        # Get features as of specific date
        as_of_date = features.index[100]
        retrieved = store.get_features(
            feature_groups=['momentum', 'technical'],
            as_of=as_of_date
        )
        
        # Should not include future data
        assert retrieved.index.max() <= as_of_date
        
    def test_confidence_calibration(self, feature_data):
        """Test model confidence calibration."""
        from brain.confidence_calibration import ConfidenceCalibrator
        
        features, targets = feature_data
        
        calibrator = ConfidenceCalibrator(n_bins=10)
        
        # Simulate model predictions
        predictions = np.random.uniform(0, 1, len(targets))
        
        # Calibrate
        calibrator.fit(predictions[:200], targets[:200])
        calibrated = calibrator.transform(predictions[200:])
        
        assert len(calibrated) == len(predictions[200:])
        assert all(0 <= p <= 1 for p in calibrated)
        
    def test_regime_detection(self, feature_data):
        """Test regime detection."""
        from brain.regime_ensemble import RegimeDetector
        
        features, _ = feature_data
        
        detector = RegimeDetector(n_regimes=3)
        
        regimes = detector.fit_predict(features[['volatility_21d', 'momentum_21d']])
        
        assert len(regimes) == len(features)
        assert set(regimes).issubset({0, 1, 2})


class TestEndToEndPipeline:
    """Full integration test of the entire system."""
    
    @pytest.fixture
    def system_config(self):
        """System configuration for integration test."""
        return {
            'universe': ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META'],
            'initial_capital': 1000000,
            'max_position_size': 0.20,
            'risk_limit': 0.10,
            'rebalance_frequency': 'weekly'
        }
    
    @pytest.mark.asyncio
    async def test_full_trading_cycle(self, system_config):
        """Test complete trading cycle from signal to execution."""
        from core.orchestrator import TradingOrchestrator
        
        # Initialize orchestrator
        orchestrator = TradingOrchestrator(config=system_config)
        
        # Mock market data
        with patch.object(orchestrator, 'fetch_market_data') as mock_data:
            mock_data.return_value = self._generate_mock_data(system_config['universe'])
            
            # Run single cycle
            result = await orchestrator.run_cycle()
            
            assert result['status'] == 'completed'
            assert 'signals' in result
            assert 'risk_check' in result
            assert 'orders' in result
            
    def _generate_mock_data(self, universe):
        """Generate mock market data."""
        np.random.seed(42)
        data = {}
        for symbol in universe:
            price = np.random.uniform(100, 500)
            data[symbol] = {
                'price': price,
                'volume': np.random.randint(1000000, 50000000),
                'bid': price - 0.01,
                'ask': price + 0.01,
                'returns_21d': np.random.randn() * 0.05
            }
        return data
    
    @pytest.mark.asyncio
    async def test_risk_breach_handling(self, system_config):
        """Test system behavior on risk breach."""
        from core.orchestrator import TradingOrchestrator
        from core.circuit_breaker import CircuitBreaker
        
        orchestrator = TradingOrchestrator(config=system_config)
        
        # Simulate risk breach
        orchestrator.circuit_breaker.trigger(
            reason='max_drawdown',
            severity='RED'
        )
        
        # Attempt to trade
        result = await orchestrator.run_cycle()
        
        assert result['status'] == 'blocked'
        assert 'circuit_breaker' in result['reason']
        
    @pytest.mark.asyncio
    async def test_data_provider_failover(self, system_config):
        """Test data provider failover mechanism."""
        from data.unified_api import UnifiedDataAPI
        
        api = UnifiedDataAPI(
            primary='alphavantage',
            fallback=['yahoo', 'polygon']
        )
        
        # Mock primary failure
        with patch.object(api, '_fetch_alphavantage') as mock_primary:
            mock_primary.side_effect = Exception("API limit exceeded")
            
            with patch.object(api, '_fetch_yahoo') as mock_fallback:
                mock_fallback.return_value = {'price': 150.0}
                
                result = await api.get_quote('AAPL')
                
                assert result['price'] == 150.0
                assert mock_fallback.called


class TestAPIEndpoints:
    """Test API endpoint integration."""
    
    @pytest.fixture
    def test_client(self):
        """Create test client for API testing."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        return TestClient(app)
    
    def test_risk_endpoint(self, test_client):
        """Test risk metrics endpoint."""
        response = test_client.get('/api/risk/metrics')
        
        assert response.status_code == 200
        data = response.json()
        assert 'var_95' in data
        assert 'portfolio_beta' in data
        
    def test_orderbook_endpoint(self, test_client):
        """Test order book endpoint."""
        response = test_client.get('/api/orderbook/AAPL')
        
        assert response.status_code == 200
        data = response.json()
        assert 'bids' in data
        assert 'asks' in data
        
    def test_signals_endpoint(self, test_client):
        """Test signals endpoint."""
        response = test_client.get('/api/signals/latest')
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
    def test_portfolio_endpoint(self, test_client):
        """Test portfolio endpoint."""
        response = test_client.get('/api/portfolio/positions')
        
        assert response.status_code == 200
        data = response.json()
        assert 'positions' in data
        assert 'total_value' in data


# Run configuration
if __name__ == '__main__':
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '-x',  # Stop on first failure
        '--asyncio-mode=auto'
    ])
