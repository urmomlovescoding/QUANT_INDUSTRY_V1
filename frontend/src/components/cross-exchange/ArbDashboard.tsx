/**
 * Arb Dashboard
 * Main arbitrage dashboard
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useEffect } from 'react';
import { RefreshCw, Settings, Zap, TrendingUp, Unplug } from 'lucide-react';
import { PriceMatrixTable } from './PriceMatrixTable';
import { ArbOpportunityList } from './ArbOpportunityList';
import { TriangularArbVisualizer } from './TriangularArbVisualizer';
import { CexDexSpreadChart } from './CexDexSpreadChart';
import { LatencyMonitor } from './LatencyMonitor';
import { ExecutionLog } from './ExecutionLog';
import {
  PriceMatrix,
  ArbOpportunity,
  TriangularArbPath,
  CexDexSpread,
  CexDexSpreadHistory,
  ExchangeLatency,
  ArbExecution,
} from '@/types/cross-exchange';

export interface ArbDashboardData {
  priceMatrices: PriceMatrix[];
  opportunities: ArbOpportunity[];
  triangularPaths: TriangularArbPath[];
  cexDexSpread: CexDexSpread | null;
  spreadHistory: CexDexSpreadHistory | null;
  latencies: ExchangeLatency[];
  executions: ArbExecution[];
}

interface ArbDashboardProps {
  data?: ArbDashboardData;
  onRefresh?: () => void;
}

const emptyData: ArbDashboardData = {
  priceMatrices: [],
  opportunities: [],
  triangularPaths: [],
  cexDexSpread: null,
  spreadHistory: null,
  latencies: [],
  executions: [],
};

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Unplug className="w-12 h-12 text-gray-600 mb-4" />
      <h3 className="text-lg font-semibold text-gray-300 mb-2">No Arbitrage Data</h3>
      <p className="text-sm text-gray-500 max-w-md">
        Connect exchange APIs to monitor cross-exchange arbitrage opportunities.
      </p>
    </div>
  );
}

export const ArbDashboard: React.FC<ArbDashboardProps> = ({
  data: propData,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState('opportunities');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdate] = useState(new Date());

  const data = propData || emptyData;

  const hasData =
    data.opportunities.length > 0 ||
    data.priceMatrices.length > 0 ||
    data.executions.length > 0;

  const handleRefresh = async () => {
    if (!onRefresh) return;
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 300);
  };

  const stats = {
    activeOpps: data.opportunities.filter(o => o.profitAfterFees > 0).length,
    totalProfit: data.executions.reduce((sum, e) => sum + Math.max(0, e.netProfit), 0),
    successRate: data.executions.length > 0
      ? data.executions.filter(e => e.status === 'success').length / data.executions.length
      : 0,
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4">
      <div className="max-w-[1800px] mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Zap className="w-6 h-6 text-yellow-400" />
              <h1 className="text-2xl font-bold">Cross-Exchange Arbitrage</h1>
            </div>
            {hasData && (
              <div className="flex items-center gap-3 text-sm">
                <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full">
                  {stats.activeOpps} active opps
                </span>
                <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full">
                  ${stats.totalProfit.toFixed(0)} profit
                </span>
                <span className="px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full">
                  {(stats.successRate * 100).toFixed(0)}% success
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-gray-400 text-sm">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
            <button
              onClick={handleRefresh}
              disabled={isRefreshing || !onRefresh}
              className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {!hasData ? (
          <EmptyState />
        ) : (
          /* Tabs */
          <div>
            <div className="flex gap-1 bg-gray-800 p-1 rounded-lg mb-6">
              {[
                { value: 'opportunities', label: 'Opportunities' },
                { value: 'prices', label: 'Price Matrix' },
                { value: 'triangular', label: 'Triangular' },
                { value: 'cexdex', label: 'CEX-DEX' },
                { value: 'latency', label: 'Latency' },
                { value: 'history', label: 'Execution Log' },
              ].map(tab => (
                <button
                  key={tab.value}
                  onClick={() => setActiveTab(tab.value)}
                  className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                    activeTab === tab.value ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'opportunities' && (
              data.opportunities.length > 0 ? (
                <ArbOpportunityList
                  opportunities={data.opportunities}
                  onExecute={() => {}}
                  onDismiss={() => {}}
                />
              ) : (
                <EmptyState />
              )
            )}
            {activeTab === 'prices' && (
              data.priceMatrices.length > 0 ? (
                <PriceMatrixTable data={data.priceMatrices} />
              ) : (
                <EmptyState />
              )
            )}
            {activeTab === 'triangular' && (
              data.triangularPaths.length > 0 ? (
                <TriangularArbVisualizer paths={data.triangularPaths} />
              ) : (
                <EmptyState />
              )
            )}
            {activeTab === 'cexdex' && (
              data.cexDexSpread && data.spreadHistory ? (
                <CexDexSpreadChart
                  currentSpread={data.cexDexSpread}
                  history={data.spreadHistory}
                  symbol="ETH/USD"
                />
              ) : (
                <EmptyState />
              )
            )}
            {activeTab === 'latency' && (
              data.latencies.length > 0 ? (
                <LatencyMonitor latencies={data.latencies} />
              ) : (
                <EmptyState />
              )
            )}
            {activeTab === 'history' && (
              data.executions.length > 0 ? (
                <ExecutionLog executions={data.executions} />
              ) : (
                <EmptyState />
              )
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ArbDashboard;
