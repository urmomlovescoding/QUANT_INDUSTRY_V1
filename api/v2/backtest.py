"""
QUANT INDUSTRY V1 - Backtesting API (v2)
========================================
Strategy backtesting: run, strategies, monte carlo.
Wired to real backtest engine implementations.
"""

from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime, date, timedelta
from enum import Enum
import uuid
import logging
import numpy as np

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class BacktestStatus(str, Enum):
    """Backtest job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StrategyType(str, Enum):
    """Strategy types."""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend_following"
    PAIRS = "pairs"
    ML_ENSEMBLE = "ml_ensemble"
    SVM = "svm"
    CUSTOM = "custom"


# ============================================================================
# Pydantic Models
# ============================================================================

class BacktestRequest(BaseModel):
    """Backtest run request."""
    strategy_id: Optional[str] = Field(None, description="Existing strategy ID")
    strategy_type: Optional[StrategyType] = Field(None, description="Built-in strategy type")
    custom_code: Optional[str] = Field(None, description="Custom strategy code")
    symbols: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    initial_capital: float = Field(100000, gt=0)
    commission: float = Field(0.001, ge=0)
    slippage: float = Field(0.001, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)


class Trade(BaseModel):
    """Individual trade from backtest."""
    symbol: str
    entry_date: datetime
    exit_date: datetime
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float
    holding_period_days: int


class EquityCurvePoint(BaseModel):
    """Equity curve data point."""
    date: date
    equity: float
    drawdown: float
    drawdown_percent: float


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""
    total_return: float
    total_return_percent: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_percent: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_period: float
    best_trade: float
    worst_trade: float
    volatility: float
    beta: Optional[float] = None
    alpha: Optional[float] = None


class BacktestResult(BaseModel):
    """Backtest result."""
    backtest_id: str
    status: BacktestStatus
    strategy_name: str
    symbols: list[str]
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    metrics: Optional[BacktestMetrics] = None
    equity_curve: list[EquityCurvePoint] = Field(default_factory=list)
    trades: list[Trade] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class Strategy(BaseModel):
    """Strategy definition."""
    id: str
    name: str
    description: str
    strategy_type: StrategyType
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    default_symbols: list[str] = Field(default_factory=list)
    created_at: datetime
    last_backtest: Optional[datetime] = None
    best_sharpe: Optional[float] = None


class StrategiesResponse(BaseModel):
    """List of strategies."""
    strategies: list[Strategy] = Field(default_factory=list)
    total: int


class MonteCarloRequest(BaseModel):
    """Monte Carlo simulation request."""
    backtest_id: str = Field(..., description="Source backtest to simulate from")
    num_simulations: int = Field(1000, ge=100, le=100000)
    confidence_levels: list[float] = Field(default=[0.95, 0.99])
    randomize_order: bool = Field(True, description="Randomize trade order")
    randomize_returns: bool = Field(False, description="Sample from return distribution")


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result."""
    simulation_id: str
    backtest_id: str
    num_simulations: int
    median_return: float
    mean_return: float
    std_return: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown_median: float
    max_drawdown_95: float
    probability_of_profit: float
    probability_of_ruin: float = Field(..., description="P(drawdown > 50%)")
    percentiles: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OptimizationRequest(BaseModel):
    """Strategy optimization request."""
    strategy_id: str
    symbols: list[str]
    start_date: date
    end_date: date
    parameter_ranges: dict[str, dict[str, Any]]
    optimization_target: str = Field("sharpe_ratio", description="Metric to optimize")
    num_iterations: int = Field(100, ge=10, le=1000)


class OptimizationResult(BaseModel):
    """Optimization result."""
    optimization_id: str
    strategy_id: str
    best_parameters: dict[str, Any]
    best_metric_value: float
    optimization_target: str
    iterations_run: int
    parameter_sensitivity: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Service Imports & Initialization
# ============================================================================

# Store for backtest results (in production, use database)
_backtest_cache: dict[str, BacktestResult] = {}

# Strategy mapping
STRATEGY_TYPE_MAP = {
    StrategyType.MOMENTUM: "momentum",
    StrategyType.MEAN_REVERSION: "rsi",  # or "bollinger"
    StrategyType.BREAKOUT: "breakout",
    StrategyType.TREND_FOLLOWING: "trend_following",
    StrategyType.PAIRS: "ma_crossover",
    StrategyType.ML_ENSEMBLE: "ml_ensemble",
    StrategyType.SVM: "svm",
}


def _get_beast_engine():
    """Get the BEAST ML engine for ML-based backtesting."""
    try:
        from brain.beast_ml import get_beast_engine
        return get_beast_engine()
    except ImportError:
        try:
            from backend.brain.beast_ml import get_beast_engine
            return get_beast_engine()
        except ImportError:
            return None


