/**
 * Microstructure Dashboard
 * Main dashboard for market microstructure analysis
 * QUANT_INDUSTRY_V1
 */

import React, { useState } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { RefreshCw, Settings, Layers, Unplug } from 'lucide-react';
import { OrderBookHeatmap } from './OrderBookHeatmap';
import { ImbalanceIndicator } from './ImbalanceIndicator';
import { TapeReader } from './TapeReader';
import { FlowModelMetrics } from './FlowModelMetrics';
import { BacktestResults } from './BacktestResults';
import {
  OrderBook,
  ImbalanceMetrics,
  TapeEntry,
  TapeAnalysis,
  FlowModelMetrics as FlowModelMetricsType,
  OrderFlowBacktestResult,
} from '@/types/microstructure';

export interface MicrostructureData {
  orderBook: OrderBook | null;
  imbalanceMetrics: ImbalanceMetrics | null;
  tapeEntries: TapeEntry[];
  tapeAnalysis: TapeAnalysis | null;
  flowModelMetrics: FlowModelMetricsType[];
  backtestResults: OrderFlowBacktestResult[];
}

interface MicrostructureDashboardProps {
  symbol?: string;
  data?: MicrostructureData;
  onRefresh?: () => void;
}

const emptyData: MicrostructureData = {
  orderBook: null,
  imbalanceMetrics: null,
  tapeEntries: [],
  tapeAnalysis: null,
  flowModelMetrics: [],
  backtestResults: [],
};

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Unplug className="w-12 h-12 text-gray-600 mb-4" />
      <h3 className="text-lg font-semibold text-gray-300 mb-2">No Microstructure Data</h3>
      <p className="text-sm text-gray-500 max-w-md">
        Connect to a real-time data feed to view order book, time and sales, and flow model analytics.
      </p>
    </div>
  );
}

export const MicrostructureDashboard: React.FC<MicrostructureDashboardProps> = ({
  symbol = 'SPY',
  data: propData,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState('orderbook');
  const [selectedSymbol, setSelectedSymbol] = useState(symbol);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdate] = useState(new Date());

  const data = propData || emptyData;

  const hasData =
    data.orderBook !== null ||
    data.tapeEntries.length > 0 ||
    data.flowModelMetrics.length > 0 ||
    data.backtestResults.length > 0;

  const handleRefresh = async () => {
    if (!onRefresh) return;
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 300);
  };

  const quickSymbols = ['SPY', 'QQQ', 'IWM', 'ES', 'NQ', 'AAPL', 'TSLA'];

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4">
      <div className="max-w-[1800px] mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Layers className="w-6 h-6 text-purple-400" />
              <h1 className="text-2xl font-bold">Market Microstructure</h1>
            </div>
            <div className="flex gap-2">
              {quickSymbols.map(s => (
                <button
                  key={s}
                  onClick={() => setSelectedSymbol(s)}
                  className={`px-3 py-1 rounded text-sm font-medium transition ${
                    selectedSymbol === s
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
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
          <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
            <Tabs.List className="flex gap-1 bg-gray-800 p-1 rounded-lg mb-6">
              <Tabs.Trigger
                value="orderbook"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'orderbook' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Order Book
              </Tabs.Trigger>
              <Tabs.Trigger
                value="tape"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'tape' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Time & Sales
              </Tabs.Trigger>
              <Tabs.Trigger
                value="models"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'models' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Flow Models
              </Tabs.Trigger>
              <Tabs.Trigger
                value="backtest"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'backtest' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Backtest
              </Tabs.Trigger>
            </Tabs.List>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main Content */}
              <div className="lg:col-span-2">
                <Tabs.Content value="orderbook">
                  {data.orderBook ? (
                    <OrderBookHeatmap data={data.orderBook} />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>

                <Tabs.Content value="tape">
                  {data.tapeEntries.length > 0 && data.tapeAnalysis ? (
                    <TapeReader
                      entries={data.tapeEntries}
                      analysis={data.tapeAnalysis}
                    />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>

                <Tabs.Content value="models">
                  {data.flowModelMetrics.length > 0 ? (
                    <FlowModelMetrics metrics={data.flowModelMetrics} />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>

                <Tabs.Content value="backtest">
                  {data.backtestResults.length > 0 ? (
                    <BacktestResults results={data.backtestResults} />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>
              </div>

              {/* Side Panel - Imbalance */}
              <div className="lg:col-span-1">
                {data.imbalanceMetrics ? (
                  <ImbalanceIndicator data={data.imbalanceMetrics} />
                ) : (
                  <div className="card p-6 text-center text-gray-500 text-sm">
                    No imbalance data available
                  </div>
                )}
              </div>
            </div>
          </Tabs.Root>
        )}
      </div>
    </div>
  );
};

export default MicrostructureDashboard;
