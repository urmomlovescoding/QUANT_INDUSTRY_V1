/**
 * Flow Signals Panel
 * Real-time flow signals list
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useMemo } from 'react';
import { FlowSignal, FlowDirection } from '@/types/options-flow';

interface FlowSignalsPanelProps {
  signals: FlowSignal[];
  onSignalClick?: (signal: FlowSignal) => void;
  maxItems?: number;
}

const SignalTypeBadge: React.FC<{ type: string }> = ({ type }) => {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    unusual_activity: { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'UNUSUAL' },
    gamma_squeeze: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'GEX' },
    dark_pool_block: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'DARK POOL' },
    smart_money_divergence: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'DIVERGENCE' },
    sweep_alert: { bg: 'bg-pink-500/20', text: 'text-pink-400', label: 'SWEEP' },
  };

  const { bg, text, label } = config[type] || { bg: 'bg-gray-500/20', text: 'text-gray-400', label: type };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      {label}
    </span>
  );
};

const DirectionIndicator: React.FC<{ direction: FlowDirection }> = ({ direction }) => {
  const config = {
    bullish: { icon: '▲', color: 'text-green-400', bg: 'bg-green-500/10' },
    bearish: { icon: '▼', color: 'text-red-400', bg: 'bg-red-500/10' },
    neutral: { icon: '—', color: 'text-gray-400', bg: 'bg-gray-500/10' },
  };

  const { icon, color, bg } = config[direction];

  return (
    <span className={`w-8 h-8 flex items-center justify-center rounded-lg ${bg} ${color} font-bold`}>
      {icon}
    </span>
  );
};

const AlertLevelIndicator: React.FC<{ level: string }> = ({ level }) => {
  const config = {
    critical: { color: 'bg-red-500', pulse: true },
    warning: { color: 'bg-yellow-500', pulse: true },
    info: { color: 'bg-blue-500', pulse: false },
  };

  const { color, pulse } = config[level as keyof typeof config] || config.info;

  return (
    <span className={`relative flex h-2 w-2`}>
      {pulse && (
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-75`} />
      )}
      <span className={`relative inline-flex rounded-full h-2 w-2 ${color}`} />
    </span>
  );
};

const StrengthBar: React.FC<{ strength: number }> = ({ strength }) => {
  const getColor = (s: number) => {
    if (s >= 0.8) return 'bg-red-500';
    if (s >= 0.6) return 'bg-orange-500';
    if (s >= 0.4) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div 
          className={`h-full ${getColor(strength)} transition-all`}
          style={{ width: `${strength * 100}%` }}
        />
      </div>
      <span className="text-xs text-gray-400">{(strength * 100).toFixed(0)}%</span>
    </div>
  );
};

const SignalCard: React.FC<{ signal: FlowSignal; onClick?: () => void }> = ({ signal, onClick }) => {
  const timeAgo = (timestamp: string): string => {
    const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <div 
      className="bg-gray-900/50 rounded-lg p-3 hover:bg-gray-700/50 cursor-pointer transition-colors border border-gray-700/50"
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <DirectionIndicator direction={signal.direction} />
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-white font-bold">{signal.symbol}</span>
            <SignalTypeBadge type={signal.signalType} />
            <AlertLevelIndicator level={signal.alertLevel} />
          </div>
          
          <p className="text-gray-300 text-sm line-clamp-2">{signal.description}</p>
          
          <div className="flex items-center justify-between mt-2">
            <StrengthBar strength={signal.strength} />
            <span className="text-gray-500 text-xs">{timeAgo(signal.timestamp)}</span>
          </div>
        </div>
      </div>

      {/* Details Preview */}
      {signal.details && Object.keys(signal.details).length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-700/50 grid grid-cols-3 gap-2 text-xs">
          {Object.entries(signal.details).slice(0, 3).map(([key, value]) => (
            <div key={key}>
              <span className="text-gray-500">{key.replace(/_/g, ' ')}:</span>
              <span className="text-gray-300 ml-1">
                {typeof value === 'number' ? value.toLocaleString() : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const FlowSignalsPanel: React.FC<FlowSignalsPanelProps> = ({
  signals,
  onSignalClick,
  maxItems = 20,
}) => {
  const [filter, setFilter] = useState<'all' | FlowDirection>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const signalTypes = useMemo(() => {
    const types = new Set(signals.map(s => s.signalType));
    return ['all', ...Array.from(types)];
  }, [signals]);

  const filteredSignals = useMemo(() => {
    return signals
      .filter(s => filter === 'all' || s.direction === filter)
      .filter(s => typeFilter === 'all' || s.signalType === typeFilter)
      .slice(0, maxItems);
  }, [signals, filter, typeFilter, maxItems]);

  const stats = useMemo(() => ({
    total: signals.length,
    bullish: signals.filter(s => s.direction === 'bullish').length,
    bearish: signals.filter(s => s.direction === 'bearish').length,
    critical: signals.filter(s => s.alertLevel === 'critical').length,
  }), [signals]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Flow Signals</h3>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-400">▲ {stats.bullish}</span>
          <span className="text-red-400">▼ {stats.bearish}</span>
          {stats.critical > 0 && (
            <span className="text-red-400 animate-pulse">🔴 {stats.critical}</span>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <div className="flex gap-1 bg-gray-900/50 rounded-lg p-1">
          {(['all', 'bullish', 'bearish', 'neutral'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                filter === f 
                  ? 'bg-gray-700 text-white' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-gray-900 text-gray-300 text-xs rounded-lg px-3 py-1 border border-gray-700"
        >
          {signalTypes.map((type) => (
            <option key={type} value={type}>
              {type === 'all' ? 'All Types' : type.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>

      {/* Signals List */}
      <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
        {filteredSignals.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No signals match your filters
          </div>
        ) : (
          filteredSignals.map((signal) => (
            <SignalCard 
              key={signal.id} 
              signal={signal}
              onClick={() => onSignalClick?.(signal)}
            />
          ))
        )}
      </div>

      {/* Load More */}
      {signals.length > maxItems && (
        <div className="text-center mt-4">
          <span className="text-gray-500 text-sm">
            Showing {filteredSignals.length} of {signals.length} signals
          </span>
        </div>
      )}
    </div>
  );
};

export default FlowSignalsPanel;