def _get_data_service():
    """Get the data service singleton."""
    try:
        from services.data_service import get_data_service
        return get_data_service()
    except ImportError:
        return None


def _get_backtest_strategies():
    """Get backtest strategies module."""
    try:
        from backend.backtest import strategies as bt_strategies
        return bt_strategies
    except ImportError:
        try:
            from backtest import strategies as bt_strategies
            return bt_strategies
        except ImportError:
            return None


def _get_strategy_registry():
    """Get strategy registry from strategies package."""
    try:
        from strategies import list_strategies, STRATEGY_REGISTRY
        return list_strategies, STRATEGY_REGISTRY
    except ImportError:
        return None, None


def _get_backtest_engine():
    """Get backtest engine."""
    try:
        from backtest.engine import BacktestEngine, BacktestConfig
        return BacktestEngine, BacktestConfig
    except ImportError:
        try:
            from backtest import BacktestEngine, BacktestConfig
            return BacktestEngine, BacktestConfig
        except ImportError:
            return None, None


def _get_monte_carlo():
    """Get Monte Carlo analyzer."""
    try:
        from backtest.engine import MonteCarloAnalyzer
        return MonteCarloAnalyzer
    except ImportError:
        try:
            from brain.math.backtester import MonteCarloSimulator
            return MonteCarloSimulator
        except ImportError:
            return None


# ============================================================================
# Helper Functions
# ============================================================================

def _fetch_historical_data(symbols: list[str], start_date: date, end_date: date) -> dict:
    """Fetch historical data for symbols."""
    ds = _get_data_service()
    if not ds:
        return {}
    
    data = {}
    period = _calculate_period(start_date, end_date)
    
    for symbol in symbols:
        try:
            historical = ds.get_historical(symbol.upper(), period, "1d")
            if historical and len(historical) > 0:
                data[symbol] = {
                    'close': [h.close for h in historical],
                    'open': [h.open for h in historical],
                    'high': [h.high for h in historical],
                    'low': [h.low for h in historical],
                    'volume': [h.volume for h in historical],
                    'timestamp': [h.timestamp if hasattr(h, 'timestamp') else datetime.now() for h in historical]
                }
        except Exception as e:
            logger.warning(f"Failed to fetch data for {symbol}: {e}")
    
    return data


def _calculate_period(start_date: date, end_date: date) -> str:
    """Calculate yfinance period string from dates."""
    days = (end_date - start_date).days
    if days <= 30:
        return "1mo"
    elif days <= 90:
        return "3mo"
    elif days <= 180:
        return "6mo"
    elif days <= 365:
        return "1y"
    elif days <= 730:
        return "2y"
    else:
        return "5y"


