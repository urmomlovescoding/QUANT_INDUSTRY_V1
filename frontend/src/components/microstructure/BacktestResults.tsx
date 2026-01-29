/**
 * Order Flow Backtest Results
 * Backtest visualization for order flow strategies
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts';
import { OrderFlowBacktestResult, OrderFlowBacktestTrade } from '@/types/microstructure';

interface BacktestResultsProps {
  results: OrderFlowBacktestResult[];
  onResultSelect?: (result: OrderFlowBacktestResult) => void;
}

const MetricCard: React.FC<{
  label: string;
  value: string | number;
  format?: 'percent' | 'currency' | 'number' | 'ratio';
  highlight?: 'positive' | 'negative' | 'neutral';
}> = ({ label, value, format = 'number', highlight }) => {
  const formatValue = (v: string | number): string => {
    if (typeof v === 'string') return v;
    switch (format) {
      case 'percent': return `${(v * 100).toFixed(2)}%`;
      case 'currency': return `$${v.toLocaleString()}`;
      case 'ratio': return v.toFixed(2);
      default: return v.toLocaleString();
    }
  };

  const getColor = () => {
    if (highlight === 'positive') return 'text-green-400';
    if (highlight === 'negative') return 'text-red-400';
    return 'text-gray-200';
  };

  return (
    <div className="bg-gray-900/50 rounded-lg p-3 text-center">
      <p className="text-gray-400 text-xs">{label}</p>
      <p className={`text-lg font-bold ${getColor()}`}>{formatValue(value)}</p>
    </div>
  );
};

const EquityCurve: React.FC<{ data: OrderFlowBacktestResult['equityCurve'] }> = ({ data }) => (
  <ResponsiveContainer width="100%" height={250}>
    <AreaChart data={data}>
      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
      <XAxis 
        dataKey="timestamp" 
        tick={{ fill: '#9CA3AF', fontSize: 10 }}
        tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
      />
      <YAxis 
        yAxisId="equity"
        tick={{ fill: '#9CA3AF', fontSize: 10 }}
        tickFormatter={(v) => `$${(v/1000).toFixed(0)}K`}
      />
      <YAxis 
        yAxisId="dd"
        orientation="right"
        tick={{ fill: '#9CA3AF', fontSize: 10 }}
        tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
      />
      <Tooltip
        contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
        labelFormatter={(v) => new Date(v).toLocaleDateString()}
        formatter={(value: number, name: string) => {
          if (name === 'equity') return [`$${value.toLocaleString()}`, 'Equity'];
          return [`${(value * 100).toFixed(2)}%`, 'Drawdown'];
        }}
      />
      <Legend />
      <Area
        yAxisId="dd"
        type="monotone"
        dataKey="drawdown"
        name="Drawdown"
        fill="#EF444444"
        stroke="#EF4444"
      />
      <Line
        yAxisId="equity"
        type="monotone"
        dataKey="equity"
        name="Equity"
        stroke="#10B981"
        dot={false}
        strokeWidth={2}
      />
      <ReferenceLine yAxisId="equity" y={100000} stroke="#6B7280" strokeDasharray="3 3" />
    </AreaChart>
  </ResponsiveContainer>
);

const MonthlyReturnsChart: React.FC<{ data: OrderFlowBacktestResult['monthlyReturns'] }> = ({ data }) => (
  <ResponsiveContainer width="100%" height={150}>
    <AreaChart data={data}>
      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
      <XAxis 
        dataKey="month" 
        tick={{ fill: '#9CA3AF', fontSize: 10 }}
      />
      <YAxis 
        tick={{ fill: '#9CA3AF', fontSize: 10 }}
        tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
      />
      <Tooltip
        contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
        formatter={(value: number) => [`${(value * 100).toFixed(2)}%`, 'Return']}
      />
      <ReferenceLine y={0} stroke="#6B7280" />
      <Area
        type="monotone"
        dataKey="return"
        fill="#3B82F644"
        stroke="#3B82F6"
      />
    </AreaChart>
  </ResponsiveContainer>
);

const TradesTable: React.FC<{ trades: OrderFlowBacktestTrade[] }> = ({ trades }) => (
  <div className="max-h-48 overflow-y-auto">
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-gray-800">
        <tr className="text-gray-400">
          <th className="text-left p-2">Entry</th>
          <th className="text-left p-2">Symbol</th>
          <th className="text-center p-2">Side</th>
          <th className="text-right p-2">Entry $</th>
          <th className="text-right p-2">Exit $</th>
          <th className="text-right p-2">P&L</th>
          <th className="text-right p-2">%</th>
        </tr>
      </thead>
      <tbody>
        {trades.slice(0, 30).map((trade) => (
          <tr key={trade.id} className="border-t border-gray-700 hover:bg-gray-700/50">
            <td className="p-2 text-gray-300">
              {new Date(trade.entryTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </td>
            <td className="p-2 text-white font-medium">{trade.symbol}</td>
            <td className={`p-2 text-center ${trade.side === 'long' ? 'text-green-400' : 'text-red-400'}`}>
              {trade.side.toUpperCase()}
            </td>
            <td className="p-2 text-right text-gray-300">${trade.entryPrice.toFixed(2)}</td>
            <td className="p-2 text-right text-gray-300">${trade.exitPrice.toFixed(2)}</td>
            <td className={`p-2 text-right font-medium ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${trade.pnl.toFixed(2)}
            </td>
            <td className={`p-2 text-right ${trade.pnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {(trade.pnlPct * 100).toFixed(1)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const ResultCard: React.FC<{
  result: OrderFlowBacktestResult;
  isSelected: boolean;
  onSelect: () => void;
}> = ({ result, isSelected, onSelect }) => (
  <div
    className={`p-3 rounded-lg cursor-pointer transition-all ${
      isSelected ? 'bg-blue-600/20 ring-2 ring-blue-500' : 'bg-gray-900/50 hover:bg-gray-700/50'
    }`}
    onClick={onSelect}
  >
    <div className="flex justify-between items-start">
      <div>
        <p className="text-white font-medium">{result.strategyName}</p>
        <p className="text-gray-500 text-xs">{result.symbol} | {result.startDate} - {result.endDate}</p>
      </div>
      <span className={`px-2 py-1 rounded text-xs font-medium ${
        result.totalReturn > 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
      }`}>
        {(result.totalReturn * 100).toFixed(1)}%
      </span>
    </div>
    <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
      <div>
        <span className="text-gray-500">Sharpe:</span>
        <span className="text-white ml-1">{result.sharpeRatio.toFixed(2)}</span>
      </div>
      <div>
        <span className="text-gray-500">Win:</span>
        <span className="text-white ml-1">{(result.winRate * 100).toFixed(0)}%</span>
      </div>
      <div>
        <span className="text-gray-500">Trades:</span>
        <span className="text-white ml-1">{result.totalTrades}</span>
      </div>
    </div>
  </div>
);

export const BacktestResults: React.FC<BacktestResultsProps> = ({
  results,
  onResultSelect,
}) => {
  const [selectedId, setSelectedId] = useState<string | null>(
    results.length > 0 ? results[0].id : null
  );

  const selectedResult = results.find(r => r.id === selectedId);

  const handleSelect = (result: OrderFlowBacktestResult) => {
    setSelectedId(result.id);
    onResultSelect?.(result);
  };

  if (results.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-64">
        <p className="text-gray-500">No backtest results available</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-gray-300 font-medium mb-4">Order Flow Backtest Results</h3>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Results List */}
        <div className="space-y-2 max-h-[500px] overflow-y-auto">
          {results.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              isSelected={result.id === selectedId}
              onSelect={() => handleSelect(result)}
            />
          ))}
        </div>

        {/* Selected Result Details */}
        {selectedResult && (
          <div className="lg:col-span-2 space-y-4">
            {/* Key Metrics */}
            <div className="grid grid-cols-4 gap-2">
              <MetricCard
                label="Total Return"
                value={selectedResult.totalReturn}
                format="percent"
                highlight={selectedResult.totalReturn >= 0 ? 'positive' : 'negative'}
              />
              <MetricCard
                label="Sharpe Ratio"
                value={selectedResult.sharpeRatio}
                format="ratio"
                highlight={selectedResult.sharpeRatio >= 1.5 ? 'positive' : 'neutral'}
              />
              <MetricCard
                label="Max Drawdown"
                value={selectedResult.maxDrawdown}
                format="percent"
                highlight="negative"
              />
              <MetricCard
                label="Win Rate"
                value={selectedResult.winRate}
                format="percent"
                highlight={selectedResult.winRate >= 0.5 ? 'positive' : 'negative'}
              />
            </div>

            <div className="grid grid-cols-4 gap-2">
              <MetricCard label="Total Trades" value={selectedResult.totalTrades} />
              <MetricCard 
                label="Profit Factor" 
                value={selectedResult.profitFactor} 
                format="ratio"
                highlight={selectedResult.profitFactor >= 1.5 ? 'positive' : 'neutral'}
              />
              <MetricCard 
                label="Avg Winner" 
                value={selectedResult.avgWinner} 
                format="currency"
                highlight="positive"
              />
              <MetricCard 
                label="Avg Loser" 
                value={selectedResult.avgLoser} 
                format="currency"
                highlight="negative"
              />
            </div>

            {/* Equity Curve */}
            <div className="bg-gray-900/50 rounded-lg p-3">
              <p className="text-gray-400 text-sm mb-2">Equity Curve</p>
              <EquityCurve data={selectedResult.equityCurve} />
            </div>

            {/* Monthly Returns */}
            <div className="bg-gray-900/50 rounded-lg p-3">
              <p className="text-gray-400 text-sm mb-2">Monthly Returns</p>
              <MonthlyReturnsChart data={selectedResult.monthlyReturns} />
            </div>

            {/* Trades Table */}
            <div className="bg-gray-900/50 rounded-lg p-3">
              <p className="text-gray-400 text-sm mb-2">Recent Trades</p>
              <TradesTable trades={selectedResult.trades} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BacktestResults;
