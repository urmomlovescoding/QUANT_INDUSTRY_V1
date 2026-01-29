"""
Database Initialization Script
Creates and seeds all required SQLite databases for QUANT_INDUSTRY_V1
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
import random
import json

BASE_DIR = Path(__file__).parent

def ensure_dir(path):
    """Ensure directory exists."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def init_trade_journal():
    """Initialize trade journal database with sample trades."""
    db_path = BASE_DIR / "backend" / "data" / "trade_journal.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id TEXT UNIQUE,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        quantity REAL NOT NULL,
        entry_price REAL,
        exit_price REAL,
        entry_time TEXT,
        exit_time TEXT,
        pnl REAL,
        pnl_percent REAL,
        strategy TEXT,
        regime TEXT,
        status TEXT DEFAULT 'open',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS trade_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id TEXT,
        decision_type TEXT,
        reason TEXT,
        confidence REAL,
        features TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Seed sample trades
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'AMD', 'META', 'AMZN']
    strategies = ['momentum', 'mean_reversion', 'breakout', 'trend_following']
    regimes = ['bull', 'bear', 'sideways', 'volatile']
    
    for i in range(50):
        trade_id = f"TRD-{datetime.now().strftime('%Y%m%d')}-{i:04d}"
        symbol = random.choice(symbols)
        side = random.choice(['long', 'short'])
        quantity = random.randint(10, 500)
        entry_price = random.uniform(100, 500)
        pnl_pct = random.uniform(-0.05, 0.08)
        exit_price = entry_price * (1 + pnl_pct) if side == 'long' else entry_price * (1 - pnl_pct)
        pnl = (exit_price - entry_price) * quantity if side == 'long' else (entry_price - exit_price) * quantity
        
        entry_time = (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat()
        exit_time = (datetime.fromisoformat(entry_time) + timedelta(hours=random.randint(1, 48))).isoformat()
        
        c.execute('''INSERT OR IGNORE INTO trades 
            (trade_id, symbol, side, quantity, entry_price, exit_price, entry_time, exit_time, pnl, pnl_percent, strategy, regime, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (trade_id, symbol, side, quantity, round(entry_price, 2), round(exit_price, 2), 
             entry_time, exit_time, round(pnl, 2), round(pnl_pct * 100, 2),
             random.choice(strategies), random.choice(regimes), 'closed'))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Trade journal: {db_path}")

def init_market_memory():
    """Initialize market memory database."""
    db_path = BASE_DIR / "backend" / "data" / "market_memory.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS market_episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_id TEXT UNIQUE,
        symbol TEXT,
        start_time TEXT,
        end_time TEXT,
        regime TEXT,
        pattern TEXT,
        outcome TEXT,
        pnl REAL,
        features TEXT,
        embedding TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS market_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_id TEXT UNIQUE,
        name TEXT,
        description TEXT,
        occurrences INTEGER DEFAULT 0,
        success_rate REAL,
        avg_return REAL,
        features TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Seed patterns
    patterns = [
        ('bull_flag', 'Bull Flag', 'Continuation pattern in uptrend', 45, 0.68, 2.3),
        ('bear_flag', 'Bear Flag', 'Continuation pattern in downtrend', 38, 0.62, -1.8),
        ('double_bottom', 'Double Bottom', 'Reversal pattern at support', 28, 0.72, 3.1),
        ('head_shoulders', 'Head and Shoulders', 'Reversal pattern at resistance', 22, 0.65, -2.5),
        ('breakout', 'Breakout', 'Price breaks key level with volume', 56, 0.58, 1.9),
        ('gap_fill', 'Gap Fill', 'Price fills previous gap', 41, 0.71, 1.2),
    ]
    
    for pid, name, desc, occ, sr, ret in patterns:
        c.execute('''INSERT OR IGNORE INTO market_patterns 
            (pattern_id, name, description, occurrences, success_rate, avg_return)
            VALUES (?, ?, ?, ?, ?, ?)''', (pid, name, desc, occ, sr, ret))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Market memory: {db_path}")

def init_portfolio():
    """Initialize portfolio database."""
    db_path = BASE_DIR / "backend" / "data" / "portfolio.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE,
        quantity REAL,
        avg_cost REAL,
        current_price REAL,
        market_value REAL,
        unrealized_pnl REAL,
        unrealized_pnl_pct REAL,
        side TEXT,
        opened_at TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        equity REAL,
        cash REAL,
        buying_power REAL,
        day_pnl REAL,
        day_pnl_pct REAL,
        total_pnl REAL,
        total_pnl_pct REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Seed positions
    positions = [
        ('AAPL', 100, 178.50, 'long'),
        ('MSFT', 50, 378.20, 'long'),
        ('NVDA', 25, 485.30, 'long'),
        ('GOOGL', 30, 142.80, 'long'),
    ]
    
    for symbol, qty, cost, side in positions:
        current = cost * random.uniform(0.95, 1.15)
        mv = qty * current
        pnl = (current - cost) * qty
        pnl_pct = ((current / cost) - 1) * 100
        
        c.execute('''INSERT OR REPLACE INTO positions 
            (symbol, quantity, avg_cost, current_price, market_value, unrealized_pnl, unrealized_pnl_pct, side, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (symbol, qty, cost, round(current, 2), round(mv, 2), round(pnl, 2), round(pnl_pct, 2), side, datetime.now().isoformat()))
    
    # Seed portfolio history
    equity = 100000
    for i in range(90):
        date = (datetime.now() - timedelta(days=90-i)).strftime('%Y-%m-%d')
        daily_return = random.uniform(-0.02, 0.025)
        equity *= (1 + daily_return)
        
        c.execute('''INSERT OR IGNORE INTO portfolio_history 
            (date, equity, cash, buying_power, day_pnl, day_pnl_pct, total_pnl, total_pnl_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (date, round(equity, 2), round(equity * 0.1, 2), round(equity * 0.5, 2),
             round(equity * daily_return, 2), round(daily_return * 100, 2),
             round(equity - 100000, 2), round((equity / 100000 - 1) * 100, 2)))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Portfolio: {db_path}")

def init_signals():
    """Initialize signals database."""
    db_path = BASE_DIR / "backend" / "data" / "signals.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT UNIQUE,
        symbol TEXT NOT NULL,
        signal_type TEXT,
        direction TEXT,
        strength REAL,
        confidence REAL,
        entry_price REAL,
        stop_loss REAL,
        take_profit REAL,
        timeframe TEXT,
        strategy TEXT,
        regime TEXT,
        features TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS signal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT,
        action TEXT,
        result TEXT,
        pnl REAL,
        notes TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Seed active signals
    symbols = ['SPY', 'QQQ', 'AAPL', 'NVDA', 'TSLA', 'AMD', 'META']
    strategies = ['momentum', 'breakout', 'mean_reversion', 'trend']
    
    for i in range(10):
        signal_id = f"SIG-{datetime.now().strftime('%Y%m%d')}-{i:04d}"
        symbol = random.choice(symbols)
        direction = random.choice(['long', 'short'])
        entry = random.uniform(100, 500)
        
        c.execute('''INSERT OR IGNORE INTO signals 
            (signal_id, symbol, signal_type, direction, strength, confidence, entry_price, stop_loss, take_profit, timeframe, strategy, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (signal_id, symbol, 'entry', direction, 
             round(random.uniform(0.6, 0.95), 2), round(random.uniform(0.5, 0.9), 2),
             round(entry, 2), round(entry * 0.97, 2), round(entry * 1.05, 2),
             random.choice(['5m', '15m', '1h', '4h']), random.choice(strategies), 'active'))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Signals: {db_path}")

def init_risk():
    """Initialize risk database."""
    db_path = BASE_DIR / "backend" / "data" / "risk.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS risk_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        var_95 REAL,
        var_99 REAL,
        cvar_95 REAL,
        max_drawdown REAL,
        current_drawdown REAL,
        sharpe_ratio REAL,
        sortino_ratio REAL,
        beta REAL,
        correlation_spy REAL,
        position_concentration REAL,
        sector_exposure TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS risk_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id TEXT UNIQUE,
        alert_type TEXT,
        severity TEXT,
        message TEXT,
        metric_name TEXT,
        metric_value REAL,
        threshold REAL,
        acknowledged INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Seed risk metrics
    for i in range(30):
        timestamp = (datetime.now() - timedelta(days=30-i)).isoformat()
        c.execute('''INSERT INTO risk_metrics 
            (timestamp, var_95, var_99, cvar_95, max_drawdown, current_drawdown, sharpe_ratio, sortino_ratio, beta, correlation_spy, position_concentration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (timestamp, 
             round(random.uniform(1.5, 3.5), 2),
             round(random.uniform(2.5, 5.0), 2),
             round(random.uniform(2.0, 4.0), 2),
             round(random.uniform(5, 15), 2),
             round(random.uniform(0, 8), 2),
             round(random.uniform(0.8, 2.5), 2),
             round(random.uniform(1.0, 3.0), 2),
             round(random.uniform(0.8, 1.3), 2),
             round(random.uniform(0.6, 0.95), 2),
             round(random.uniform(10, 40), 2)))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Risk metrics: {db_path}")

def init_backtest():
    """Initialize backtest results database."""
    db_path = BASE_DIR / "backend" / "data" / "backtest.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE,
        strategy_name TEXT,
        start_date TEXT,
        end_date TEXT,
        initial_capital REAL,
        final_capital REAL,
        total_return REAL,
        sharpe_ratio REAL,
        max_drawdown REAL,
        win_rate REAL,
        profit_factor REAL,
        total_trades INTEGER,
        parameters TEXT,
        status TEXT DEFAULT 'completed',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS backtest_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        symbol TEXT,
        side TEXT,
        entry_date TEXT,
        exit_date TEXT,
        entry_price REAL,
        exit_price REAL,
        quantity REAL,
        pnl REAL,
        pnl_percent REAL,
        holding_period INTEGER
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS backtest_equity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        date TEXT,
        equity REAL,
        drawdown REAL,
        returns REAL
    )''')
    
    # Seed backtest runs
    strategies = ['Momentum Alpha', 'Mean Reversion Pro', 'Breakout Hunter', 'Trend Master']
    
    for i, strat in enumerate(strategies):
        run_id = f"BT-{datetime.now().strftime('%Y%m%d')}-{i:04d}"
        initial = 100000
        total_return = random.uniform(-0.1, 0.4)
        final = initial * (1 + total_return)
        
        c.execute('''INSERT OR IGNORE INTO backtest_runs 
            (run_id, strategy_name, start_date, end_date, initial_capital, final_capital, total_return, sharpe_ratio, max_drawdown, win_rate, profit_factor, total_trades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (run_id, strat, '2024-01-01', '2024-12-31', initial, round(final, 2), 
             round(total_return * 100, 2), round(random.uniform(0.5, 2.5), 2),
             round(random.uniform(5, 20), 2), round(random.uniform(0.45, 0.65), 2),
             round(random.uniform(1.0, 2.0), 2), random.randint(50, 200)))
        
        # Add equity curve
        equity = initial
        for day in range(252):
            date = (datetime(2024, 1, 1) + timedelta(days=day)).strftime('%Y-%m-%d')
            daily_ret = random.uniform(-0.02, 0.025)
            equity *= (1 + daily_ret)
            peak = max(initial, equity)
            dd = (peak - equity) / peak * 100
            
            c.execute('''INSERT INTO backtest_equity (run_id, date, equity, drawdown, returns)
                VALUES (?, ?, ?, ?, ?)''', (run_id, date, round(equity, 2), round(dd, 2), round(daily_ret * 100, 2)))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Backtest: {db_path}")

def init_feature_store():
    """Initialize feature store database."""
    db_path = BASE_DIR / "data" / "feature_store.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_id TEXT UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        data_type TEXT,
        category TEXT,
        update_frequency TEXT,
        source TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS feature_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_id TEXT,
        symbol TEXT,
        timestamp TEXT,
        value REAL,
        UNIQUE(feature_id, symbol, timestamp)
    )''')
    
    # Seed features
    features = [
        ('rsi_14', 'RSI 14', 'Relative Strength Index 14 period', 'float', 'momentum', '1m'),
        ('macd_signal', 'MACD Signal', 'MACD Signal Line', 'float', 'momentum', '1m'),
        ('bb_position', 'BB Position', 'Position within Bollinger Bands', 'float', 'volatility', '1m'),
        ('volume_ratio', 'Volume Ratio', 'Current vs average volume', 'float', 'volume', '1m'),
        ('atr_14', 'ATR 14', 'Average True Range 14 period', 'float', 'volatility', '1m'),
        ('regime', 'Market Regime', 'Current market regime classification', 'string', 'regime', '5m'),
        ('sentiment', 'News Sentiment', 'Aggregated news sentiment score', 'float', 'sentiment', '1h'),
        ('flow_score', 'Options Flow Score', 'Smart money flow indicator', 'float', 'flow', '5m'),
    ]
    
    for fid, name, desc, dtype, cat, freq in features:
        c.execute('''INSERT OR IGNORE INTO features 
            (feature_id, name, description, data_type, category, update_frequency, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', (fid, name, desc, dtype, cat, freq, 'computed'))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Feature store: {db_path}")

def init_compliance():
    """Initialize compliance database."""
    db_path = BASE_DIR / "data" / "compliance.db"
    ensure_dir(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS compliance_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id TEXT UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT,
        threshold REAL,
        operator TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS compliance_violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        violation_id TEXT UNIQUE,
        rule_id TEXT,
        severity TEXT,
        message TEXT,
        metric_value REAL,
        threshold REAL,
        resolved INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Seed rules
    rules = [
        ('max_position_size', 'Max Position Size', 'Maximum single position as % of portfolio', 'position', 10, '<='),
        ('max_daily_loss', 'Max Daily Loss', 'Maximum daily loss percentage', 'risk', 3, '<='),
        ('max_drawdown', 'Max Drawdown', 'Maximum portfolio drawdown', 'risk', 10, '<='),
        ('min_cash_reserve', 'Min Cash Reserve', 'Minimum cash reserve percentage', 'liquidity', 5, '>='),
        ('max_sector_exposure', 'Max Sector Exposure', 'Maximum exposure to single sector', 'concentration', 30, '<='),
        ('max_correlation', 'Max Position Correlation', 'Maximum correlation between positions', 'correlation', 0.7, '<='),
    ]
    
    for rid, name, desc, cat, thresh, op in rules:
        c.execute('''INSERT OR IGNORE INTO compliance_rules 
            (rule_id, name, description, category, threshold, operator)
            VALUES (?, ?, ?, ?, ?, ?)''', (rid, name, desc, cat, thresh, op))
    
    conn.commit()
    conn.close()
    print(f"âœ“ Compliance: {db_path}")

def main():
    """Initialize all databases."""
    print("=" * 50)
    print("QUANT_INDUSTRY_V1 Database Initialization")
    print("=" * 50)
    print()
    
    init_trade_journal()
    init_market_memory()
    init_portfolio()
    init_signals()
    init_risk()
    init_backtest()
    init_feature_store()
    init_compliance()
    
    print()
    print("=" * 50)
    print("All databases initialized successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()

