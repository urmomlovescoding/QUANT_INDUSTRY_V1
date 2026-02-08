/**
 * Advanced Backtest Visualization Component
 * QUANT_INDUSTRY_V1 - P2 Task 16
 * 
 * Interactive and detailed performance visualizations using Recharts.
 * Features:
 * - Multi-timeframe equity curves
 * - Rolling performance metrics
 * - Distribution analysis
 * - Trade clustering
 * - Factor exposure charts
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  ComposedChart,
  Brush,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';

// =============================================================================
// TYPES
// =============================================================================

interface EquityPoint {
  date: string;
  equity: number;
  benchmark: number;
  drawdown: number;
  returns: number;
}

interface RollingMetric {
  date: string;
  sharpe: number;
  sortino: number;
  volatility: number;
  beta: number;
  alpha: number;
}

interface TradePoint {
  date: string;
  pnl: number;
  holdingDays: number;
  symbol: string;
  side: 'long' | 'short';
}

interface ReturnDistribution {
  bin: string;
  count: number;
  range: [number, number];
}

interface FactorExposure {
  factor: string;
  exposure: number;
  contribution: number;
}

interface BacktestVisualizationProps {
  equity: EquityPoint[];
  rollingMetrics?: RollingMetric[];
  trades?: TradePoint[];
  factorExposures?: FactorExposure[];
  benchmarkName?: string;
  className?: string;
}

type TimeFrame = '1M' | '3M' | '6M' | '1Y' | 'YTD' | 'ALL';
type ChartView = 'equity' | 'rolling' | 'distribution' | 'trades' | 'factors';

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

const filterByTimeframe = <T extends { date: string }>(
  data: T[],
  timeframe: TimeFrame
): T[] => {
  if (timeframe === 'ALL' || data.length === 0) return data;

  const now = new Date();
  let cutoff: Date;

  switch (timeframe) {
    case '1M':
      cutoff = new Date(now.setMonth(now.getMonth() - 1));
      break;
    case '3M':
      cutoff = new Date(now.setMonth(now.getMonth() - 3));
      break;
    case '6M':
      cutoff = new Date(now.setMonth(now.getMonth() - 6));
      break;
    case '1Y':
      cutoff = new Date(now.setFullYear(now.getFullYear() - 1));
      break;
    case 'YTD':
      cutoff = new Date(now.getFullYear(), 0, 1);
      break;
    default:
      return data;
  }

  return data.filter((d) => new Date(d.date) >= cutoff);
};

const calculateReturnDistribution = (
  equity: EquityPoint[],
  bins: number = 20
): ReturnDistribution[] => {
  const returns = equity.map((d) => d.returns).filter((r) => r !== undefined);
  if (returns.length === 0) return [];

  const min = Math.min(...returns);
  const max = Math.max(...returns);
  const binWidth = (max - min) / bins;

  const distribution: ReturnDistribution[] = [];
  for (let i = 0; i < bins; i++) {
    const rangeStart = min + i * binWidth;
    const rangeEnd = rangeStart + binWidth;
    const count = returns.filter((r) => r >= rangeStart && r < rangeEnd).length;
    distribution.push({
      bin: `${(rangeStart * 100).toFixed(1)}%`,
      count,
      range: [rangeStart, rangeEnd],
    });
  }
  return distribution;
};

const formatPercent = (value: number): string => `${(value * 100).toFixed(2)}%`;
const formatCurrency = (value: number): string =>
  `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

// Timeframe Selector
const TimeframeSelector: React.FC<{
  selected: TimeFrame;
  onSelect: (tf: TimeFrame) => void;
}> = ({ selected, onSelect }) => {
  const timeframes: TimeFrame[] = ['1M', '3M', '6M', '1Y', 'YTD', 'ALL'];

  return (
    <div className="flex gap-1 bg-gray-700 rounded-lg p-1">
      {timeframes.map((tf) => (
        <button
          key={tf}
          onClick={() => onSelect(tf)}
          className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
            selected === tf
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-600'
          }`}
        >
          {tf}
        </button>
      ))}
    </div>
  );
};

// View Selector
const ViewSelector: React.FC<{
  selected: ChartView;
  onSelect: (view: ChartView) => void;
}> = ({ selected, onSelect }) => {
  const views: { id: ChartView; label: string; icon: string }[] = [
    { id: 'equity', label: 'Equity Curve', icon: '📈' },
    { id: 'rolling', label: 'Rolling Metrics', icon: '📊' },
    { id: 'distribution', label: 'Distribution', icon: '📉' },
    { id: 'trades', label: 'Trade Analysis', icon: '🎯' },
    { id: 'factors', label: 'Factor Exposure', icon: '🔬' },
  ];

  return (
    <div className="flex gap-2">
      {views.map((v) => (
        <button
          key={v.id}
          onClick={() => onSelect(v.id)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selected === v.id
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <span>{v.icon}</span>
          <span className="hidden md:inline">{v.label}</span>
        </button>
      ))}
    </div>
  );
};

// Advanced Equity Curve with Underwater Chart
const EquityCurveChart: React.FC<{
  data: EquityPoint[];
  benchmarkName: string;
}> = ({ data, benchmarkName }) => {
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [showDrawdown, setShowDrawdown] = useState(true);

  const normalizedData = useMemo(() => {
    if (data.length === 0) return [];
    const startEquity = data[0].equity;
    const startBenchmark = data[0].benchmark;
    return data.map((d) => ({
      ...d,
      normalizedEquity: (d.equity / startEquity - 1) * 100,
      normalizedBenchmark: (d.benchmark / startBenchmark - 1) * 100,
      drawdownPct: d.drawdown * 100,
    }));
  }, [data]);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={showBenchmark}
            onChange={(e) => setShowBenchmark(e.target.checked)}
            className="rounded bg-gray-700"
          />
          Show {benchmarkName}
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={showDrawdown}
            onChange={(e) => setShowDrawdown(e.target.checked)}
            className="rounded bg-gray-700"
          />
          Show Drawdown
        </label>
      </div>

      {/* Main Chart */}
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={normalizedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            tickFormatter={(d) => new Date(d).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
          />
          <YAxis
            yAxisId="return"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            label={{ value: 'Return %', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
          />
          {showDrawdown && (
            <YAxis
              yAxisId="drawdown"
              orientation="right"
              tick={{ fill: '#9CA3AF', fontSize: 12 }}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              domain={['dataMin', 0]}
            />
          )}
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
            labelStyle={{ color: '#9CA3AF' }}
            formatter={(value: number, name: string) => [
              `${value.toFixed(2)}%`,
              name.replace('normalized', '').replace('Pct', ''),
            ]}
          />
          <Legend />
          {showDrawdown && (
            <Area
              yAxisId="drawdown"
              type="monotone"
              dataKey="drawdownPct"
              fill="rgba(239, 68, 68, 0.2)"
              stroke="#EF4444"
              name="Drawdown"
            />
          )}
          <Line
            yAxisId="return"
            type="monotone"
            dataKey="normalizedEquity"
            stroke="#10B981"
            strokeWidth={2}
            dot={false}
            name="Strategy"
          />
          {showBenchmark && (
            <Line
              yAxisId="return"
              type="monotone"
              dataKey="normalizedBenchmark"
              stroke="#6B7280"
              strokeWidth={1}
              strokeDasharray="5 5"
              dot={false}
              name={benchmarkName}
            />
          )}
          <ReferenceLine yAxisId="return" y={0} stroke="#4B5563" />
          <Brush dataKey="date" height={30} stroke="#4B5563" fill="#1F2937" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

// Rolling Metrics Chart
const RollingMetricsChart: React.FC<{
  data: RollingMetric[];
}> = ({ data }) => {
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['sharpe', 'volatility']);

  const metrics = [
    { key: 'sharpe', label: 'Sharpe Ratio', color: '#10B981' },
    { key: 'sortino', label: 'Sortino Ratio', color: '#3B82F6' },
    { key: 'volatility', label: 'Volatility', color: '#F59E0B' },
    { key: 'beta', label: 'Beta', color: '#8B5CF6' },
    { key: 'alpha', label: 'Alpha', color: '#EC4899' },
  ];

  const toggleMetric = (key: string) => {
    setSelectedMetrics((prev) =>
      prev.includes(key) ? prev.filter((m) => m !== key) : [...prev, key]
    );
  };

  return (
    <div className="space-y-4">
      {/* Metric toggles */}
      <div className="flex flex-wrap gap-2">
        {metrics.map((m) => (
          <button
            key={m.key}
            onClick={() => toggleMetric(m.key)}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors flex items-center gap-2 ${
              selectedMetrics.includes(m.key)
                ? 'bg-gray-600 text-white'
                : 'bg-gray-800 text-gray-400'
            }`}
          >
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: m.color }}
            />
            {m.label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            tickFormatter={(d) => new Date(d).toLocaleDateString('en-US', { month: 'short' })}
          />
          <YAxis tick={{ fill: '#9CA3AF', fontSize: 12 }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
            labelStyle={{ color: '#9CA3AF' }}
          />
          <Legend />
          {metrics
            .filter((m) => selectedMetrics.includes(m.key))
            .map((m) => (
              <Line
                key={m.key}
                type="monotone"
                dataKey={m.key}
                stroke={m.color}
                strokeWidth={2}
                dot={false}
                name={m.label}
              />
            ))}
          <ReferenceLine y={0} stroke="#4B5563" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

// Return Distribution Chart
const ReturnDistributionChart: React.FC<{
  data: ReturnDistribution[];
}> = ({ data }) => {
  const getBarColor = (range: [number, number]) => {
    const midpoint = (range[0] + range[1]) / 2;
    if (midpoint > 0.01) return '#10B981';
    if (midpoint > 0) return '#6EE7B7';
    if (midpoint > -0.01) return '#F87171';
    return '#EF4444';
  };

  // Calculate statistics
  const stats = useMemo(() => {
    const allReturns = data.flatMap((d) =>
      Array(d.count).fill((d.range[0] + d.range[1]) / 2)
    );
    if (allReturns.length === 0) return null;

    const mean = allReturns.reduce((a, b) => a + b, 0) / allReturns.length;
    const variance =
      allReturns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / allReturns.length;
    const stdDev = Math.sqrt(variance);
    const sortedReturns = [...allReturns].sort((a, b) => a - b);
    const median = sortedReturns[Math.floor(sortedReturns.length / 2)];

    return { mean, stdDev, median };
  }, [data]);

  return (
    <div className="space-y-4">
      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-700 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-sm">Mean Return</div>
            <div className={`text-xl font-bold ${stats.mean >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatPercent(stats.mean)}
            </div>
          </div>
          <div className="bg-gray-700 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-sm">Std Deviation</div>
            <div className="text-xl font-bold text-yellow-400">
              {formatPercent(stats.stdDev)}
            </div>
          </div>
          <div className="bg-gray-700 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-sm">Median Return</div>
            <div className={`text-xl font-bold ${stats.median >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatPercent(stats.median)}
            </div>
          </div>
        </div>
      )}

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="bin"
            tick={{ fill: '#9CA3AF', fontSize: 10 }}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis tick={{ fill: '#9CA3AF', fontSize: 12 }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
            labelStyle={{ color: '#9CA3AF' }}
          />
          <Bar dataKey="count" name="Frequency">
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getBarColor(entry.range)} />
            ))}
          </Bar>
          <ReferenceLine x="0.0%" stroke="#FBBF24" strokeWidth={2} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

// Trade Analysis Scatter Chart
const TradeAnalysisChart: React.FC<{
  trades: TradePoint[];
}> = ({ trades }) => {
  const chartData = useMemo(() => {
    return trades.map((t) => ({
      ...t,
      pnlK: t.pnl / 1000,
    }));
  }, [trades]);

  const winningTrades = chartData.filter((t) => t.pnl > 0);
  const losingTrades = chartData.filter((t) => t.pnl <= 0);

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-700 rounded-lg p-3 text-center">
          <div className="text-gray-400 text-sm">Win Rate</div>
          <div className="text-xl font-bold text-green-400">
            {((winningTrades.length / trades.length) * 100).toFixed(1)}%
          </div>
        </div>
        <div className="bg-gray-700 rounded-lg p-3 text-center">
          <div className="text-gray-400 text-sm">Avg Win</div>
          <div className="text-xl font-bold text-green-400">
            {formatCurrency(
              winningTrades.reduce((a, b) => a + b.pnl, 0) / (winningTrades.length || 1)
            )}
          </div>
        </div>
        <div className="bg-gray-700 rounded-lg p-3 text-center">
          <div className="text-gray-400 text-sm">Avg Loss</div>
          <div className="text-xl font-bold text-red-400">
            {formatCurrency(
              losingTrades.reduce((a, b) => a + b.pnl, 0) / (losingTrades.length || 1)
            )}
          </div>
        </div>
        <div className="bg-gray-700 rounded-lg p-3 text-center">
          <div className="text-gray-400 text-sm">Avg Holding</div>
          <div className="text-xl font-bold text-blue-400">
            {(trades.reduce((a, b) => a + b.holdingDays, 0) / trades.length).toFixed(1)} days
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="holdingDays"
            name="Holding Period"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            label={{ value: 'Holding Days', position: 'bottom', fill: '#9CA3AF' }}
          />
          <YAxis
            dataKey="pnlK"
            name="P&L"
            tick={{ fill: '#9CA3AF', fontSize: 12 }}
            tickFormatter={(v) => `$${v}K`}
            label={{ value: 'P&L ($K)', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
            formatter={(value: number, name: string) => [
              name === 'pnlK' ? formatCurrency(value * 1000) : value,
              name === 'pnlK' ? 'P&L' : name,
            ]}
            labelFormatter={(label) => `${label} days`}
          />
          <Legend />
          <ReferenceLine y={0} stroke="#4B5563" />
          <Scatter
            name="Long Trades"
            data={chartData.filter((t) => t.side === 'long')}
            fill="#10B981"
          />
          <Scatter
            name="Short Trades"
            data={chartData.filter((t) => t.side === 'short')}
            fill="#EF4444"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};

// Factor Exposure Radar Chart
const FactorExposureChart: React.FC<{
  exposures: FactorExposure[];
}> = ({ exposures }) => {
  const radarData = exposures.map((e) => ({
    factor: e.factor,
    exposure: Math.abs(e.exposure) * 100,
    fullMark: 100,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Radar Chart */}
        <ResponsiveContainer width="100%" height={300}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="factor" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#9CA3AF' }} />
            <Radar
              name="Exposure"
              dataKey="exposure"
              stroke="#3B82F6"
              fill="#3B82F6"
              fillOpacity={0.3}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
              formatter={(v: number) => [`${v.toFixed(1)}%`, 'Exposure']}
            />
          </RadarChart>
        </ResponsiveContainer>

        {/* Factor Table */}
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 p-2">Factor</th>
                <th className="text-right text-gray-400 p-2">Exposure</th>
                <th className="text-right text-gray-400 p-2">Contribution</th>
              </tr>
            </thead>
            <tbody>
              {exposures.map((e) => (
                <tr key={e.factor} className="border-b border-gray-800">
                  <td className="text-white p-2">{e.factor}</td>
                  <td
                    className={`text-right p-2 ${
                      e.exposure >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {(e.exposure * 100).toFixed(1)}%
                  </td>
                  <td
                    className={`text-right p-2 ${
                      e.contribution >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {(e.contribution * 100).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const BacktestVisualization: React.FC<BacktestVisualizationProps> = ({
  equity,
  rollingMetrics,
  trades,
  factorExposures,
  benchmarkName = 'S&P 500',
  className = '',
}) => {
  const [timeframe, setTimeframe] = useState<TimeFrame>('ALL');
  const [view, setView] = useState<ChartView>('equity');

  // Filter data by timeframe
  const filteredEquity = useMemo(
    () => filterByTimeframe(equity, timeframe),
    [equity, timeframe]
  );

  const filteredRolling = useMemo(
    () => (rollingMetrics ? filterByTimeframe(rollingMetrics, timeframe) : []),
    [rollingMetrics, timeframe]
  );

  const returnDistribution = useMemo(
    () => calculateReturnDistribution(filteredEquity),
    [filteredEquity]
  );

  // Use real data or empty arrays - no mock/random data
  const displayRollingMetrics = useMemo(() => {
    return rollingMetrics ? filteredRolling : [];
  }, [rollingMetrics, filteredRolling]);

  const displayTrades = useMemo(() => {
    return trades || [];
  }, [trades]);

  const displayFactorExposures = useMemo(() => {
    return factorExposures || [];
  }, [factorExposures]);

  const renderChart = () => {
    switch (view) {
      case 'equity':
        return <EquityCurveChart data={filteredEquity} benchmarkName={benchmarkName} />;
      case 'rolling':
        if (displayRollingMetrics.length === 0) {
          return (
            <div className="flex items-center justify-center h-[400px] text-gray-500">
              No backtest data available
            </div>
          );
        }
        return <RollingMetricsChart data={displayRollingMetrics} />;
      case 'distribution':
        return <ReturnDistributionChart data={returnDistribution} />;
      case 'trades':
        if (displayTrades.length === 0) {
          return (
            <div className="flex items-center justify-center h-[400px] text-gray-500">
              No backtest data available
            </div>
          );
        }
        return <TradeAnalysisChart trades={displayTrades} />;
      case 'factors':
        if (displayFactorExposures.length === 0) {
          return (
            <div className="flex items-center justify-center h-[400px] text-gray-500">
              No backtest data available
            </div>
          );
        }
        return <FactorExposureChart exposures={displayFactorExposures} />;
      default:
        return null;
    }
  };

  return (
    <div className={`bg-gray-800 rounded-lg p-6 ${className}`}>
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <h2 className="text-xl font-bold text-white">Performance Analysis</h2>
        <TimeframeSelector selected={timeframe} onSelect={setTimeframe} />
      </div>

      {/* View Selector */}
      <div className="mb-6">
        <ViewSelector selected={view} onSelect={setView} />
      </div>

      {/* Chart Container */}
      <div className="min-h-[400px]">
        {filteredEquity.length === 0 ? (
          <div className="flex items-center justify-center h-[400px] text-gray-500">
            No data available for selected timeframe
          </div>
        ) : (
          renderChart()
        )}
      </div>
    </div>
  );
};

export default BacktestVisualization;