def _run_ml_backtest(
    strategy_name: str,
    data: dict,
    initial_capital: float,
    commission: float,
    slippage: float,
    parameters: dict
) -> tuple[list, list, float]:
    """
    Run ML-based backtest using BEAST ML engine (including SVM).
    Uses walk-forward training on historical data to generate signals.
    """
    import pandas as pd

    beast = _get_beast_engine()
    if beast is None:
        raise HTTPException(status_code=500, detail="BEAST ML engine not available")

    symbol = list(data.keys())[0]
    symbol_data = data[symbol]

    # Build DataFrame from data
    df = pd.DataFrame({
        'open': symbol_data.get('open', symbol_data['close']),
        'high': symbol_data.get('high', symbol_data['close']),
        'low': symbol_data.get('low', symbol_data['close']),
        'close': symbol_data['close'],
        'volume': symbol_data.get('volume', [0] * len(symbol_data['close']))
    })

    if len(df) < 100:
        raise HTTPException(status_code=400, detail="Insufficient data for ML backtest (need 100+ bars)")

    # Walk-forward: train on first 70%, test on last 30%
    train_size = int(len(df) * 0.7)
    train_df = df.iloc[:train_size]
    test_df = df.iloc[train_size:]

    # Train all models (including SVM)
    try:
        beast.walk_forward_train(train_df)
    except Exception as e:
        logger.warning(f"ML training failed, using untrained signals: {e}")

    # Generate signals on test period using sliding window
    timestamps = symbol_data.get('timestamp', [])
    closes = np.array(symbol_data['close'])
    equity = initial_capital
    cash = initial_capital
    shares = 0
    in_position = False
    entry_price = 0.0
    entry_idx = 0
    trades = []
    equity_curve = []

    confidence_threshold = parameters.get('confidence_threshold', 0.65)
    lookback = 200  # Lookback window for feature calculation

    for i in range(train_size, len(df)):
        current_price = closes[i]

        # Generate prediction using sliding window
        try:
            window_start = max(0, i - lookback)
            window_df = df.iloc[window_start:i + 1]

            if beast.is_trained and len(window_df) >= 50:
                prediction = beast.predict(window_df)
                signal = prediction.get('signal')
                confidence = prediction.get('confidence', 0)

                # Generate buy/sell signals from ML prediction
                if hasattr(signal, 'value'):
                    signal_val = signal.value
                else:
                    signal_val = 0

                if signal_val > 0 and confidence >= confidence_threshold and not in_position:
                    # Buy
                    trade_value = cash * 0.95
                    shares = int(trade_value / current_price)
                    if shares > 0:
                        cost = shares * current_price * (1 + slippage)
                        commission_cost = cost * commission
                        cash -= (cost + commission_cost)
                        in_position = True
                        entry_price = current_price * (1 + slippage)
                        entry_idx = i

                elif signal_val < 0 and in_position:
                    # Sell
                    proceeds = shares * current_price * (1 - slippage)
                    commission_cost = proceeds * commission
                    cash += (proceeds - commission_cost)

                    pnl = proceeds - commission_cost - (shares * entry_price)
                    pnl_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else 0

                    trade_record = {
                        'symbol': symbol,
                        'entry_date': timestamps[entry_idx] if entry_idx < len(timestamps) else datetime.now(),
                        'exit_date': timestamps[i] if i < len(timestamps) else datetime.now(),
                        'side': 'long',
                        'quantity': shares,
                        'entry_price': entry_price,
                        'exit_price': current_price * (1 - slippage),
                        'pnl': pnl,
                        'pnl_percent': pnl_pct,
                        'holding_period_days': i - entry_idx
                    }
                    trades.append(trade_record)
                    shares = 0
                    in_position = False
        except Exception as e:
            logger.debug(f"ML prediction error at bar {i}: {e}")

        # Calculate equity
        equity = cash + (shares * current_price if in_position else 0)
        peak = max(initial_capital, max([e['equity'] for e in equity_curve]) if equity_curve else initial_capital)
        drawdown = peak - equity
        drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0

        equity_curve.append({
            'date': timestamps[i].date() if i < len(timestamps) and hasattr(timestamps[i], 'date') else date.today(),
            'equity': equity,
            'drawdown': drawdown,
            'drawdown_percent': drawdown_pct
        })

    # Close remaining position
    if in_position and len(closes) > 0:
        final_price = closes[-1]
        proceeds = shares * final_price * (1 - slippage)
        commission_cost = proceeds * commission
        cash += (proceeds - commission_cost)
        pnl = proceeds - commission_cost - (shares * entry_price)
        pnl_pct = (final_price / entry_price - 1) * 100 if entry_price > 0 else 0

        trades.append({
            'symbol': symbol,
            'entry_date': timestamps[entry_idx] if entry_idx < len(timestamps) else datetime.now(),
            'exit_date': timestamps[-1] if timestamps else datetime.now(),
            'side': 'long',
            'quantity': shares,
            'entry_price': entry_price,
            'exit_price': final_price * (1 - slippage),
            'pnl': pnl,
            'pnl_percent': pnl_pct,
            'holding_period_days': len(closes) - 1 - entry_idx
        })
        equity = cash

    return trades, equity_curve, equity


