/**
 * Latency Monitor
 * Exchange latency stats
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
  LineChart,
  Line,
  Cell,
} from 'recharts';
import { ExchangeLatency } from '@/types/cross-exchange';

interface LatencyMonitorProps {
  latencies: ExchangeLatency[];
  onExchangeSelect?: (exchange: string) => void;
}

const StatusIndicator: React.FC<{ status: 'healthy' | 'degraded' | 'down' }> = ({ status }) => {
  const config = {
    healthy: { color: 'bg-green-500', pulse: false },
    degraded: { color: 'bg-yellow-500', pulse: true },
    down: { color: 'bg-red-500', pulse: true },
  };
  const { color, pulse } = config[status];

  return (
    <span className="relative flex h-3 w-3">
      {pulse && (
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-75`} />
      )}
      <span className={`relative inline-flex rounded-full h-3 w-3 ${color}`} />
    </span>
  );
};

const LatencyBar: React.FC<{ value: number; max: number; label: string }> = ({ value, max, label }) => {
  const pct = (value / max) * 100;
  const getColor = () => {
    if (value < 50) return 'bg-green-500';
    if (value < 100) return 'bg-yellow-500';
    if (value < 200) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-500">{label}</span>
        <span className={`font-medium ${value < 100 ? 'text-gray-300' : 'text-yellow-400'}`}>
          {value}ms
        </span>
      </div>
      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div 
          className={`h-full ${getColor()} transition-all`} 
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
};

const ExchangeCard: React.FC<{
  latency: ExchangeLatency;
  onClick: () => void;
}> = ({ latency, onClick }) => (
  <div 
    className="bg-gray-900/50 rounded-lg p-3 cursor-pointer hover:bg-gray-700/50 transition-all border border-gray-700/50"
    onClick={onClick}
  >
    <div className="flex justify-between items-center mb-3">
      <div className="flex items-center gap-2">
        <StatusIndicator status={latency.status} />
        <span className="text-white font-medium">{latency.exchange}</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
          latency.exchangeType === 'cex' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
        }`}>
          {latency.exchangeType.toUpperCase()}
        </span>
      </div>
      <span className={`text-lg font-bold ${
        latency.lastPingMs < 50 ? 'text-green-400' :
        latency.lastPingMs < 100 ? 'text-yellow-400' : 'text-red-400'
      }`}>
        {latency.lastPingMs}ms
      </span>
    </div>

    <div className="space-y-2">
      <LatencyBar value={latency.p50LatencyMs} max={300} label="P50" />
      <LatencyBar value={latency.p95LatencyMs} max={300} label="P95" />
      <LatencyBar value={latency.p99LatencyMs} max={300} label="P99" />
    </div>

    <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-700 text-center">
      <div>
        <p className="text-gray-500 text-[10px]">Avg</p>
        <p className="text-gray-300 text-xs">{latency.avgLatencyMs}ms</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">Uptime</p>
        <p className="text-gray-300 text-xs">{(latency.uptime * 100).toFixed(1)}%</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">Max</p>
        <p className="text-gray-300 text-xs">{latency.maxLatencyMs}ms</p>
      </div>
    </div>
  </div>
);

const ComparisonChart: React.FC<{ latencies: ExchangeLatency[] }> = ({ latencies }) => {
  const chartData = latencies.map(l => ({
    exchange: l.exchange,
    avg: l.avgLatencyMs,
    p95: l.p95LatencyMs,
  })).sort((a, b) => a.avg - b.avg);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis type="number" tick={{ fill: '#9CA3AF', fontSize: 10 }} domain={[0, 'auto']} />
        <YAxis type="category" dataKey="exchange" tick={{ fill: '#9CA3AF', fontSize: 10 }} width={80} />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
          formatter={(value: number, name: string) => [`${value}ms`, name === 'avg' ? 'Average' : 'P95']}
        />
        <Bar dataKey="avg" name="Average" fill="#3B82F6" radius={2}>
          {chartData.map((entry, index) => (
            <Cell 
              key={`cell-${index}`} 
              fill={entry.avg < 50 ? '#10B981' : entry.avg < 100 ? '#FBBF24' : '#EF4444'}
            />
          ))}
        </Bar>
        <Bar dataKey="p95" name="P95" fill="#8B5CF6" radius={2} />
      </BarChart>
    </ResponsiveContainer>
  );
};

export const LatencyMonitor: React.FC<LatencyMonitorProps> = ({
  latencies,
  onExchangeSelect,
}) => {
  const stats = useMemo(() => {
    const healthy = latencies.filter(l => l.status === 'healthy').length;
    const avgLatency = latencies.reduce((sum, l) => sum + l.avgLatencyMs, 0) / latencies.length;
    const fastestExchange = latencies.reduce((min, l) => l.avgLatencyMs < min.avgLatencyMs ? l : min, latencies[0]);
    
    return { healthy, avgLatency, fastestExchange, total: latencies.length };
  }, [latencies]);

  if (latencies.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-64">
        <p className="text-gray-500">No latency data available</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Exchange Latency</h3>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-green-400">{stats.healthy}/{stats.total} healthy</span>
          <span className="text-gray-400">Avg: {stats.avgLatency.toFixed(0)}ms</span>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        <div className="bg-gray-900/50 rounded p-2 text-center">
          <p className="text-gray-500 text-[10px]">Fastest</p>
          <p className="text-green-400 font-medium text-sm">{stats.fastestExchange?.exchange}</p>
          <p className="text-gray-400 text-xs">{stats.fastestExchange?.avgLatencyMs}ms</p>
        </div>
        <div className="bg-gray-900/50 rounded p-2 text-center">
          <p className="text-gray-500 text-[10px]">Healthy</p>
          <p className="text-green-400 font-medium text-lg">{stats.healthy}</p>
        </div>
        <div className="bg-gray-900/50 rounded p-2 text-center">
          <p className="text-gray-500 text-[10px]">Degraded</p>
          <p className="text-yellow-400 font-medium text-lg">
            {latencies.filter(l => l.status === 'degraded').length}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded p-2 text-center">
          <p className="text-gray-500 text-[10px]">Down</p>
          <p className="text-red-400 font-medium text-lg">
            {latencies.filter(l => l.status === 'down').length}
          </p>
        </div>
      </div>

      {/* Comparison Chart */}
      <div className="bg-gray-900/50 rounded-lg p-3 mb-4">
        <p className="text-gray-400 text-sm mb-2">Latency Comparison</p>
        <ComparisonChart latencies={latencies} />
      </div>

      {/* Exchange Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[400px] overflow-y-auto">
        {latencies
          .sort((a, b) => a.avgLatencyMs - b.avgLatencyMs)
          .map(latency => (
            <ExchangeCard
              key={latency.exchange}
              latency={latency}
              onClick={() => onExchangeSelect?.(latency.exchange)}
            />
          ))}
      </div>
    </div>
  );
};

export default LatencyMonitor;
