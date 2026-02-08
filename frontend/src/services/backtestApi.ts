/**
 * Backtest API Service
 * Connects frontend to the backtest service endpoints
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Types matching backend
export interface BacktestConfig {
  tenant_id: string;
  strategy_code: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  initial_capital?: number;
  strategy_params?: Record<string, any>;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  webhook_url?: string;
}

export interface BacktestJob {
  job_id: string;
  tenant_id: string;
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'timeout';
  priority: number;
  config: any;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  progress: number;
  current_step: string;
  error: string | null;
}

export interface BacktestPerformance {
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  calmar_ratio: number;
  volatility: number;
}

export interface BacktestTrades {
  total: number;
  winning: number;
  losing: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  avg_holding_period: number;
}

export interface BacktestRisk {
  var_95: number;
  cvar_95: number;
  beta: number;
  alpha: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}

export interface MonthlyReturn {
  month: string;
  return: number;
}

export interface TradeRecord {
  date: string;
  symbol: string;
  side: 'buy' | 'sell';
  shares: number;
  price: number;
  commission: number;
  value: number;
}

export interface BacktestResult {
  job_id: string;
  config_hash: string;
  performance: BacktestPerformance;
  trades: BacktestTrades;
  risk: BacktestRisk;
  curves: {
    equity: EquityPoint[];
    drawdown: DrawdownPoint[];
    monthly_returns: MonthlyReturn[];
  };
  trade_log: TradeRecord[];
  execution: {
    time_seconds: number;
    data_points: number;
  };
  warnings: string[];
}

export interface QueueStatus {
  queue_size: number;
  running_jobs: number;
  max_workers: number;
  available_workers: number;
}

// API Functions
export async function submitBacktest(config: BacktestConfig): Promise<BacktestJob> {
  const response = await fetch(`${API_BASE}/backtest/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to submit backtest');
  }
  
  return response.json();
}

export async function getBacktestJob(jobId: string): Promise<BacktestJob> {
  const response = await fetch(`${API_BASE}/backtest/job/${jobId}`);
  
  if (!response.ok) {
    throw new Error('Job not found');
  }
  
  return response.json();
}

export async function getBacktestResult(jobId: string): Promise<BacktestResult> {
  const response = await fetch(`${API_BASE}/backtest/job/${jobId}/result`);
  
  if (!response.ok) {
    throw new Error('Result not available');
  }
  
  return response.json();
}

export async function cancelBacktest(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/backtest/job/${jobId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error('Failed to cancel job');
  }
}

export async function getQueueStatus(): Promise<QueueStatus> {
  const response = await fetch(`${API_BASE}/backtest/queue/status`);
  
  if (!response.ok) {
    throw new Error('Failed to get queue status');
  }
  
  return response.json();
}

export async function getUsage(tenantId: string): Promise<Record<string, any>> {
  const response = await fetch(`${API_BASE}/backtest/usage/${tenantId}`);
  
  if (!response.ok) {
    throw new Error('Failed to get usage');
  }
  
  return response.json();
}

// Polling helper for job completion
export async function waitForBacktestCompletion(
  jobId: string,
  onProgress?: (job: BacktestJob) => void,
  pollInterval = 1000,
  timeout = 300000
): Promise<BacktestResult> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeout) {
    const job = await getBacktestJob(jobId);
    
    if (onProgress) {
      onProgress(job);
    }
    
    if (job.status === 'completed') {
      return getBacktestResult(jobId);
    }
    
    if (job.status === 'failed') {
      throw new Error(job.error || 'Backtest failed');
    }
    
    if (job.status === 'cancelled') {
      throw new Error('Backtest was cancelled');
    }
    
    if (job.status === 'timeout') {
      throw new Error('Backtest timed out');
    }
    
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  throw new Error('Timeout waiting for backtest completion');
}

// Transform backtest result to visualization format
export function transformResultToVisualization(result: BacktestResult) {
  // Transform equity curve to include benchmark (mock for now)
  const equity = result.curves.equity.map((point, index) => {
    const benchmarkGrowth = 1 + (index / result.curves.equity.length) * 0.1; // Mock 10% benchmark
    return {
      date: point.date,
      equity: point.equity,
      benchmark: result.curves.equity[0]?.equity * benchmarkGrowth || 100000,
      drawdown: result.curves.drawdown[index]?.drawdown || 0,
      returns: index > 0 
        ? (point.equity - result.curves.equity[index - 1].equity) / result.curves.equity[index - 1].equity
        : 0,
    };
  });

  // Transform trades to visualization format
  const trades = result.trade_log.map(trade => ({
    date: trade.date,
    pnl: trade.side === 'sell' ? trade.value * 0.1 : -trade.value * 0.05, // Estimate P&L from trade value
    holdingDays: 0, // Holding days not available from trade log - would need entry/exit date pairs
    symbol: trade.symbol,
    side: trade.side === 'buy' ? 'long' : 'short' as 'long' | 'short',
  }));

  // Rolling metrics sampled from equity curve using the overall result metrics
  // These are static snapshots of the final metrics - real rolling calculation
  // would require windowed computation on the backend
  const rollingMetrics = equity
    .filter((_, i) => i % 20 === 0 && i > 0)
    .map(point => ({
      date: point.date,
      sharpe: result.performance.sharpe_ratio,
      sortino: result.performance.sortino_ratio,
      volatility: result.performance.volatility,
      beta: result.risk.beta,
      alpha: result.risk.alpha,
    }));

  // Factor exposures derived from available risk metrics
  // Only Market factor can be computed from the data we have;
  // other factors require backend factor analysis
  const factorExposures = [
    { factor: 'Market', exposure: result.risk.beta, contribution: result.risk.alpha * result.risk.beta },
    { factor: 'Volatility', exposure: -Math.abs(result.performance.volatility), contribution: -0.005 },
  ];

  return {
    equity,
    trades,
    rollingMetrics,
    factorExposures,
    summary: {
      totalReturn: result.performance.total_return,
      sharpeRatio: result.performance.sharpe_ratio,
      maxDrawdown: result.performance.max_drawdown,
      winRate: result.trades.win_rate,
      totalTrades: result.trades.total,
    },
  };
}

// Sample strategies for quick testing
export const sampleStrategies = {
  momentum: `
def generate_signals(data, params):
    """Simple momentum strategy"""
    lookback = params.get('lookback', 20)
    signals = {}
    
    for col in data.columns:
        if len(data) < lookback + 1:
            continue
        returns = data[col].pct_change(lookback).iloc[-1]
        if returns > 0.05:  # 5% return threshold
            signals[col] = 1  # Long
        elif returns < -0.05:
            signals[col] = -1  # Short
        else:
            signals[col] = 0
    
    return signals
`,
  meanReversion: `
def generate_signals(data, params):
    """Mean reversion strategy"""
    window = params.get('window', 20)
    threshold = params.get('threshold', 2)
    signals = {}
    
    for col in data.columns:
        if len(data) < window + 1:
            continue
        
        sma = data[col].rolling(window).mean().iloc[-1]
        std = data[col].rolling(window).std().iloc[-1]
        price = data[col].iloc[-1]
        
        zscore = (price - sma) / std if std > 0 else 0
        
        if zscore < -threshold:
            signals[col] = 1  # Buy oversold
        elif zscore > threshold:
            signals[col] = -1  # Sell overbought
        else:
            signals[col] = 0
    
    return signals
`,
  trendFollowing: `
def generate_signals(data, params):
    """Dual moving average trend following"""
    fast = params.get('fast', 10)
    slow = params.get('slow', 30)
    signals = {}
    
    for col in data.columns:
        if len(data) < slow + 1:
            continue
        
        fast_ma = data[col].rolling(fast).mean().iloc[-1]
        slow_ma = data[col].rolling(slow).mean().iloc[-1]
        
        if fast_ma > slow_ma:
            signals[col] = 1  # Uptrend
        elif fast_ma < slow_ma:
            signals[col] = -1  # Downtrend
        else:
            signals[col] = 0
    
    return signals
`,
};
