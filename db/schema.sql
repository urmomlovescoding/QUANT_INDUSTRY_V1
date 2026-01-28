-- QUANT_INDUSTRY_V1 SQLite Schema
-- Version: 1.0.0
-- Author: Institutional Quant Team
-- Description: SQLite-first storage layer for institutional-grade trading platform

-- Enable required pragmas
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Runs table: Track every execution run for reproducibility
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    start_ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_ts DATETIME,
    mode TEXT NOT NULL CHECK(mode IN ('backtest', 'paper', 'live', 'research')),
    git_hash TEXT,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed', 'cancelled')),
    metadata_json TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_run_id ON runs(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_start_ts ON runs(start_ts);
CREATE INDEX IF NOT EXISTS idx_runs_mode ON runs(mode);

-- ============================================================================
-- MARKET DATA TABLES
-- ============================================================================

-- Market bars: OHLCV data storage
CREATE TABLE IF NOT EXISTS market_bars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL CHECK(timeframe IN ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M')),
    ts DATETIME NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    vwap REAL,
    trade_count INTEGER,
    source TEXT NOT NULL CHECK(source IN ('alpaca', 'yahoo', 'polygon', 'manual')),
    is_adjusted INTEGER NOT NULL DEFAULT 1,
    quality_score REAL DEFAULT 1.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, ts, source)
);

CREATE INDEX IF NOT EXISTS idx_market_bars_symbol ON market_bars(symbol);
CREATE INDEX IF NOT EXISTS idx_market_bars_ts ON market_bars(ts);
CREATE INDEX IF NOT EXISTS idx_market_bars_symbol_timeframe ON market_bars(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_market_bars_symbol_ts ON market_bars(symbol, ts DESC);

-- Data quality events: Track data issues
CREATE TABLE IF NOT EXISTS data_quality_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    ts DATETIME NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('gap', 'outlier', 'stale', 'missing', 'corporate_action', 'reconciliation_failure')),
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'error', 'critical')),
    description TEXT,
    remediation TEXT,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_dq_events_symbol ON data_quality_events(symbol);
CREATE INDEX IF NOT EXISTS idx_dq_events_ts ON data_quality_events(ts);

-- ============================================================================
-- FEATURE STORE TABLES
-- ============================================================================

-- Feature definitions: Version-controlled feature specs
CREATE TABLE IF NOT EXISTS feature_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name TEXT UNIQUE NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    computation_code TEXT NOT NULL,
    dependencies_json TEXT,
    data_type TEXT NOT NULL CHECK(data_type IN ('float', 'int', 'bool', 'category')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feature_defs_name ON feature_definitions(feature_name);

-- Feature values: Computed feature storage
CREATE TABLE IF NOT EXISTS feature_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    ts DATETIME NOT NULL,
    feature_name TEXT NOT NULL,
    value REAL NOT NULL,
    features_hash TEXT NOT NULL,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feature_name) REFERENCES feature_definitions(feature_name),
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    UNIQUE(symbol, ts, feature_name, features_hash)
);

CREATE INDEX IF NOT EXISTS idx_feature_values_symbol ON feature_values(symbol);
CREATE INDEX IF NOT EXISTS idx_feature_values_ts ON feature_values(ts);
CREATE INDEX IF NOT EXISTS idx_feature_values_hash ON feature_values(features_hash);

-- ============================================================================
-- MODEL REGISTRY TABLES
-- ============================================================================

-- Models: Track all trained models
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT UNIQUE NOT NULL,
    model_type TEXT NOT NULL CHECK(model_type IN ('supervised', 'rl', 'ensemble', 'meta', 'rule_based')),
    version INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    description TEXT,
    dataset_hash TEXT NOT NULL,
    feature_hash TEXT NOT NULL,
    hyperparams_json TEXT NOT NULL,
    metrics_json TEXT,
    training_config_json TEXT,
    artifact_path TEXT,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate', 'staging', 'production', 'deprecated', 'failed')),
    promoted_at DATETIME,
    deprecated_at DATETIME,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_models_model_id ON models(model_id);
CREATE INDEX IF NOT EXISTS idx_models_type ON models(model_type);
CREATE INDEX IF NOT EXISTS idx_models_status ON models(status);

-- Model validation results: Track validation metrics
CREATE TABLE IF NOT EXISTS model_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    validation_type TEXT NOT NULL CHECK(validation_type IN ('oos_sharpe', 'max_drawdown', 'turnover', 'regime_stability', 'calibration')),
    threshold REAL NOT NULL,
    actual_value REAL NOT NULL,
    passed INTEGER NOT NULL,
    details_json TEXT,
    validated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id)
);