def _run_strategy_backtest(
    strategy_name: str,
    data: dict,
    initial_capital: float,
    commission: float,
    slippage: float,
    parameters: dict
) -> tuple[list, list, float]:
    """Run strategy backtest and return trades, equity curve, final value."""
    # Route ML/SVM strategies to the ML backtest engine
    if strategy_name in ('ml_ensemble', 'svm'):
        return _run_ml_backtest(
            strategy_name, data, initial_capital,
            commission, slippage, parameters
        )

    bt_strategies = _get_backtest_strategies()

    if not bt_strategies:
        raise HTTPException(status_code=500, detail="Backtest strategies module not available")
    
    # Get the first symbol's data
    symbol = list(data.keys())[0]
    symbol_data = data[symbol]
    
    closes = np.array(symbol_data['close'])
    opens = np.array(symbol_data.get('open', symbol_data['close']))
    highs = np.array(symbol_data.get('high', symbol_data['close']))
    lows = np.array(symbol_data.get('low', symbol_data['close']))
    volumes = np.array(symbol_data.get('volume', [0] * len(closes)))
    timestamps = symbol_data.get('timestamp', [])
    
    # Get strategy class
    try:
        strategy = bt_strategies.get_strategy(strategy_name, **parameters)
    except ValueError:
        # Fall back to default strategy
        strategy = bt_strategies.MACrossoverStrategy(**parameters)
    
    # Generate signals
    signals = strategy.generate_signals(opens, highs, lows, closes, volumes)
    
    # Simple backtest simulation
    equity = initial_capital
    cash = initial_capital
    shares = 0
    in_position = False
    entry_price = 0.0
    entry_idx = 0
    trades = []
    equity_curve = []
    
    for i in range(len(closes)):
        current_price = closes[i]
        
        # Process signals
        if signals[i] == 1 and not in_position:  # Buy
            # Buy with available cash minus commission
            trade_value = cash * 0.95  # Leave some cash for fees
            shares = int(trade_value / current_price)
            if shares > 0:
                cost = shares * current_price * (1 + slippage)
                commission_cost = cost * commission
                cash -= (cost + commission_cost)
                in_position = True
                entry_price = current_price * (1 + slippage)
                entry_idx = i
                
        elif signals[i] == -1 and in_position:  # Sell
            proceeds = shares * current_price * (1 - slippage)
            commission_cost = proceeds * commission
            cash += (proceeds - commission_cost)
            
            # Record trade
            pnl = proceeds - commission_cost - (shares * entry_price)
            pnl_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else 0
            
            trade_record = {
                'symbol': symbol,
                'entry_date': timestamps[entry_idx] if entry_idx < len(timestamps) else datetime.now(),
                'exit_date': timestamps[i] if i < len(timestamps) else datetime.now(),
                'side': 'long',
                'quantity': shares,
                'entry_price': entry_price,
                'exit_price': current_price * (1 - slippage),
                'pnl': pnl,
                'pnl_percent': pnl_pct,
                'holding_period_days': i - entry_idx
            }
            trades.append(trade_record)
            
            shares = 0
            in_position = False
        
        # Calculate equity
        equity = cash + (shares * current_price if in_position else 0)
        
        # Record equity curve point
        peak = max(initial_capital, max([e['equity'] for e in equity_curve]) if equity_curve else initial_capital)
        drawdown = peak - equity
        drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0
        
        equity_point = {
            'date': timestamps[i].date() if i < len(timestamps) and hasattr(timestamps[i], 'date') else date.today(),
            'equity': equity,
            'drawdown': drawdown,
            'drawdown_percent': drawdown_pct
        }
        equity_curve.append(equity_point)
    
    # Close any remaining position
    if in_position and len(closes) > 0:
        final_price = closes[-1]
        proceeds = shares * final_price * (1 - slippage)
        commission_cost = proceeds * commission
        cash += (proceeds - commission_cost)
        
        pnl = proceeds - commission_cost - (shares * entry_price)
        pnl_pct = (final_price / entry_price - 1) * 100 if entry_price > 0 else 0
        
        trade_record = {
            'symbol': symbol,
            'entry_date': timestamps[entry_idx] if entry_idx < len(timestamps) else datetime.now(),
            'exit_date': timestamps[-1] if timestamps else datetime.now(),
            'side': 'long',
            'quantity': shares,
            'entry_price': entry_price,
            'exit_price': final_price * (1 - slippage),
            'pnl': pnl,
            'pnl_percent': pnl_pct,
            'holding_period_days': len(closes) - 1 - entry_idx
        }
        trades.append(trade_record)
        equity = cash
    
    return trades, equity_curve, equity


