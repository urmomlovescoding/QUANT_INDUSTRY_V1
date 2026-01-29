/**
 * Smart Money Tracker
 * Institutional flow tracking
 * QUANT_INDUSTRY_V1
 */

import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
  PieChart,
  Pie,
} from 'recharts';
import { InstitutionalFlow, SmartMoneyMetrics } from '@/types/options-flow';

interface SmartMoneyTrackerProps {
  flow: InstitutionalFlow[];
  metrics: SmartMoneyMetrics[];
  onSymbolClick?: (symbol: string) => void;
}

const formatNotional = (value: number): string => {
  const absValue = Math.abs(value);
  if (absValue >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (absValue >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (absValue >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
};

const SentimentMeter: React.FC<{ value: number; label: string }> = ({ value, label }) => {
  const percentage = Math.min(100, Math.max(0, (value + 1) * 50)); // Convert -1 to 1 range to 0-100
  
  return (
    <div className="flex items-center gap-3">
      <span className="text-gray-400 text-sm w-20">{label}</span>
      <div className="flex-1 h-3 bg-gray-700 rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all duration-500 ${
            value > 0 ? 'bg-green-500' : value < 0 ? 'bg-red-500' : 'bg-gray-500'
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className={`text-sm font-medium w-12 text-right ${
        value > 0 ? 'text-green-400' : value < 0 ? 'text-red-400' : 'text-gray-400'
      }`}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
};

const MetricsCard: React.FC<{ metrics: SmartMoneyMetrics }> = ({ metrics }) => (
  <div className="bg-gray-900/50 rounded-lg p-4">
    <div className="flex justify-between items-center mb-3">
      <h4 className="text-white font-bold">{metrics.symbol}</h4>
      <span className={`px-2 py-1 rounded text-xs font-medium ${
        metrics.smartMoneySentiment === 'bullish' ? 'bg-green-500/20 text-green-400' :
        metrics.smartMoneySentiment === 'bearish' ? 'bg-red-500/20 text-red-400' :
        'bg-gray-500/20 text-gray-400'
      }`}>
        {metrics.smartMoneySentiment.toUpperCase()}
      </span>
    </div>

    <div className="space-y-2">
      <SentimentMeter value={metrics.smartMoneyIndex} label="SMI" />
      <SentimentMeter value={metrics.institutionalAccumulation} label="Accum" />
      <SentimentMeter value={metrics.flowImbalance} label="Imbal" />
    </div>

    <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-gray-700">
      <div>
        <p className="text-gray-400 text-xs">Large Trader</p>
        <p className="text-white font-medium">{(metrics.largeTraderActivity * 100).toFixed(1)}%</p>
      </div>
      <div>
        <p className="text-gray-400 text-xs">Divergence</p>
        <p className={`font-medium ${
          Math.abs(metrics.divergence) > 0.3 ? 'text-yellow-400' : 'text-gray-400'
        }`}>
          {(metrics.divergence * 100).toFixed(1)}%
        </p>
      </div>
    </div>
  </div>
);

const FlowChart: React.FC<{ flow: InstitutionalFlow[] }> = ({ flow }) => {
  const aggregatedFlow = useMemo(() => {
    const bySymbol: Record<string, { symbol: string; buyFlow: number; sellFlow: number }> = {};
    
    flow.forEach(f => {
      if (!bySymbol[f.symbol]) {
        bySymbol[f.symbol] = { symbol: f.symbol, buyFlow: 0, sellFlow: 0 };
      }
      if (f.flowType === 'buy') {
        bySymbol[f.symbol].buyFlow += f.notional;
      } else {
        bySymbol[f.symbol].sellFlow += f.notional;
      }
    });

    return Object.values(bySymbol)
      .sort((a, b) => (b.buyFlow + b.sellFlow) - (a.buyFlow + a.sellFlow))
      .slice(0, 10);
  }, [flow]);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={aggregatedFlow} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis 
          type="number" 
          tick={{ fill: '#9CA3AF', fontSize: 11 }}
          tickFormatter={(v) => formatNotional(v)}
        />
        <YAxis 
          type="category" 
          dataKey="symbol" 
          tick={{ fill: '#9CA3AF', fontSize: 11 }}
          width={60}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
          formatter={(value: number, name: string) => [formatNotional(value), name]}
        />
        <Legend />
        <Bar dataKey="buyFlow" name="Buy Flow" fill="#10B981" stackId="stack" />
        <Bar dataKey="sellFlow" name="Sell Flow" fill="#EF4444" stackId="stack" />
      </BarChart>
    </ResponsiveContainer>
  );
};

const RecentFlow: React.FC<{ flow: InstitutionalFlow[] }> = ({ flow }) => (
  <div className="overflow-auto max-h-48">
    <table className="w-full text-sm">
      <thead className="sticky top-0 bg-gray-800">
        <tr className="text-gray-400 text-xs">
          <th className="text-left p-2">Time</th>
          <th className="text-left p-2">Symbol</th>
          <th className="text-center p-2">Side</th>
          <th className="text-right p-2">Notional</th>
          <th className="text-center p-2">Type</th>
          <th className="text-right p-2">Conf</th>
        </tr>
      </thead>
      <tbody>
        {flow.slice(0, 20).map((f) => (
          <tr key={f.id} className="border-t border-gray-700 hover:bg-gray-700/50">
            <td className="p-2 text-gray-300 text-xs">
              {new Date(f.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
            </td>
            <td className="p-2 text-white font-medium">{f.symbol}</td>
            <td className="p-2 text-center">
              <span className={f.flowType === 'buy' ? 'text-green-400' : 'text-red-400'}>
                {f.flowType === 'buy' ? '▲' : '▼'}
              </span>
            </td>
            <td className="p-2 text-right text-white">{formatNotional(f.notional)}</td>
            <td className="p-2 text-center">
              {f.isBlock && <span className="px-1 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded mr-1">B</span>}
              {f.isSweep && <span className="px-1 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">S</span>}
            </td>
            <td className="p-2 text-right text-gray-300">{(f.confidence * 100).toFixed(0)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export const SmartMoneyTracker: React.FC<SmartMoneyTrackerProps> = ({
  flow,
  metrics,
  onSymbolClick,
}) => {
  const stats = useMemo(() => {
    const totalBuy = flow.filter(f => f.flowType === 'buy').reduce((sum, f) => sum + f.notional, 0);
    const totalSell = flow.filter(f => f.flowType === 'sell').reduce((sum, f) => sum + f.notional, 0);
    const blocks = flow.filter(f => f.isBlock);
    const sweeps = flow.filter(f => f.isSweep);
    
    return {
      totalFlow: totalBuy + totalSell,
      netFlow: totalBuy - totalSell,
      buyPct: (totalBuy / (totalBuy + totalSell || 1)) * 100,
      blockCount: blocks.length,
      sweepCount: sweeps.length,
    };
  }, [flow]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-gray-300 font-medium mb-4">Smart Money Tracker</h3>

      {/* Stats Row */}
      <div className="grid grid-cols-5 gap-4 mb-4 p-3 bg-gray-900/50 rounded-lg">
        <div className="text-center">
          <p className="text-gray-400 text-xs">Total Flow</p>
          <p className="text-white font-bold">{formatNotional(stats.totalFlow)}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Net Flow</p>
          <p className={`font-bold ${stats.netFlow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatNotional(stats.netFlow)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Buy/Sell</p>
          <p className={`font-bold ${stats.buyPct >= 50 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.buyPct.toFixed(0)}%/{(100 - stats.buyPct).toFixed(0)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Blocks</p>
          <p className="text-purple-400 font-bold">{stats.blockCount}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Sweeps</p>
          <p className="text-yellow-400 font-bold">{stats.sweepCount}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Flow Chart */}
        <div className="bg-gray-900/30 rounded-lg p-3">
          <h4 className="text-gray-400 text-sm mb-2">Flow by Symbol</h4>
          <FlowChart flow={flow} />
        </div>

        {/* Metrics Cards */}
        <div className="space-y-3">
          <h4 className="text-gray-400 text-sm">Smart Money Metrics</h4>
          <div className="grid grid-cols-1 gap-3 max-h-[320px] overflow-auto">
            {metrics.slice(0, 6).map((m) => (
              <MetricsCard key={m.symbol} metrics={m} />
            ))}
          </div>
        </div>
      </div>

      {/* Recent Flow */}
      <div className="mt-4">
        <h4 className="text-gray-400 text-sm mb-2">Recent Institutional Flow</h4>
        <RecentFlow flow={flow} />
      </div>
    </div>
  );
};

export default SmartMoneyTracker;
