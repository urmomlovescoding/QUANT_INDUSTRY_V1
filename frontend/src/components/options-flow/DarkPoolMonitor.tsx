/**
 * Dark Pool Monitor
 * Dark pool prints table + accumulation chart
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useMemo } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';
import { DarkPoolPrint, DarkPoolAccumulation } from '@/types/options-flow';

interface DarkPoolMonitorProps {
  prints: DarkPoolPrint[];
  accumulation: DarkPoolAccumulation[];
  selectedSymbol?: string;
  onSymbolSelect?: (symbol: string) => void;
}

const formatNotional = (value: number): string => {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
};

const PrintsTable: React.FC<{ prints: DarkPoolPrint[] }> = ({ prints }) => (
  <div className="overflow-auto max-h-64">
    <table className="w-full text-sm">
      <thead className="sticky top-0 bg-gray-800">
        <tr className="text-gray-400 text-xs">
          <th className="text-left p-2">Time</th>
          <th className="text-left p-2">Symbol</th>
          <th className="text-right p-2">Price</th>
          <th className="text-right p-2">Size</th>
          <th className="text-right p-2">Notional</th>
          <th className="text-center p-2">Type</th>
          <th className="text-center p-2">Side</th>
        </tr>
      </thead>
      <tbody>
        {prints.slice(0, 50).map((print) => (
          <tr key={print.id} className="border-t border-gray-700 hover:bg-gray-700/50">
            <td className="p-2 text-gray-300">
              {new Date(print.timestamp).toLocaleTimeString('en-US', { 
                hour: '2-digit', minute: '2-digit', second: '2-digit' 
              })}
            </td>
            <td className="p-2 text-white font-bold">{print.symbol}</td>
            <td className="p-2 text-right text-gray-300">${print.price.toFixed(2)}</td>
            <td className="p-2 text-right text-gray-300">{print.size.toLocaleString()}</td>
            <td className="p-2 text-right text-white font-medium">{formatNotional(print.notional)}</td>
            <td className="p-2 text-center">
              <span className={`px-2 py-0.5 rounded text-xs ${
                print.blockTrade ? 'bg-purple-500/20 text-purple-400' :
                print.darkPoolType === 'hidden' ? 'bg-blue-500/20 text-blue-400' :
                'bg-gray-500/20 text-gray-400'
              }`}>
                {print.blockTrade ? 'BLOCK' : print.darkPoolType.toUpperCase()}
              </span>
            </td>
            <td className="p-2 text-center">
              <span className={`text-sm ${
                print.aboveAsk ? 'text-green-400' : 
                print.belowBid ? 'text-red-400' : 
                'text-gray-400'
              }`}>
                {print.aboveAsk ? '↑' : print.belowBid ? '↓' : '—'}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const AccumulationChart: React.FC<{ data: DarkPoolAccumulation[] }> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-gray-500">
        No accumulation data
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis 
          dataKey="symbol" 
          tick={{ fill: '#9CA3AF', fontSize: 11 }}
        />
        <YAxis 
          tick={{ fill: '#9CA3AF', fontSize: 11 }}
          tickFormatter={(v) => formatNotional(v)}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
          formatter={(value: number, name: string) => [formatNotional(value), name]}
        />
        <Legend />
        <Bar dataKey="darkPoolVolume" name="Dark Pool Volume" fill="#8B5CF6">
          {data.map((entry, index) => (
            <Cell 
              key={`cell-${index}`}
              fill={entry.netAccumulation > 0 ? '#10B981' : '#EF4444'}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export const DarkPoolMonitor: React.FC<DarkPoolMonitorProps> = ({
  prints,
  accumulation,
  selectedSymbol,
  onSymbolSelect,
}) => {
  const [view, setView] = useState<'prints' | 'accumulation'>('prints');

  const filteredPrints = useMemo(() => {
    if (!selectedSymbol) return prints;
    return prints.filter(p => p.symbol === selectedSymbol);
  }, [prints, selectedSymbol]);

  const stats = useMemo(() => {
    const totalNotional = prints.reduce((sum, p) => sum + p.notional, 0);
    const blockPrints = prints.filter(p => p.blockTrade);
    const blockNotional = blockPrints.reduce((sum, p) => sum + p.notional, 0);
    const aboveAsk = prints.filter(p => p.aboveAsk).length;
    const belowBid = prints.filter(p => p.belowBid).length;
    
    return {
      totalPrints: prints.length,
      totalNotional,
      blockPrints: blockPrints.length,
      blockNotional,
      buyPressure: (aboveAsk / (aboveAsk + belowBid || 1)) * 100,
    };
  }, [prints]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Dark Pool Monitor</h3>
        <div className="flex gap-2">
          <button
            onClick={() => setView('prints')}
            className={`px-3 py-1 rounded text-sm ${
              view === 'prints' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'
            }`}
          >
            Prints
          </button>
          <button
            onClick={() => setView('accumulation')}
            className={`px-3 py-1 rounded text-sm ${
              view === 'accumulation' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'
            }`}
          >
            Accumulation
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-5 gap-4 mb-4 p-3 bg-gray-900/50 rounded-lg">
        <div className="text-center">
          <p className="text-gray-400 text-xs">Total Prints</p>
          <p className="text-white font-bold">{stats.totalPrints.toLocaleString()}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Total Notional</p>
          <p className="text-white font-bold">{formatNotional(stats.totalNotional)}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Block Trades</p>
          <p className="text-purple-400 font-bold">{stats.blockPrints}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Block Notional</p>
          <p className="text-purple-400 font-bold">{formatNotional(stats.blockNotional)}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Buy Pressure</p>
          <p className={`font-bold ${stats.buyPressure > 50 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.buyPressure.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Content */}
      {view === 'prints' ? (
        <PrintsTable prints={filteredPrints} />
      ) : (
        <AccumulationChart data={accumulation} />
      )}
    </div>
  );
};

export default DarkPoolMonitor;