def _calculate_metrics(
    trades: list,
    equity_curve: list,
    initial_capital: float,
    final_capital: float,
    start_date: date,
    end_date: date
) -> BacktestMetrics:
    """Calculate backtest performance metrics."""
    total_return = final_capital - initial_capital
    total_return_pct = (total_return / initial_capital) * 100 if initial_capital > 0 else 0
    
    # Calculate days and annualized return
    days = (end_date - start_date).days
    years = days / 365.25 if days > 0 else 1
    annualized_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    # Calculate returns for Sharpe/Sortino
    if len(equity_curve) > 1:
        equities = [e['equity'] for e in equity_curve]
        returns = np.diff(equities) / equities[:-1]
        volatility = float(np.std(returns) * np.sqrt(252) * 100) if len(returns) > 0 else 0
        
        # Sharpe (assume 2% risk-free)
        excess_return = np.mean(returns) - 0.02 / 252
        sharpe = float(excess_return / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
        
        # Sortino
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0.01
        sortino = float(excess_return * 252 / downside_std) if downside_std > 0 else sharpe
    else:
        volatility = 0
        sharpe = 0
        sortino = 0
    
    # Max drawdown
    max_dd = max([e['drawdown'] for e in equity_curve]) if equity_curve else 0
    max_dd_pct = max([e['drawdown_percent'] for e in equity_curve]) if equity_curve else 0
    
    # Calmar ratio
    calmar = annualized_return / max_dd_pct if max_dd_pct > 0 else 0
    
    # Trade statistics
    total_trades = len(trades)
    if total_trades > 0:
        pnls = [t['pnl'] for t in trades]
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / total_trades
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t['pnl']) for t in losing_trades]) if losing_trades else 0
        avg_trade = np.mean(pnls)
        
        gross_profit = sum([t['pnl'] for t in winning_trades])
        gross_loss = abs(sum([t['pnl'] for t in losing_trades]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        best_trade = max(pnls)
        worst_trade = min(pnls)
        
        avg_holding = np.mean([t['holding_period_days'] for t in trades])
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        avg_trade = 0
        profit_factor = 0
        best_trade = 0
        worst_trade = 0
        avg_holding = 0
        winning_trades = []
        losing_trades = []
    
    return BacktestMetrics(
        total_return=round(total_return, 2),
        total_return_percent=round(total_return_pct, 2),
        annualized_return=round(annualized_return, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        calmar_ratio=round(calmar, 2),
        max_drawdown=round(max_dd, 2),
        max_drawdown_percent=round(max_dd_pct, 2),
        win_rate=round(win_rate, 3),
        profit_factor=round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        avg_trade=round(avg_trade, 2),
        total_trades=total_trades,
        winning_trades=len(winning_trades),
        losing_trades=len(losing_trades),
        avg_holding_period=round(avg_holding, 1),
        best_trade=round(best_trade, 2),
        worst_trade=round(worst_trade, 2),
        volatility=round(volatility, 2)
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/run",
    response_model=BacktestResult,
    summary="Run backtest",
    description="Run a backtest with specified strategy and parameters."
)
async def run_backtest(request: BacktestRequest) -> BacktestResult:
    """
    Run a strategy backtest.
    
    Supports built-in strategies, saved strategies, or custom code.
    Uses real market data and backtest engine.
    """
    backtest_id = str(uuid.uuid4())[:8]
    
    try:
        # Fetch historical data
        data = _fetch_historical_data(request.symbols, request.start_date, request.end_date)
        
        if not data:
            raise HTTPException(
                status_code=400,
                detail=f"No data available for symbols {request.symbols} in specified date range"
            )
        
        # Determine strategy name
        if request.strategy_type:
            strategy_name = STRATEGY_TYPE_MAP.get(request.strategy_type, "ma_crossover")
        elif request.strategy_id:
            strategy_name = request.strategy_id.split("-")[-1] if "-" in request.strategy_id else request.strategy_id
        else:
            strategy_name = "ma_crossover"
        
        # Run backtest
        trades_raw, equity_curve_raw, final_capital = _run_strategy_backtest(
            strategy_name=strategy_name,
            data=data,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
            parameters=request.parameters
        )
        
        # Convert to response models
        trades = [
            Trade(
                symbol=t['symbol'],
                entry_date=t['entry_date'] if isinstance(t['entry_date'], datetime) else datetime.combine(t['entry_date'], datetime.min.time()),
                exit_date=t['exit_date'] if isinstance(t['exit_date'], datetime) else datetime.combine(t['exit_date'], datetime.min.time()),
                side=t['side'],
                quantity=t['quantity'],
                entry_price=round(t['entry_price'], 2),
                exit_price=round(t['exit_price'], 2),
                pnl=round(t['pnl'], 2),
                pnl_percent=round(t['pnl_percent'], 2),
                holding_period_days=t['holding_period_days']
            )
            for t in trades_raw
        ]
        
        equity_curve = [
            EquityCurvePoint(
                date=e['date'] if isinstance(e['date'], date) else date.today(),
                equity=round(e['equity'], 2),
                drawdown=round(e['drawdown'], 2),
                drawdown_percent=round(e['drawdown_percent'], 2)
            )
            for e in equity_curve_raw[::max(1, len(equity_curve_raw) // 100)]  # Sample to ~100 points
        ]
        
        # Calculate metrics
        metrics = _calculate_metrics(
            trades_raw, equity_curve_raw,
            request.initial_capital, final_capital,
            request.start_date, request.end_date
        )
        
        result = BacktestResult(
            backtest_id=backtest_id,
            status=BacktestStatus.COMPLETED,
            strategy_name=strategy_name,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            final_capital=round(final_capital, 2),
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades[:100],  # Limit trade log
            parameters=request.parameters,
            completed_at=datetime.utcnow()
        )
        
        # Cache result for Monte Carlo
        _backtest_cache[backtest_id] = result
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return BacktestResult(
            backtest_id=backtest_id,
            status=BacktestStatus.FAILED,
            strategy_name=request.strategy_type.value if request.strategy_type else "unknown",
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            final_capital=request.initial_capital,
            error=str(e)
        )


@router.get(
    "/results/{backtest_id}",
    response_model=BacktestResult,
    summary="Get backtest result",
    description="Get results of a completed backtest."
)
async def get_backtest_result(
    backtest_id: str = Path(...)
) -> BacktestResult:
    """
    Get results of a backtest by ID.
    """
    if backtest_id in _backtest_cache:
        return _backtest_cache[backtest_id]
    
    raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")


@router.get(
    "/strategies",
    response_model=StrategiesResponse,
    summary="List strategies",
    description="Get available backtesting strategies."
)
async def list_strategies(
    strategy_type: Optional[StrategyType] = Query(None)
) -> StrategiesResponse:
    """
    List available strategies for backtesting.
    Uses real strategy registry.
    """
    strategies = []
    
    # Try to get from backtest strategies module
    bt_strategies = _get_backtest_strategies()
    if bt_strategies:
        for strat_id in bt_strategies.list_strategies():
            strat_class = bt_strategies.STRATEGIES.get(strat_id)
            if strat_class:
                # Map to strategy type
                if "momentum" in strat_id.lower():
                    st_type = StrategyType.MOMENTUM
                elif "rsi" in strat_id.lower() or "bollinger" in strat_id.lower():
                    st_type = StrategyType.MEAN_REVERSION
                elif "breakout" in strat_id.lower():
                    st_type = StrategyType.BREAKOUT
                elif "trend" in strat_id.lower():
                    st_type = StrategyType.TREND_FOLLOWING
                else:
                    st_type = StrategyType.CUSTOM
                
                strategies.append(Strategy(
                    id=f"strat-{strat_id}",
                    name=strat_id.replace("_", " ").title(),
                    description=f"Built-in {strat_id.replace('_', ' ')} strategy",
                    strategy_type=st_type,
                    parameters={},
                    parameter_schema={},
                    default_symbols=["SPY", "QQQ"],
                    created_at=datetime(2024, 1, 1)
                ))
    
    # Also try main strategies package
    list_strats_fn, registry = _get_strategy_registry()
    if list_strats_fn:
        try:
            for strat_info in list_strats_fn():
                strat_id = strat_info.get('id', strat_info.get('name', 'unknown'))
                
                # Map to strategy type
                if "momentum" in strat_id.lower():
                    st_type = StrategyType.MOMENTUM
                elif "reversion" in strat_id.lower() or "rsi" in strat_id.lower():
                    st_type = StrategyType.MEAN_REVERSION
                elif "pairs" in strat_id.lower():
                    st_type = StrategyType.PAIRS
                else:
                    st_type = StrategyType.CUSTOM
                
                strategies.append(Strategy(
                    id=f"strat-{strat_id}",
                    name=strat_info.get('name', strat_id.replace("_", " ").title()),
                    description=strat_info.get('description', f"Strategy: {strat_id}"),
                    strategy_type=st_type,
                    parameters={},
                    parameter_schema={},
                    default_symbols=["SPY"],
                    created_at=datetime(2024, 1, 1)
                ))
        except Exception as e:
            logger.warning(f"Failed to list strategies from registry: {e}")
    
    # Add fallback strategies if none found
    if not strategies:
        strategies = [
            Strategy(
                id="strat-momentum-001",
                name="Momentum Classic",
                description="Classic momentum strategy using RSI and price breakouts",
                strategy_type=StrategyType.MOMENTUM,
                parameters={"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
                parameter_schema={
                    "rsi_period": {"type": "int", "min": 5, "max": 50},
                    "rsi_oversold": {"type": "int", "min": 10, "max": 40},
                    "rsi_overbought": {"type": "int", "min": 60, "max": 90},
                },
                default_symbols=["SPY", "QQQ"],
                created_at=datetime(2024, 6, 1)
            ),
            Strategy(
                id="strat-meanrev-001",
                name="Mean Reversion RSI",
                description="Mean reversion strategy buying oversold conditions",
                strategy_type=StrategyType.MEAN_REVERSION,
                parameters={"lookback": 20, "entry_zscore": -2, "exit_zscore": 0},
                parameter_schema={
                    "lookback": {"type": "int", "min": 10, "max": 100},
                    "entry_zscore": {"type": "float", "min": -3, "max": -1},
                    "exit_zscore": {"type": "float", "min": -1, "max": 1},
                },
                default_symbols=["SPY"],
                created_at=datetime(2024, 6, 15)
            ),
            Strategy(
                id="strat-trend-001",
                name="Trend Following MA",
                description="Trend following using moving average crossovers",
                strategy_type=StrategyType.TREND_FOLLOWING,
                parameters={"fast_ma": 20, "slow_ma": 50, "atr_multiplier": 2.0},
                parameter_schema={
                    "fast_ma": {"type": "int", "min": 5, "max": 50},
                    "slow_ma": {"type": "int", "min": 20, "max": 200},
                    "atr_multiplier": {"type": "float", "min": 1.0, "max": 5.0},
                },
                default_symbols=["SPY", "QQQ", "IWM"],
                created_at=datetime(2024, 7, 1)
            ),
            Strategy(
                id="strat-ml-ensemble-001",
                name="ML Ensemble (XGB + LGB + NN + SVM)",
                description="BEAST ML ensemble combining XGBoost, LightGBM, Neural Network, and SVM for signal generation",
                strategy_type=StrategyType.ML_ENSEMBLE,
                parameters={"target_horizon": 5, "confidence_threshold": 0.65},
                parameter_schema={
                    "target_horizon": {"type": "int", "min": 1, "max": 20},
                    "confidence_threshold": {"type": "float", "min": 0.5, "max": 0.9},
                },
                default_symbols=["SPY", "QQQ"],
                created_at=datetime(2024, 8, 1)
            ),
            Strategy(
                id="strat-svm-001",
                name="SVM Signal Classifier",
                description="Support Vector Machine with RBF kernel for BUY/SELL/HOLD classification using 100+ technical features",
                strategy_type=StrategyType.SVM,
                parameters={"C": 10.0, "kernel": "rbf", "top_k_features": 40},
                parameter_schema={
                    "C": {"type": "float", "min": 0.1, "max": 100.0},
                    "kernel": {"type": "str", "values": ["rbf", "poly", "linear"]},
                    "top_k_features": {"type": "int", "min": 10, "max": 100},
                },
                default_symbols=["SPY"],
                created_at=datetime(2024, 8, 15)
            ),
        ]
    
    # Filter by type if specified
    if strategy_type:
        strategies = [s for s in strategies if s.strategy_type == strategy_type]
    
    return StrategiesResponse(
        strategies=strategies,
        total=len(strategies)
    )


@router.get(
    "/strategies/{strategy_id}",
    response_model=Strategy,
    summary="Get strategy",
    description="Get details of a specific strategy."
)
async def get_strategy(
    strategy_id: str = Path(...)
) -> Strategy:
    """
    Get strategy details by ID.
    """
    # Get all strategies and find the one
    all_strategies = await list_strategies()
    
    for strat in all_strategies.strategies:
        if strat.id == strategy_id:
            return strat
    
    raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResult,
    summary="Monte Carlo simulation",
    description="Run Monte Carlo simulation on backtest results."
)
async def run_monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    """
    Run Monte Carlo simulation to assess strategy robustness.
    Uses real trade data from cached backtest.
    """
    # Get cached backtest result
    if request.backtest_id not in _backtest_cache:
        raise HTTPException(status_code=404, detail=f"Backtest {request.backtest_id} not found")
    
    backtest = _backtest_cache[request.backtest_id]
    
    # Extract trade returns
    trade_returns = []
    for trade in backtest.trades:
        trade_returns.append(trade.pnl_percent / 100)  # Convert to decimal
    
    if not trade_returns:
        raise HTTPException(status_code=400, detail="Backtest has no trades for simulation")
    
    trade_returns = np.array(trade_returns)
    initial_capital = backtest.initial_capital
    
    # Run Monte Carlo simulations
    n_simulations = min(request.num_simulations, 10000)
    n_trades = len(trade_returns)
    
    final_equities = []
    max_drawdowns = []
    
    np.random.seed(42)  # For reproducibility
    
    for _ in range(n_simulations):
        if request.randomize_order:
            # Shuffle trade order
            sampled_returns = np.random.permutation(trade_returns)
        elif request.randomize_returns:
            # Sample from return distribution
            sampled_returns = np.random.choice(trade_returns, size=n_trades, replace=True)
        else:
            sampled_returns = trade_returns
        
        # Build equity curve
        equity = [initial_capital]
        for ret in sampled_returns:
            equity.append(equity[-1] * (1 + ret))
        
        final_equities.append(equity[-1])
        
        # Calculate max drawdown
        equity_arr = np.array(equity)
        peak = np.maximum.accumulate(equity_arr)
        dd = (peak - equity_arr) / peak
        max_drawdowns.append(np.max(dd))
    
    final_equities = np.array(final_equities)
    max_drawdowns = np.array(max_drawdowns)
    
    # Calculate returns
    total_returns = (final_equities - initial_capital) / initial_capital
    
    # VaR and CVaR
    var_95 = np.percentile(total_returns, 5)
    var_99 = np.percentile(total_returns, 1)
    cvar_95 = np.mean(total_returns[total_returns <= var_95])
    cvar_99 = np.mean(total_returns[total_returns <= var_99])
    
    # Probability of ruin (>50% drawdown)
    prob_ruin = np.mean(max_drawdowns > 0.5)
    
    return MonteCarloResult(
        simulation_id=str(uuid.uuid4())[:8],
        backtest_id=request.backtest_id,
        num_simulations=n_simulations,
        median_return=round(float(np.median(total_returns)) * 100, 2),
        mean_return=round(float(np.mean(total_returns)) * 100, 2),
        std_return=round(float(np.std(total_returns)) * 100, 2),
        var_95=round(float(var_95) * 100, 2),
        var_99=round(float(var_99) * 100, 2),
        cvar_95=round(float(cvar_95) * 100, 2),
        cvar_99=round(float(cvar_99) * 100, 2),
        max_drawdown_median=round(float(np.median(max_drawdowns)) * 100, 2),
        max_drawdown_95=round(float(np.percentile(max_drawdowns, 95)) * 100, 2),
        probability_of_profit=round(float(np.mean(total_returns > 0)), 3),
        probability_of_ruin=round(float(prob_ruin), 3),
        percentiles={
            "5th": round(float(np.percentile(total_returns, 5)) * 100, 2),
            "25th": round(float(np.percentile(total_returns, 25)) * 100, 2),
            "50th": round(float(np.percentile(total_returns, 50)) * 100, 2),
            "75th": round(float(np.percentile(total_returns, 75)) * 100, 2),
            "95th": round(float(np.percentile(total_returns, 95)) * 100, 2)
        }
    )


@router.post(
    "/optimize",
    response_model=OptimizationResult,
    summary="Optimize strategy",
    description="Optimize strategy parameters."
)
async def optimize_strategy(request: OptimizationRequest) -> OptimizationResult:
    """
    Run parameter optimization for a strategy.
    """
    optimization_id = str(uuid.uuid4())[:8]
    
    # Parse strategy name from ID
    strategy_name = request.strategy_id.split("-")[-1] if "-" in request.strategy_id else request.strategy_id
    
    # Fetch data
    data = _fetch_historical_data(request.symbols, request.start_date, request.end_date)
    if not data:
        raise HTTPException(status_code=400, detail="No data available for optimization")
    
    # Simple grid search optimization
    best_params = {}
    best_metric = float('-inf')
    iterations_run = 0
    param_sensitivity = {}
    
    # Generate parameter combinations
    param_combinations = [{}]
    for param_name, param_range in request.parameter_ranges.items():
        new_combinations = []
        values = param_range.get('values', [])
        if not values:
            min_val = param_range.get('min', 0)
            max_val = param_range.get('max', 100)
            step = param_range.get('step', (max_val - min_val) / 5)
            values = list(np.arange(min_val, max_val + step, step))[:10]
        
        for combo in param_combinations:
            for val in values:
                new_combo = combo.copy()
                new_combo[param_name] = val
                new_combinations.append(new_combo)
        param_combinations = new_combinations
    
    # Limit iterations
    param_combinations = param_combinations[:request.num_iterations]
    
    # Track param performance for sensitivity
    param_performance = {p: [] for p in request.parameter_ranges.keys()}
    
    for params in param_combinations:
        try:
            trades, equity_curve, final_capital = _run_strategy_backtest(
                strategy_name=strategy_name,
                data=data,
                initial_capital=100000,
                commission=0.001,
                slippage=0.001,
                parameters=params
            )
            
            metrics = _calculate_metrics(
                trades, equity_curve, 100000, final_capital,
                request.start_date, request.end_date
            )
            
            # Get target metric
            metric_value = getattr(metrics, request.optimization_target, 0)
            
            if metric_value > best_metric:
                best_metric = metric_value
                best_params = params
            
            # Track for sensitivity
            for p, v in params.items():
                param_performance[p].append((v, metric_value))
            
            iterations_run += 1
            
        except Exception as e:
            logger.warning(f"Optimization iteration failed: {e}")
            continue
    
    # Calculate parameter sensitivity
    for param_name, perf_data in param_performance.items():
        if len(perf_data) > 1:
            values = [p[0] for p in perf_data]
            metrics = [p[1] for p in perf_data]
            if np.std(values) > 0 and np.std(metrics) > 0:
                corr = np.corrcoef(values, metrics)[0, 1]
                param_sensitivity[param_name] = round(abs(corr), 3) if not np.isnan(corr) else 0
            else:
                param_sensitivity[param_name] = 0
    
    return OptimizationResult(
        optimization_id=optimization_id,
        strategy_id=request.strategy_id,
        best_parameters=best_params,
        best_metric_value=round(best_metric, 4),
        optimization_target=request.optimization_target,
        iterations_run=iterations_run,
        parameter_sensitivity=param_sensitivity
    )


@router.get(
    "/history",
    summary="Backtest history",
    description="Get history of backtest runs."
)
async def get_backtest_history(
    strategy_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
) -> dict:
    """
    Get history of backtest runs from cache.
    """
    backtests = list(_backtest_cache.values())
    
    # Filter by strategy
    if strategy_id:
        backtests = [b for b in backtests if b.strategy_name in strategy_id or strategy_id in b.strategy_name]
    
    # Sort by creation time
    backtests.sort(key=lambda b: b.created_at, reverse=True)
    
    # Limit results
    backtests = backtests[:limit]
    
    return {
        "backtests": [
            {
                "backtest_id": b.backtest_id,
                "strategy_name": b.strategy_name,
                "symbols": b.symbols,
                "sharpe_ratio": b.metrics.sharpe_ratio if b.metrics else 0,
                "total_return_percent": b.metrics.total_return_percent if b.metrics else 0,
                "created_at": b.created_at.isoformat()
            }
            for b in backtests
        ],
        "total": len(backtests)
    }