CREATE INDEX IF NOT EXISTS idx_model_validations_model ON model_validations(model_id);

-- ============================================================================
-- SIGNALS TABLES
-- ============================================================================

-- Signals: Trading signals generated by models
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    ts DATETIME NOT NULL,
    signal_type TEXT NOT NULL CHECK(signal_type IN ('entry_long', 'entry_short', 'exit', 'hold', 'scale_in', 'scale_out')),
    direction TEXT NOT NULL CHECK(direction IN ('long', 'short', 'flat')),
    strength REAL NOT NULL CHECK(strength >= -1.0 AND strength <= 1.0),
    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    features_hash TEXT NOT NULL,
    model_id TEXT NOT NULL,
    strategy_id TEXT,
    regime TEXT,
    explanation_json TEXT,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
CREATE INDEX IF NOT EXISTS idx_signals_model ON signals(model_id);
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_id);

-- ============================================================================
-- TRADING TABLES
-- ============================================================================

-- Orders: All order submissions
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    order_type TEXT NOT NULL CHECK(order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    qty REAL NOT NULL,
    limit_price REAL,
    stop_price REAL,
    time_in_force TEXT NOT NULL DEFAULT 'day' CHECK(time_in_force IN ('day', 'gtc', 'ioc', 'fok')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'submitted', 'accepted', 'partial', 'filled', 'cancelled', 'rejected', 'expired')),
    submitted_at DATETIME,
    filled_at DATETIME,
    cancelled_at DATETIME,
    signal_id INTEGER,
    strategy_id TEXT,
    model_id TEXT,
    run_id TEXT,
    broker_order_id TEXT,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id),
    FOREIGN KEY (model_id) REFERENCES models(model_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_submitted ON orders(submitted_at);

-- Trades: Executed fills
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    order_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    qty REAL NOT NULL,
    price REAL NOT NULL,
    commission REAL NOT NULL DEFAULT 0,
    slippage REAL,
    expected_price REAL,
    fill_status TEXT NOT NULL CHECK(fill_status IN ('full', 'partial')),
    executed_at DATETIME NOT NULL,
    strategy_id TEXT,
    model_id TEXT,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (model_id) REFERENCES models(model_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id);
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);

-- Positions: Current and historical positions
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    ts DATETIME NOT NULL,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    market_price REAL,
    unrealized_pnl REAL,
    realized_pnl REAL NOT NULL DEFAULT 0,
    cost_basis REAL NOT NULL,
    strategy_id TEXT,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_ts ON positions(ts);
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id);

-- Portfolio snapshots: Point-in-time portfolio state
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL,
    cash REAL NOT NULL,
    equity REAL NOT NULL,
    buying_power REAL NOT NULL,
    gross_exposure REAL NOT NULL,
    net_exposure REAL NOT NULL,
    positions_json TEXT NOT NULL,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_ts ON portfolio_snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_portfolio_run ON portfolio_snapshots(run_id);

-- ============================================================================
-- RISK MANAGEMENT TABLES
-- ============================================================================

-- Risk metrics: Track risk measurements over time
CREATE TABLE IF NOT EXISTS risk_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL,
    metric_type TEXT NOT NULL CHECK(metric_type IN ('var_95', 'var_99', 'cvar_95', 'cvar_99', 'max_drawdown', 'current_drawdown', 'sharpe', 'sortino', 'volatility', 'beta', 'correlation')),
    value REAL NOT NULL,
    lookback_days INTEGER,
    symbol TEXT,
    strategy_id TEXT,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_risk_metrics_ts ON risk_metrics(ts);
CREATE INDEX IF NOT EXISTS idx_risk_metrics_type ON risk_metrics(metric_type);

-- Risk limits: Configurable risk constraints
CREATE TABLE IF NOT EXISTS risk_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    limit_type TEXT NOT NULL CHECK(limit_type IN ('max_position_size', 'max_sector_exposure', 'max_gross_exposure', 'max_net_exposure', 'max_daily_loss', 'max_drawdown', 'min_cash', 'max_orders_per_minute', 'max_beta')),
    limit_value REAL NOT NULL,
    symbol TEXT,
    sector TEXT,
    strategy_id TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_limits_type ON risk_limits(limit_type);

