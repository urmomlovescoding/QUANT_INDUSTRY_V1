/**
 * Tape Reader
 * Time & sales visualization
 * QUANT_INDUSTRY_V1
 */

import React, { useMemo, useEffect, useRef } from 'react';
import { TapeEntry, TapeAnalysis } from '@/types/microstructure';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface TapeReaderProps {
  entries: TapeEntry[];
  analysis: TapeAnalysis | null;
  autoScroll?: boolean;
  maxEntries?: number;
}

const formatSize = (size: number): string => {
  if (size >= 1e6) return `${(size / 1e6).toFixed(1)}M`;
  if (size >= 1e3) return `${(size / 1e3).toFixed(0)}K`;
  return size.toString();
};

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  const time = date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  const ms = date.getMilliseconds().toString().padStart(3, '0').slice(0, 1);
  return `${time}.${ms}`;
};

const TapeRow: React.FC<{ entry: TapeEntry; isLarge: boolean }> = ({ entry, isLarge }) => {
  const sideColor = entry.side === 'buy' ? 'text-green-400' : 
                    entry.side === 'sell' ? 'text-red-400' : 'text-gray-400';
  
  return (
    <div className={`flex items-center text-xs font-mono px-2 py-0.5 hover:bg-gray-700/50 ${
      isLarge ? 'bg-yellow-500/10 border-l-2 border-yellow-500' : ''
    }`}>
      <span className="w-20 text-gray-500">{formatTime(entry.timestamp)}</span>
      <span className={`w-20 text-right ${sideColor}`}>{formatSize(entry.size)}</span>
      <span className="w-20 text-right text-white">${entry.price.toFixed(2)}</span>
      <span className={`w-8 text-center ${sideColor}`}>
        {entry.direction === 'uptick' ? '↑' : entry.direction === 'downtick' ? '↓' : '—'}
      </span>
      <span className="w-12 text-gray-500 text-center">{entry.exchange}</span>
      {entry.isBlock && <span className="px-1 bg-purple-500/20 text-purple-400 rounded text-[10px]">BLK</span>}
      {entry.isSweep && <span className="px-1 bg-yellow-500/20 text-yellow-400 rounded text-[10px] ml-1">SWP</span>}
    </div>
  );
};

const VolumeProfileChart: React.FC<{ volumeProfile: TapeAnalysis['volumeProfile'] }> = ({ volumeProfile }) => {
  if (!volumeProfile || volumeProfile.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={150}>
      <BarChart data={volumeProfile} layout="vertical">
        <XAxis type="number" tick={{ fill: '#9CA3AF', fontSize: 10 }} />
        <YAxis 
          type="category" 
          dataKey="price" 
          tick={{ fill: '#9CA3AF', fontSize: 10 }}
          width={50}
          tickFormatter={(v) => `$${v.toFixed(0)}`}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
          formatter={(value: number) => [formatSize(value), 'Volume']}
        />
        <Bar dataKey="buyVolume" stackId="stack" fill="#10B981" />
        <Bar dataKey="sellVolume" stackId="stack" fill="#EF4444" />
      </BarChart>
    </ResponsiveContainer>
  );
};

