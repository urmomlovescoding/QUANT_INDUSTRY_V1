/**
 * Backtest Dashboard Component
 * QUANT_INDUSTRY_V1
 * 
 * Interactive backtesting interface with performance visualization
 */

import React, { useState, useCallback } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
} from 'recharts';

// Types
interface BacktestConfig {
  strategyId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  symbols: string[];
  parameters: Record<string, any>;
  slippageBps: number;
  commissionPerShare: number;
}

interface BacktestResult {
  id: string;
  status: 'running' | 'completed' | 'failed';
  config: BacktestConfig;
  metrics: PerformanceMetrics;
  equity: EquityPoint[];
  trades: Trade[];
  drawdowns: DrawdownPoint[];
  monthlyReturns: MonthlyReturn[];
  positionHistory: PositionSnapshot[];
}

interface PerformanceMetrics {
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  sortinoRatio: number;
  calmarRatio: number;
  maxDrawdown: number;
  maxDrawdownDuration: number;
  winRate: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  totalTrades: number;
  avgHoldingPeriod: number;
  beta: number;
  alpha: number;
  informationRatio: number;
  volatility: number;
}

interface EquityPoint {
  date: string;
  equity: number;
  benchmark: number;
  drawdown: number;
}

interface Trade {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  entryDate: string;
  entryPrice: number;
  exitDate: string;
  exitPrice: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  holdingDays: number;
}

interface DrawdownPoint {
  date: string;
  drawdown: number;
  duration: number;
}

interface MonthlyReturn {
  year: number;
  month: number;
  return: number;
}

interface PositionSnapshot {
  date: string;
  positions: Record<string, number>;
  exposure: number;
}