-- Risk breaches: Track limit violations
CREATE TABLE IF NOT EXISTS risk_breaches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL,
    limit_id INTEGER NOT NULL,
    limit_type TEXT NOT NULL,
    limit_value REAL NOT NULL,
    actual_value REAL NOT NULL,
    action_taken TEXT NOT NULL CHECK(action_taken IN ('logged', 'warned', 'blocked', 'liquidated')),
    details_json TEXT,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (limit_id) REFERENCES risk_limits(id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_risk_breaches_ts ON risk_breaches(ts);
CREATE INDEX IF NOT EXISTS idx_risk_breaches_type ON risk_breaches(limit_type);

-- ============================================================================
-- STRATEGY GOVERNANCE TABLES
-- ============================================================================

-- Strategies: Strategy registry
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    strategy_type TEXT NOT NULL CHECK(strategy_type IN ('momentum', 'mean_reversion', 'trend_following', 'arbitrage', 'ml_based', 'hybrid')),
    config_json TEXT NOT NULL,
    required_data_json TEXT,
    failure_modes_json TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 1.0,
    max_allocation REAL NOT NULL DEFAULT 0.25,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_strategies_id ON strategies(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategies_active ON strategies(is_active);

-- Strategy performance: Track strategy outcomes
CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    ts DATETIME NOT NULL,
    period TEXT NOT NULL CHECK(period IN ('daily', 'weekly', 'monthly')),
    pnl REAL NOT NULL,
    sharpe REAL,
    sortino REAL,
    max_drawdown REAL,
    win_rate REAL,
    avg_win REAL,
    avg_loss REAL,
    trade_count INTEGER NOT NULL DEFAULT 0,
    run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_strat_perf_strategy ON strategy_performance(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strat_perf_ts ON strategy_performance(ts);

-- ============================================================================
-- AUDIT & LOGGING TABLES
-- ============================================================================

-- Audit log: Comprehensive audit trail
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor TEXT NOT NULL DEFAULT 'system',
    action TEXT NOT NULL CHECK(action IN ('create', 'read', 'update', 'delete', 'execute', 'approve', 'reject', 'enable', 'disable', 'login', 'logout', 'config_change', 'model_promote', 'model_deprecate', 'risk_override')),
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    details_json TEXT,
    ip_address TEXT,
    user_agent TEXT,
    run_id TEXT,
    correlation_id TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_log(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_log(correlation_id);

-- Errors: System error tracking
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subsystem TEXT NOT NULL CHECK(subsystem IN ('data', 'brain', 'execution', 'risk', 'ui', 'api', 'db', 'config', 'unknown')),
    severity TEXT NOT NULL CHECK(severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    error_code TEXT,
    message TEXT NOT NULL,
    stack_trace TEXT,
    context_json TEXT,
    run_id TEXT,
    correlation_id TEXT,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at DATETIME,
    resolution_notes TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors(ts);
CREATE INDEX IF NOT EXISTS idx_errors_subsystem ON errors(subsystem);
CREATE INDEX IF NOT EXISTS idx_errors_severity ON errors(severity);
CREATE INDEX IF NOT EXISTS idx_errors_resolved ON errors(resolved);

-- System health: Track system metrics
CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metric_type TEXT NOT NULL CHECK(metric_type IN ('api_latency', 'db_latency', 'model_inference_time', 'ui_render_time', 'memory_usage', 'cpu_usage', 'queue_depth', 'cache_hit_rate', 'data_freshness', 'error_rate')),
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    subsystem TEXT,
    run_id TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_health_ts ON system_health(ts);
CREATE INDEX IF NOT EXISTS idx_health_type ON system_health(metric_type);

-- ============================================================================
-- SELF-GRADING TABLES
-- ============================================================================

-- Self-grade scores: Nightly system assessment
CREATE TABLE IF NOT EXISTS self_grade_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    category TEXT NOT NULL CHECK(category IN ('data_freshness', 'model_drift', 'execution_quality', 'strategy_health', 'ui_performance', 'overall')),
    score REAL NOT NULL CHECK(score >= 0.0 AND score <= 100.0),
    details_json TEXT,
    issues_found INTEGER NOT NULL DEFAULT 0,
    run_id TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_grades_ts ON self_grade_scores(ts);
CREATE INDEX IF NOT EXISTS idx_grades_category ON self_grade_scores(category);

-- Remediation plans: Auto-generated fix suggestions
CREATE TABLE IF NOT EXISTS remediation_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_id INTEGER NOT NULL,
    priority INTEGER NOT NULL CHECK(priority >= 1 AND priority <= 10),
    issue_description TEXT NOT NULL,
    suggested_fix TEXT NOT NULL,
    estimated_impact REAL,
    auto_fixable INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'in_progress', 'completed', 'rejected')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grade_id) REFERENCES self_grade_scores(id)
);

CREATE INDEX IF NOT EXISTS idx_remediation_grade ON remediation_plans(grade_id);
CREATE INDEX IF NOT EXISTS idx_remediation_priority ON remediation_plans(priority);
CREATE INDEX IF NOT EXISTS idx_remediation_status ON remediation_plans(status);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active positions view
CREATE VIEW IF NOT EXISTS v_active_positions AS
SELECT
    p.*,
    mb.close as current_price,
    (mb.close - p.avg_price) * p.qty as current_unrealized_pnl
FROM positions p
LEFT JOIN (
    SELECT symbol, close, MAX(ts) as max_ts
    FROM market_bars
    WHERE timeframe = '1d'
    GROUP BY symbol
) mb ON p.symbol = mb.symbol
WHERE p.qty != 0
ORDER BY p.symbol;

-- Recent signals view
CREATE VIEW IF NOT EXISTS v_recent_signals AS
SELECT
    s.*,
    m.name as model_name,
    m.model_type
FROM signals s
JOIN models m ON s.model_id = m.model_id
WHERE s.ts >= datetime('now', '-1 day')
ORDER BY s.ts DESC;

-- Strategy leaderboard view
CREATE VIEW IF NOT EXISTS v_strategy_leaderboard AS
SELECT
    strategy_id,
    SUM(pnl) as total_pnl,
    AVG(sharpe) as avg_sharpe,
    MIN(max_drawdown) as worst_drawdown,
    AVG(win_rate) as avg_win_rate,
    SUM(trade_count) as total_trades
FROM strategy_performance
WHERE ts >= datetime('now', '-30 days')
GROUP BY strategy_id
ORDER BY total_pnl DESC;

-- Production models view
CREATE VIEW IF NOT EXISTS v_production_models AS
SELECT
    m.*,
    (SELECT COUNT(*) FROM signals s WHERE s.model_id = m.model_id AND s.ts >= datetime('now', '-1 day')) as signals_24h
FROM models m
WHERE m.status = 'production'
ORDER BY m.promoted_at DESC;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update timestamp trigger for runs
CREATE TRIGGER IF NOT EXISTS trg_runs_updated
AFTER UPDATE ON runs
BEGIN
    UPDATE runs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp trigger for models
CREATE TRIGGER IF NOT EXISTS trg_models_updated
AFTER UPDATE ON models
BEGIN
    UPDATE models SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp trigger for positions
CREATE TRIGGER IF NOT EXISTS trg_positions_updated
AFTER UPDATE ON positions
BEGIN
    UPDATE positions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp trigger for orders
CREATE TRIGGER IF NOT EXISTS trg_orders_updated
AFTER UPDATE ON orders
BEGIN
    UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp trigger for strategies
CREATE TRIGGER IF NOT EXISTS trg_strategies_updated
AFTER UPDATE ON strategies
BEGIN
    UPDATE strategies SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update timestamp trigger for risk_limits
CREATE TRIGGER IF NOT EXISTS trg_risk_limits_updated
AFTER UPDATE ON risk_limits
BEGIN
    UPDATE risk_limits SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Audit trigger for model status changes
CREATE TRIGGER IF NOT EXISTS trg_model_status_audit
AFTER UPDATE OF status ON models
WHEN OLD.status != NEW.status
BEGIN
    INSERT INTO audit_log (actor, action, object_type, object_id, old_value_json, new_value_json)
    VALUES (
        'system',
        CASE
            WHEN NEW.status = 'production' THEN 'model_promote'
            WHEN NEW.status = 'deprecated' THEN 'model_deprecate'
            ELSE 'update'
        END,
        'model',
        NEW.model_id,
        json_object('status', OLD.status),
        json_object('status', NEW.status)
    );
END;

-- Audit trigger for strategy activation
CREATE TRIGGER IF NOT EXISTS trg_strategy_activation_audit
AFTER UPDATE OF is_active ON strategies
WHEN OLD.is_active != NEW.is_active
BEGIN
    INSERT INTO audit_log (actor, action, object_type, object_id, old_value_json, new_value_json)
    VALUES (
        'system',
        CASE WHEN NEW.is_active = 1 THEN 'enable' ELSE 'disable' END,
        'strategy',
        NEW.strategy_id,
        json_object('is_active', OLD.is_active),
        json_object('is_active', NEW.is_active)
    );
END;