export const TapeReader: React.FC<TapeReaderProps> = ({
  entries,
  analysis,
  autoScroll = true,
  maxEntries = 100,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries, autoScroll]);

  const displayEntries = useMemo(() => {
    return entries.slice(-maxEntries);
  }, [entries, maxEntries]);

  const largeThreshold = useMemo(() => {
    if (entries.length === 0) return 10000;
    const sizes = entries.map(e => e.size);
    const sorted = [...sizes].sort((a, b) => b - a);
    return sorted[Math.floor(sorted.length * 0.1)] || 10000; // Top 10% are "large"
  }, [entries]);

  const stats = useMemo(() => {
    if (!analysis) return null;
    const buyPct = (analysis.buyVolume / analysis.totalVolume) * 100;
    return {
      buyPct,
      sellPct: (analysis.sellVolume / analysis.totalVolume) * 100,
      buyBias: buyPct > 55 ? 'BUY PRESSURE' : buyPct < 45 ? 'SELL PRESSURE' : 'BALANCED',
    };
  }, [analysis]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Time & Sales</h3>
        {stats && (
          <span className={`px-2 py-1 rounded text-xs font-medium ${
            stats.buyPct > 55 ? 'bg-green-500/20 text-green-400' :
            stats.buyPct < 45 ? 'bg-red-500/20 text-red-400' :
            'bg-gray-500/20 text-gray-400'
          }`}>
            {stats.buyBias}
          </span>
        )}
      </div>

      {/* Summary Stats */}
      {analysis && (
        <div className="grid grid-cols-5 gap-2 mb-4 p-2 bg-gray-900/50 rounded">
          <div className="text-center">
            <p className="text-gray-500 text-[10px]">Total Vol</p>
            <p className="text-white font-medium text-sm">{formatSize(analysis.totalVolume)}</p>
          </div>
          <div className="text-center">
            <p className="text-gray-500 text-[10px]">Buy Vol</p>
            <p className="text-green-400 font-medium text-sm">{formatSize(analysis.buyVolume)}</p>
          </div>
          <div className="text-center">
            <p className="text-gray-500 text-[10px]">Sell Vol</p>
            <p className="text-red-400 font-medium text-sm">{formatSize(analysis.sellVolume)}</p>
          </div>
          <div className="text-center">
            <p className="text-gray-500 text-[10px]">VWAP</p>
            <p className="text-white font-medium text-sm">${analysis.vwap.toFixed(2)}</p>
          </div>
          <div className="text-center">
            <p className="text-gray-500 text-[10px]">Velocity</p>
            <p className="text-blue-400 font-medium text-sm">{analysis.tradeVelocity.toFixed(0)}/s</p>
          </div>
        </div>
      )}

      {/* Buy/Sell Bar */}
      {stats && (
        <div className="flex h-3 rounded overflow-hidden mb-4">
          <div 
            className="bg-green-500 flex items-center justify-center"
            style={{ width: `${stats.buyPct}%` }}
          >
            {stats.buyPct > 20 && (
              <span className="text-[10px] text-white font-medium">{stats.buyPct.toFixed(0)}%</span>
            )}
          </div>
          <div 
            className="bg-red-500 flex items-center justify-center"
            style={{ width: `${stats.sellPct}%` }}
          >
            {stats.sellPct > 20 && (
              <span className="text-[10px] text-white font-medium">{stats.sellPct.toFixed(0)}%</span>
            )}
          </div>
        </div>
      )}

      {/* Tape Header */}
      <div className="flex items-center text-[10px] text-gray-500 px-2 py-1 border-b border-gray-700 font-medium">
        <span className="w-20">TIME</span>
        <span className="w-20 text-right">SIZE</span>
        <span className="w-20 text-right">PRICE</span>
        <span className="w-8 text-center">DIR</span>
        <span className="w-12 text-center">EXCH</span>
        <span>FLAGS</span>
      </div>

      {/* Tape Entries */}
      <div 
        ref={scrollRef}
        className="h-64 overflow-y-auto scrollbar-thin"
      >
        {displayEntries.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            No trades yet
          </div>
        ) : (
          displayEntries.map((entry) => (
            <TapeRow 
              key={entry.id} 
              entry={entry} 
              isLarge={entry.size >= largeThreshold}
            />
          ))
        )}
      </div>

      {/* Volume Profile */}
      {analysis && analysis.volumeProfile && analysis.volumeProfile.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <p className="text-gray-400 text-sm mb-2">Volume Profile</p>
          <VolumeProfileChart volumeProfile={analysis.volumeProfile} />
        </div>
      )}
    </div>
  );
};

export default TapeReader;
