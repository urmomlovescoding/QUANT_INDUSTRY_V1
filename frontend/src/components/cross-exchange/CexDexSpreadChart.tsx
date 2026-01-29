/**
 * CEX vs DEX Spread Chart
 * Spread over time visualization
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
import { CexDexSpread, CexDexSpreadHistory } from '@/types/cross-exchange';

interface CexDexSpreadChartProps {
  currentSpread: CexDexSpread | null;
  history: CexDexSpreadHistory | null;
  symbol?: string;
}

const CustomTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-white text-xs font-medium mb-2">
        {new Date(label).toLocaleTimeString()}
      </p>
      <div className="space-y-1 text-xs">
        <div className="flex justify-between gap-4">
          <span className="text-blue-400">CEX Price:</span>
          <span className="text-white">${payload[0]?.payload?.cexPrice?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-purple-400">DEX Price:</span>
          <span className="text-white">${payload[0]?.payload?.dexPrice?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between gap-4 border-t border-gray-700 pt-1">
          <span className="text-gray-400">Spread:</span>
          <span className={payload[0]?.value > 0 ? 'text-green-400' : 'text-red-400'}>
            {(payload[0]?.value * 100).toFixed(3)}%
          </span>
        </div>
      </div>
    </div>
  );
};

const SpreadGauge: React.FC<{ spread: CexDexSpread }> = ({ spread }) => {
  const spreadPct = spread.spreadPct * 100;
  const isProfitable = spread.profitable;

  return (
    <div className="bg-gray-900/50 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <span className="text-gray-400 text-sm">Current Spread</span>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          isProfitable ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
        }`}>
          {isProfitable ? 'PROFITABLE' : 'NOT PROFITABLE'}
        </span>
      </div>

      <div className="text-center mb-4">
        <p className={`text-4xl font-bold ${
          spreadPct > 0.5 ? 'text-green-400' : 
          spreadPct > 0 ? 'text-yellow-400' : 'text-gray-400'
        }`}>
          {spreadPct > 0 ? '+' : ''}{spreadPct.toFixed(3)}%
        </p>
        <p className="text-gray-500 text-xs mt-1">
          {spread.direction === 'cex_to_dex' ? 'Buy CEX → Sell DEX' : 'Buy DEX → Sell CEX'}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="text-center">
          <p className="text-gray-500 text-xs">CEX ({spread.cexExchange})</p>
          <p className="text-blue-400 font-medium">${spread.cexPrice.toFixed(2)}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-500 text-xs">DEX ({spread.dexExchange})</p>
          <p className="text-purple-400 font-medium">${spread.dexPrice.toFixed(2)}</p>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-700">
        <div className="grid grid-cols-2 gap-2 text-center">
          <div>
            <p className="text-gray-500 text-[10px]">Gas Cost</p>
            <p className="text-orange-400 text-sm">${spread.gasCostUsd.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-gray-500 text-[10px]">Net Profit</p>
            <p className={`text-sm font-medium ${spread.netProfit > 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${spread.netProfit.toFixed(2)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export const CexDexSpreadChart: React.FC<CexDexSpreadChartProps> = ({
  currentSpread,
  history,
  symbol,
}) => {
  const [timeRange, setTimeRange] = useState<'1h' | '4h' | '24h'>('1h');

  const chartData = useMemo(() => {
    if (!history || !history.data) return [];
    
    const now = Date.now();
    const rangeMs = {
      '1h': 60 * 60 * 1000,
      '4h': 4 * 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
    }[timeRange];

    return history.data
      .filter(d => now - new Date(d.timestamp).getTime() < rangeMs)
      .map(d => ({
        ...d,
        spreadPct: d.spreadPct,
      }));
  }, [history, timeRange]);

  const stats = useMemo(() => {
    if (chartData.length === 0) return { avg: 0, max: 0, min: 0 };
    const spreads = chartData.map(d => d.spreadPct);
    return {
      avg: spreads.reduce((a, b) => a + b, 0) / spreads.length,
      max: Math.max(...spreads),
      min: Math.min(...spreads),
    };
  }, [chartData]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">
          CEX vs DEX Spread {symbol && `- ${symbol}`}
        </h3>
        <div className="flex gap-1 bg-gray-900/50 rounded p-1">
          {(['1h', '4h', '24h'] as const).map(range => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                timeRange === range ? 'bg-gray-700 text-white' : 'text-gray-400'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Current Spread Gauge */}
        {currentSpread && (
          <div className="lg:col-span-1">
            <SpreadGauge spread={currentSpread} />
          </div>
        )}

        {/* Spread Chart */}
        <div className={`${currentSpread ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
          {chartData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis 
                    dataKey="timestamp" 
                    tick={{ fill: '#9CA3AF', fontSize: 10 }}
                    tickFormatter={(v) => new Date(v).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                  />
                  <YAxis 
                    tick={{ fill: '#9CA3AF', fontSize: 10 }}
                    tickFormatter={(v) => `${(v * 100).toFixed(2)}%`}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine y={0} stroke="#6B7280" strokeDasharray="3 3" />
                  <Area
                    type="monotone"
                    dataKey="spreadPct"
                    name="Spread"
                    stroke="#3B82F6"
                    fill="#3B82F644"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 mt-4">
                <div className="bg-gray-900/50 rounded p-2 text-center">
                  <p className="text-gray-500 text-xs">Avg Spread</p>
                  <p className="text-white font-medium">{(stats.avg * 100).toFixed(3)}%</p>
                </div>
                <div className="bg-gray-900/50 rounded p-2 text-center">
                  <p className="text-gray-500 text-xs">Max Spread</p>
                  <p className="text-green-400 font-medium">{(stats.max * 100).toFixed(3)}%</p>
                </div>
                <div className="bg-gray-900/50 rounded p-2 text-center">
                  <p className="text-gray-500 text-xs">Min Spread</p>
                  <p className="text-red-400 font-medium">{(stats.min * 100).toFixed(3)}%</p>
                </div>
              </div>
            </>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No spread history available
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CexDexSpreadChart;
