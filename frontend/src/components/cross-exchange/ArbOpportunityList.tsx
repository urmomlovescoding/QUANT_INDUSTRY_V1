/**
 * Arb Opportunity List
 * Active arbitrage opportunities
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useMemo } from 'react';
import { ArbOpportunity } from '@/types/cross-exchange';

interface ArbOpportunityListProps {
  opportunities: ArbOpportunity[];
  onExecute?: (opportunity: ArbOpportunity) => void;
  onDismiss?: (id: string) => void;
}

const RiskBadge: React.FC<{ risk: 'low' | 'medium' | 'high' }> = ({ risk }) => {
  const config = {
    low: { bg: 'bg-green-500/20', text: 'text-green-400' },
    medium: { bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
    high: { bg: 'bg-red-500/20', text: 'text-red-400' },
  };
  const { bg, text } = config[risk];
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      {risk.toUpperCase()}
    </span>
  );
};

const TypeBadge: React.FC<{ type: string }> = ({ type }) => {
  const config: Record<string, { bg: string; text: string }> = {
    simple: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
    triangular: { bg: 'bg-purple-500/20', text: 'text-purple-400' },
    statistical: { bg: 'bg-cyan-500/20', text: 'text-cyan-400' },
    cex_dex: { bg: 'bg-orange-500/20', text: 'text-orange-400' },
  };
  const { bg, text } = config[type] || { bg: 'bg-gray-500/20', text: 'text-gray-400' };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      {type.toUpperCase().replace('_', '-')}
    </span>
  );
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const config: Record<string, { bg: string; text: string; pulse?: boolean }> = {
    pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
    executing: { bg: 'bg-blue-500/20', text: 'text-blue-400', pulse: true },
    completed: { bg: 'bg-green-500/20', text: 'text-green-400' },
    failed: { bg: 'bg-red-500/20', text: 'text-red-400' },
    expired: { bg: 'bg-gray-500/20', text: 'text-gray-400' },
  };
  const { bg, text, pulse } = config[status] || config.pending;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text} ${pulse ? 'animate-pulse' : ''}`}>
      {status.toUpperCase()}
    </span>
  );
};

const formatCurrency = (value: number): string => {
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
};

const ProgressBar: React.FC<{ expiresIn: number; maxTime: number }> = ({ expiresIn, maxTime }) => {
  const pct = Math.max(0, Math.min(100, (expiresIn / maxTime) * 100));
  const getColor = () => {
    if (pct > 60) return 'bg-green-500';
    if (pct > 30) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="w-full h-1 bg-gray-700 rounded-full overflow-hidden">
      <div className={`h-full ${getColor()} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
};

const OpportunityCard: React.FC<{
  opp: ArbOpportunity;
  onExecute: () => void;
  onDismiss: () => void;
}> = ({ opp, onExecute, onDismiss }) => (
  <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700/50 hover:border-gray-600 transition-all">
    <div className="flex justify-between items-start mb-3">
      <div className="flex items-center gap-2">
        <span className="text-white font-bold text-lg">{opp.symbol}</span>
        <TypeBadge type={opp.type} />
        <StatusBadge status={opp.status} />
      </div>
      <RiskBadge risk={opp.risk} />
    </div>

    <div className="grid grid-cols-2 gap-4 mb-3">
      <div className="bg-gray-800/50 rounded p-2">
        <p className="text-gray-500 text-xs">Buy @ {opp.buyExchange}</p>
        <p className="text-green-400 font-medium">${opp.buyPrice.toFixed(4)}</p>
      </div>
      <div className="bg-gray-800/50 rounded p-2">
        <p className="text-gray-500 text-xs">Sell @ {opp.sellExchange}</p>
        <p className="text-red-400 font-medium">${opp.sellPrice.toFixed(4)}</p>
      </div>
    </div>

    <div className="grid grid-cols-4 gap-2 text-center mb-3">
      <div>
        <p className="text-gray-500 text-[10px]">Spread</p>
        <p className="text-white font-medium text-sm">{(opp.spreadPct * 100).toFixed(2)}%</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">Profit Est</p>
        <p className="text-green-400 font-medium text-sm">{formatCurrency(opp.profitEstimate)}</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">After Fees</p>
        <p className={`font-medium text-sm ${opp.profitAfterFees > 0 ? 'text-green-400' : 'text-red-400'}`}>
          {formatCurrency(opp.profitAfterFees)}
        </p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">Confidence</p>
        <p className="text-blue-400 font-medium text-sm">{(opp.confidence * 100).toFixed(0)}%</p>
      </div>
    </div>

    <div className="mb-3">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Time remaining</span>
        <span>{opp.expiresIn}s</span>
      </div>
      <ProgressBar expiresIn={opp.expiresIn} maxTime={opp.executionWindow} />
    </div>

    <div className="flex gap-2">
      <button
        onClick={onExecute}
        disabled={opp.status !== 'pending' || opp.profitAfterFees <= 0}
        className="flex-1 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-500 rounded font-medium text-sm transition-colors"
      >
        Execute
      </button>
      <button
        onClick={onDismiss}
        className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
      >
        Dismiss
      </button>
    </div>
  </div>
);

export const ArbOpportunityList: React.FC<ArbOpportunityListProps> = ({
  opportunities,
  onExecute,
  onDismiss,
}) => {
  const [filter, setFilter] = useState<'all' | 'profitable'>('profitable');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const types = useMemo(() => {
    const t = new Set(opportunities.map(o => o.type));
    return ['all', ...Array.from(t)];
  }, [opportunities]);

  const filteredOpps = useMemo(() => {
    return opportunities
      .filter(o => filter === 'all' || o.profitAfterFees > 0)
      .filter(o => typeFilter === 'all' || o.type === typeFilter)
      .sort((a, b) => b.profitAfterFees - a.profitAfterFees);
  }, [opportunities, filter, typeFilter]);

  const stats = useMemo(() => ({
    total: opportunities.length,
    profitable: opportunities.filter(o => o.profitAfterFees > 0).length,
    totalProfit: opportunities.reduce((sum, o) => sum + Math.max(0, o.profitAfterFees), 0),
  }), [opportunities]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Arbitrage Opportunities</h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-green-400">{stats.profitable} profitable</span>
          <span className="text-gray-500">|</span>
          <span className="text-gray-400">{formatCurrency(stats.totalProfit)} total</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        <div className="flex gap-1 bg-gray-900/50 rounded-lg p-1">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              filter === 'all' ? 'bg-gray-700 text-white' : 'text-gray-400'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('profitable')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              filter === 'profitable' ? 'bg-gray-700 text-white' : 'text-gray-400'
            }`}
          >
            Profitable
          </button>
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-gray-900 text-gray-300 text-xs rounded-lg px-3 py-1 border border-gray-700"
        >
          {types.map(type => (
            <option key={type} value={type}>
              {type === 'all' ? 'All Types' : type.toUpperCase()}
            </option>
          ))}
        </select>
      </div>

      {/* Opportunities Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 max-h-[600px] overflow-y-auto">
        {filteredOpps.length === 0 ? (
          <div className="col-span-2 text-center py-12 text-gray-500">
            No opportunities match your filters
          </div>
        ) : (
          filteredOpps.map(opp => (
            <OpportunityCard
              key={opp.id}
              opp={opp}
              onExecute={() => onExecute?.(opp)}
              onDismiss={() => onDismiss?.(opp.id)}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default ArbOpportunityList;
