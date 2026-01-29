/**
 * Execution Log
 * Arb execution history
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useMemo } from 'react';
import { ArbExecution } from '@/types/cross-exchange';

interface ExecutionLogProps {
  executions: ArbExecution[];
  onExecutionSelect?: (execution: ArbExecution) => void;
}

const formatCurrency = (value: number): string => {
  const prefix = value >= 0 ? '+' : '';
  if (Math.abs(value) >= 1e6) return `${prefix}$${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `${prefix}$${(value / 1e3).toFixed(1)}K`;
  return `${prefix}$${value.toFixed(2)}`;
};

const StatusBadge: React.FC<{ status: 'success' | 'partial' | 'failed' }> = ({ status }) => {
  const config = {
    success: { bg: 'bg-green-500/20', text: 'text-green-400', icon: '✓' },
    partial: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', icon: '◐' },
    failed: { bg: 'bg-red-500/20', text: 'text-red-400', icon: '✗' },
  };
  const { bg, text, icon } = config[status];
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      {icon} {status.toUpperCase()}
    </span>
  );
};

const TypeBadge: React.FC<{ type: string }> = ({ type }) => {
  const colors: Record<string, string> = {
    simple: 'bg-blue-500/20 text-blue-400',
    triangular: 'bg-purple-500/20 text-purple-400',
    statistical: 'bg-cyan-500/20 text-cyan-400',
    cex_dex: 'bg-orange-500/20 text-orange-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[type] || 'bg-gray-500/20 text-gray-400'}`}>
      {type.toUpperCase().replace('_', '-')}
    </span>
  );
};

const SlippageIndicator: React.FC<{ slippagePct: number }> = ({ slippagePct }) => {
  const absSlippage = Math.abs(slippagePct);
  const color = absSlippage < 0.1 ? 'text-green-400' : 
                absSlippage < 0.3 ? 'text-yellow-400' : 'text-red-400';
  return (
    <span className={color}>
      {slippagePct > 0 ? '+' : ''}{(slippagePct * 100).toFixed(3)}%
    </span>
  );
};

const ExecutionRow: React.FC<{
  execution: ArbExecution;
  onClick: () => void;
}> = ({ execution, onClick }) => (
  <tr 
    className="border-b border-gray-700/50 hover:bg-gray-700/30 cursor-pointer"
    onClick={onClick}
  >
    <td className="p-3">
      <div className="flex flex-col">
        <span className="text-gray-300 text-xs">
          {new Date(execution.timestamp).toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })}
        </span>
        <span className="text-gray-500 text-[10px]">{execution.id.slice(0, 8)}...</span>
      </div>
    </td>
    <td className="p-3">
      <div className="flex items-center gap-2">
        <span className="text-white font-medium">{execution.symbol}</span>
        <TypeBadge type={execution.type} />
      </div>
    </td>
    <td className="p-3">
      <div className="flex flex-col text-xs">
        <span className="text-green-400">
          Buy: {execution.buyExchange} @ ${execution.actualBuyPrice.toFixed(2)}
        </span>
        <span className="text-red-400">
          Sell: {execution.sellExchange} @ ${execution.actualSellPrice.toFixed(2)}
        </span>
      </div>
    </td>
    <td className="p-3 text-center">
      <StatusBadge status={execution.status} />
    </td>
    <td className="p-3 text-right">
      <SlippageIndicator slippagePct={execution.slippagePct} />
    </td>
    <td className="p-3 text-right">
      <div className="flex flex-col">
        <span className={`font-medium ${execution.netProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {formatCurrency(execution.netProfit)}
        </span>
        <span className="text-gray-500 text-xs">
          Fees: ${execution.fees.toFixed(2)}
        </span>
      </div>
    </td>
    <td className="p-3 text-right text-gray-400 text-xs">
      {execution.executionTimeMs}ms
    </td>
  </tr>
);

const ExecutionDetails: React.FC<{ execution: ArbExecution; onClose: () => void }> = ({ execution, onClose }) => (
  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
    <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-white font-bold text-lg">{execution.symbol} Execution</h3>
          <p className="text-gray-500 text-sm">{execution.id}</p>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs mb-1">Expected Profit</p>
          <p className="text-white font-medium">{formatCurrency(execution.expectedProfit)}</p>
        </div>
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs mb-1">Actual Profit</p>
          <p className={`font-medium ${execution.actualProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(execution.actualProfit)}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-gray-400 text-sm font-medium">Execution Legs</p>
        {execution.legs.map((leg, i) => (
          <div key={i} className="bg-gray-900/50 rounded p-3 flex justify-between items-center">
            <div>
              <span className={leg.side === 'buy' ? 'text-green-400' : 'text-red-400'}>
                {leg.side.toUpperCase()}
              </span>
              <span className="text-gray-400 ml-2">@ {leg.exchange}</span>
            </div>
            <div className="text-right">
              <p className="text-white">${leg.avgPrice.toFixed(4)}</p>
              <p className="text-gray-500 text-xs">
                {leg.filledQty} filled | {leg.latencyMs}ms | 
                <span className={
                  leg.status === 'filled' ? 'text-green-400' : 
                  leg.status === 'partial' ? 'text-yellow-400' : 'text-red-400'
                }>
                  {' '}{leg.status}
                </span>
              </p>
            </div>
          </div>
        ))}
      </div>

      {execution.errorMessage && (
        <div className="mt-4 bg-red-500/10 border border-red-500/30 rounded p-3">
          <p className="text-red-400 text-sm">{execution.errorMessage}</p>
        </div>
      )}
    </div>
  </div>
);

export const ExecutionLog: React.FC<ExecutionLogProps> = ({
  executions,
  onExecutionSelect,
}) => {
  const [selectedExecution, setSelectedExecution] = useState<ArbExecution | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'partial' | 'failed'>('all');

  const filteredExecutions = useMemo(() => {
    return executions
      .filter(e => statusFilter === 'all' || e.status === statusFilter)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [executions, statusFilter]);

  const stats = useMemo(() => ({
    total: executions.length,
    success: executions.filter(e => e.status === 'success').length,
    totalProfit: executions.reduce((sum, e) => sum + e.netProfit, 0),
    avgSlippage: executions.length > 0 
      ? executions.reduce((sum, e) => sum + Math.abs(e.slippagePct), 0) / executions.length 
      : 0,
  }), [executions]);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Execution Log</h3>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-400">{stats.total} executions</span>
          <span className="text-green-400">{stats.success} successful</span>
          <span className={stats.totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}>
            {formatCurrency(stats.totalProfit)} total
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-1 bg-gray-900/50 rounded-lg p-1 mb-4 w-fit">
        {(['all', 'success', 'partial', 'failed'] as const).map(status => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              statusFilter === status ? 'bg-gray-700 text-white' : 'text-gray-400'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-800">
            <tr className="text-gray-400 text-xs border-b border-gray-700">
              <th className="text-left p-3">Time</th>
              <th className="text-left p-3">Symbol</th>
              <th className="text-left p-3">Route</th>
              <th className="text-center p-3">Status</th>
              <th className="text-right p-3">Slippage</th>
              <th className="text-right p-3">P&L</th>
              <th className="text-right p-3">Exec Time</th>
            </tr>
          </thead>
          <tbody>
            {filteredExecutions.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-gray-500">
                  No executions match your filter
                </td>
              </tr>
            ) : (
              filteredExecutions.map(execution => (
                <ExecutionRow
                  key={execution.id}
                  execution={execution}
                  onClick={() => setSelectedExecution(execution)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Details Modal */}
      {selectedExecution && (
        <ExecutionDetails 
          execution={selectedExecution} 
          onClose={() => setSelectedExecution(null)} 
        />
      )}
    </div>
  );
};

export default ExecutionLog;