// Metric Card Component
const MetricCard: React.FC<{
  label: string;
  value: string | number;
  change?: number;
  format?: 'percent' | 'currency' | 'number' | 'ratio';
  highlight?: 'positive' | 'negative' | 'neutral';
}> = ({ label, value, change, format = 'number', highlight }) => {
  const formatValue = (v: string | number): string => {
    if (typeof v === 'string') return v;
    switch (format) {
      case 'percent':
        return `${(v * 100).toFixed(2)}%`;
      case 'currency':
        return `$${v.toLocaleString()}`;
      case 'ratio':
        return v.toFixed(2);
      default:
        return v.toLocaleString();
    }
  };

  const getHighlightColor = () => {
    if (highlight === 'positive') return 'text-green-400';
    if (highlight === 'negative') return 'text-red-400';
    return 'text-gray-200';
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-gray-400 text-sm">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${getHighlightColor()}`}>
        {formatValue(value)}
      </div>
      {change !== undefined && (
        <div className={`text-sm mt-1 ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {change >= 0 ? '↑' : '↓'} {Math.abs(change * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
};

// Strategy Selector
const StrategySelector: React.FC<{
  strategies: Array<{ id: string; name: string; description: string }>;
  selected: string;
  onSelect: (id: string) => void;
}> = ({ strategies, selected, onSelect }) => (
  <div className="bg-gray-800 rounded-lg p-4">
    <label className="block text-gray-400 text-sm mb-2">Strategy</label>
    <select
      value={selected}
      onChange={(e) => onSelect(e.target.value)}
      className="w-full bg-gray-700 text-white rounded px-3 py-2 focus:ring-2 focus:ring-blue-500"
    >
      {strategies.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
        </option>
      ))}
    </select>
    {selected && (
      <p className="text-gray-500 text-xs mt-2">
        {strategies.find((s) => s.id === selected)?.description}
      </p>
    )}
  </div>
);

// Parameter Editor
const ParameterEditor: React.FC<{
  parameters: Record<string, { value: any; type: string; min?: number; max?: number; options?: string[] }>;
  onChange: (params: Record<string, any>) => void;
}> = ({ parameters, onChange }) => {
  const handleChange = (key: string, value: any) => {
    const newParams = { ...parameters };
    newParams[key] = { ...newParams[key], value };
    onChange(Object.fromEntries(Object.entries(newParams).map(([k, v]) => [k, v.value])));
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-gray-300 font-medium mb-3">Parameters</h3>
      <div className="space-y-3">
        {Object.entries(parameters).map(([key, param]) => (
          <div key={key}>
            <label className="block text-gray-400 text-sm mb-1">
              {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
            </label>
            {param.type === 'number' && (
              <input
                type="number"
                value={param.value}
                min={param.min}
                max={param.max}
                onChange={(e) => handleChange(key, parseFloat(e.target.value))}
                className="w-full bg-gray-700 text-white rounded px-3 py-2"
              />
            )}
            {param.type === 'select' && (
              <select
                value={param.value}
                onChange={(e) => handleChange(key, e.target.value)}
                className="w-full bg-gray-700 text-white rounded px-3 py-2"
              >
                {param.options?.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            )}
            {param.type === 'boolean' && (
              <input
                type="checkbox"
                checked={param.value}
                onChange={(e) => handleChange(key, e.target.checked)}
                className="rounded bg-gray-700"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Equity Curve Chart
const EquityCurve: React.FC<{ data: EquityPoint[] }> = ({ data }) => (
  <div className="bg-gray-800 rounded-lg p-4">
    <h3 className="text-gray-300 font-medium mb-3">Equity Curve</h3>
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="date" tick={{ fill: '#9CA3AF' }} />
        <YAxis yAxisId="left" tick={{ fill: '#9CA3AF' }} />
        <YAxis yAxisId="right" orientation="right" tick={{ fill: '#9CA3AF' }} />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: 'none' }}
          labelStyle={{ color: '#9CA3AF' }}
        />
        <Legend />
        <Area
          yAxisId="right"
          type="monotone"
          dataKey="drawdown"
          fill="#EF444444"
          stroke="#EF4444"
          name="Drawdown"
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="equity"
          stroke="#10B981"
          dot={false}
          name="Strategy"
          strokeWidth={2}
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="benchmark"
          stroke="#6B7280"
          dot={false}
          name="Benchmark"
          strokeWidth={1}
          strokeDasharray="5 5"
        />
      </ComposedChart>
    </ResponsiveContainer>
  </div>
);

// Drawdown Chart
const DrawdownChart: React.FC<{ data: DrawdownPoint[] }> = ({ data }) => (
  <div className="bg-gray-800 rounded-lg p-4">
    <h3 className="text-gray-300 font-medium mb-3">Drawdown Analysis</h3>
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="date" tick={{ fill: '#9CA3AF' }} />
        <YAxis tick={{ fill: '#9CA3AF' }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: 'none' }}
          formatter={(value: number) => [`${(value * 100).toFixed(2)}%`, 'Drawdown']}
        />
        <Area type="monotone" dataKey="drawdown" fill="#EF4444" stroke="#DC2626" />
        <ReferenceLine y={-0.1} stroke="#FBBF24" strokeDasharray="3 3" label="10%" />
        <ReferenceLine y={-0.2} stroke="#F87171" strokeDasharray="3 3" label="20%" />
      </AreaChart>
    </ResponsiveContainer>
  </div>
);

// Monthly Returns Heatmap
const MonthlyReturnsHeatmap: React.FC<{ data: MonthlyReturn[] }> = ({ data }) => {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const years = [...new Set(data.map((d) => d.year))].sort();

  const getColor = (ret: number) => {
    if (ret > 0.05) return 'bg-green-500';
    if (ret > 0.02) return 'bg-green-400';
    if (ret > 0) return 'bg-green-300';
    if (ret > -0.02) return 'bg-red-300';
    if (ret > -0.05) return 'bg-red-400';
    return 'bg-red-500';
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-gray-300 font-medium mb-3">Monthly Returns</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-gray-400 p-1">Year</th>
              {months.map((m) => (
                <th key={m} className="text-gray-400 p-1">
                  {m}
                </th>
              ))}
              <th className="text-gray-400 p-1">YTD</th>
            </tr>
          </thead>
          <tbody>
            {years.map((year) => {
              const yearData = data.filter((d) => d.year === year);
              const ytd = yearData.reduce((acc, d) => acc * (1 + d.return), 1) - 1;
              return (
                <tr key={year}>
                  <td className="text-gray-300 p-1 font-medium">{year}</td>
                  {months.map((_, i) => {
                    const monthData = yearData.find((d) => d.month === i + 1);
                    return (
                      <td key={i} className="p-1">
                        {monthData ? (
                          <div
                            className={`${getColor(monthData.return)} rounded px-2 py-1 text-center text-white text-xs`}
                          >
                            {(monthData.return * 100).toFixed(1)}%
                          </div>
                        ) : (
                          <div className="bg-gray-700 rounded px-2 py-1 text-center text-gray-500 text-xs">
                            -
                          </div>
                        )}
                      </td>
                    );
                  })}
                  <td className="p-1">
                    <div
                      className={`${getColor(ytd)} rounded px-2 py-1 text-center text-white text-xs font-bold`}
                    >
                      {(ytd * 100).toFixed(1)}%
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Trade List
const TradeList: React.FC<{ trades: Trade[] }> = ({ trades }) => (
  <div className="bg-gray-800 rounded-lg p-4">
    <h3 className="text-gray-300 font-medium mb-3">Recent Trades</h3>
    <div className="overflow-x-auto max-h-64 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-gray-800">
          <tr>
            <th className="text-gray-400 text-left p-2">Symbol</th>
            <th className="text-gray-400 text-left p-2">Side</th>
            <th className="text-gray-400 text-left p-2">Entry</th>
            <th className="text-gray-400 text-left p-2">Exit</th>
            <th className="text-gray-400 text-right p-2">P&L</th>
            <th className="text-gray-400 text-right p-2">%</th>
            <th className="text-gray-400 text-right p-2">Days</th>
          </tr>
        </thead>
        <tbody>
          {trades.slice(0, 50).map((trade) => (
            <tr key={trade.id} className="border-t border-gray-700">
              <td className="text-white p-2 font-medium">{trade.symbol}</td>
              <td className={`p-2 ${trade.side === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                {trade.side.toUpperCase()}
              </td>
              <td className="text-gray-300 p-2">
                {trade.entryDate} @ ${trade.entryPrice.toFixed(2)}
              </td>
              <td className="text-gray-300 p-2">
                {trade.exitDate} @ ${trade.exitPrice.toFixed(2)}
              </td>
              <td className={`p-2 text-right ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${trade.pnl.toFixed(2)}
              </td>
              <td
                className={`p-2 text-right ${trade.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}
              >
                {(trade.pnlPercent * 100).toFixed(1)}%
              </td>
              <td className="text-gray-300 p-2 text-right">{trade.holdingDays}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

// Main Dashboard Component
export const BacktestDashboard: React.FC = () => {
  const [config, setConfig] = useState<BacktestConfig>({
    strategyId: 'momentum',
    startDate: '2020-01-01',
    endDate: '2024-01-01',
    initialCapital: 100000,
    symbols: ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META'],
    parameters: {},
    slippageBps: 5,
    commissionPerShare: 0.005,
  });

  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const strategies = [
    { id: 'momentum', name: 'Momentum Strategy', description: 'Cross-sectional momentum with lookback periods' },
    { id: 'mean_reversion', name: 'Mean Reversion', description: 'RSI-based mean reversion' },
    { id: 'trend_following', name: 'Trend Following', description: 'Moving average crossover' },
    { id: 'factor_model', name: 'Multi-Factor', description: 'Value, momentum, quality factors' },
  ];

  const parameters: Record<string, { value: any; type: string; min?: number; max?: number; options?: string[] }> = {
    lookback_period: { value: 21, type: 'number', min: 5, max: 252 },
    holding_period: { value: 21, type: 'number', min: 1, max: 63 },
    top_n: { value: 5, type: 'number', min: 1, max: 20 },
    rebalance_frequency: { value: 'weekly', type: 'select', options: ['daily', 'weekly', 'monthly'] },
  };

  const runBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error('Backtest failed');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [config]);

  // No mock data - result starts as null until a real backtest is run

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Backtest Dashboard</h1>
          <button
            onClick={runBacktest}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-6 py-2 rounded-lg font-medium transition"
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>

        {/* Config Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <StrategySelector
            strategies={strategies}
            selected={config.strategyId}
            onSelect={(id) => setConfig({ ...config, strategyId: id })}
          />
          <div className="bg-gray-800 rounded-lg p-4">
            <label className="block text-gray-400 text-sm mb-2">Date Range</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={config.startDate}
                onChange={(e) => setConfig({ ...config, startDate: e.target.value })}
                className="flex-1 bg-gray-700 text-white rounded px-3 py-2"
              />
              <input
                type="date"
                value={config.endDate}
                onChange={(e) => setConfig({ ...config, endDate: e.target.value })}
                className="flex-1 bg-gray-700 text-white rounded px-3 py-2"
              />
            </div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <label className="block text-gray-400 text-sm mb-2">Initial Capital</label>
            <input
              type="number"
              value={config.initialCapital}
              onChange={(e) => setConfig({ ...config, initialCapital: parseFloat(e.target.value) })}
              className="w-full bg-gray-700 text-white rounded px-3 py-2"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-900/50 border border-red-500 text-red-200 p-4 rounded-lg mb-6">
            {error}
          </div>
        )}

        {!result && !loading && !error && (
          <div className="flex flex-col items-center justify-center h-[400px] bg-gray-800 rounded-lg">
            <div className="text-gray-500 text-lg mb-2">Run a backtest to see results</div>
            <div className="text-gray-600 text-sm">Configure your strategy above and click "Run Backtest"</div>
          </div>
        )}

        {result && (
          <>
            {/* Key Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
              <MetricCard
                label="Total Return"
                value={result.metrics.totalReturn}
                format="percent"
                highlight={result.metrics.totalReturn >= 0 ? 'positive' : 'negative'}
              />
              <MetricCard
                label="Sharpe Ratio"
                value={result.metrics.sharpeRatio}
                format="ratio"
                highlight={result.metrics.sharpeRatio >= 1.5 ? 'positive' : 'neutral'}
              />
              <MetricCard
                label="Max Drawdown"
                value={result.metrics.maxDrawdown}
                format="percent"
                highlight="negative"
              />
              <MetricCard
                label="Win Rate"
                value={result.metrics.winRate}
                format="percent"
                highlight={result.metrics.winRate >= 0.5 ? 'positive' : 'negative'}
              />
              <MetricCard
                label="Profit Factor"
                value={result.metrics.profitFactor}
                format="ratio"
                highlight={result.metrics.profitFactor >= 1.5 ? 'positive' : 'neutral'}
              />
              <MetricCard
                label="Total Trades"
                value={result.metrics.totalTrades}
                format="number"
              />
            </div>

            {/* Charts */}
            <div className="space-y-6">
              <EquityCurve data={result.equity} />
              <DrawdownChart data={result.drawdowns} />
              <MonthlyReturnsHeatmap data={result.monthlyReturns} />
              <TradeList trades={result.trades} />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default BacktestDashboard;
