/**
 * Options Flow Dashboard
 * Main dashboard with tabs
 * QUANT_INDUSTRY_V1
 */

import React, { useState } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { RefreshCw, Settings, Filter, Download, Activity, Unplug } from 'lucide-react';
import { UnusualActivityTable } from './UnusualActivityTable';
import { GammaExposureChart } from './GammaExposureChart';
import { DarkPoolMonitor } from './DarkPoolMonitor';
import { SmartMoneyTracker } from './SmartMoneyTracker';
import { FlowSignalsPanel } from './FlowSignalsPanel';
import {
  UnusualActivity,
  GammaExposureProfile,
  DarkPoolPrint,
  DarkPoolAccumulation,
  InstitutionalFlow,
  SmartMoneyMetrics,
  FlowSignal,
} from '@/types/options-flow';

export interface OptionsFlowData {
  unusualActivity: UnusualActivity[];
  gammaExposure: GammaExposureProfile | null;
  darkPoolPrints: DarkPoolPrint[];
  darkPoolAccumulation: DarkPoolAccumulation[];
  institutionalFlow: InstitutionalFlow[];
  smartMoneyMetrics: SmartMoneyMetrics[];
  flowSignals: FlowSignal[];
}

interface OptionsFlowDashboardProps {
  symbol?: string;
  data?: OptionsFlowData;
  onRefresh?: () => void;
}

const emptyData: OptionsFlowData = {
  unusualActivity: [],
  gammaExposure: null,
  darkPoolPrints: [],
  darkPoolAccumulation: [],
  institutionalFlow: [],
  smartMoneyMetrics: [],
  flowSignals: [],
};

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Unplug className="w-12 h-12 text-gray-600 mb-4" />
      <h3 className="text-lg font-semibold text-gray-300 mb-2">No Options Flow Data</h3>
      <p className="text-sm text-gray-500 max-w-md">
        Connect to an options data provider to view unusual activity, gamma exposure, dark pool prints, and smart money flow.
      </p>
    </div>
  );
}

export const OptionsFlowDashboard: React.FC<OptionsFlowDashboardProps> = ({
  symbol = 'SPY',
  data: propData,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState('unusual');
  const [selectedSymbol, setSelectedSymbol] = useState(symbol);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdate] = useState(new Date());

  const data = propData || emptyData;

  const hasData =
    data.unusualActivity.length > 0 ||
    data.gammaExposure !== null ||
    data.darkPoolPrints.length > 0 ||
    data.institutionalFlow.length > 0;

  const handleRefresh = async () => {
    if (!onRefresh) return;
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const quickSymbols = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'AMD'];

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4">
      <div className="max-w-[1800px] mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Activity className="w-6 h-6 text-blue-400" />
              <h1 className="text-2xl font-bold">Options Flow</h1>
            </div>
            <div className="flex gap-2">
              {quickSymbols.map(s => (
                <button
                  key={s}
                  onClick={() => setSelectedSymbol(s)}
                  className={`px-3 py-1 rounded text-sm font-medium transition ${
                    selectedSymbol === s
                      ? 'bg-blue-600 text-white'
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
              <Filter className="w-4 h-4" />
            </button>
            <button className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg">
              <Download className="w-4 h-4" />
            </button>
            <button className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {!hasData ? (
          <EmptyState />
        ) : (
          /* Main Content */
          <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
            <Tabs.List className="flex gap-1 bg-gray-800 p-1 rounded-lg mb-6">
              <Tabs.Trigger
                value="unusual"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'unusual' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Unusual Activity
              </Tabs.Trigger>
              <Tabs.Trigger
                value="gex"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'gex' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Gamma Exposure
              </Tabs.Trigger>
              <Tabs.Trigger
                value="darkpool"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'darkpool' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Dark Pool
              </Tabs.Trigger>
              <Tabs.Trigger
                value="smartmoney"
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === 'smartmoney' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                Smart Money
              </Tabs.Trigger>
            </Tabs.List>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              {/* Main Content Area */}
              <div className="lg:col-span-3">
                <Tabs.Content value="unusual" className="h-[600px]">
                  {data.unusualActivity.length > 0 ? (
                    <UnusualActivityTable
                      data={data.unusualActivity.filter(
                        a => selectedSymbol === 'ALL' || a.symbol === selectedSymbol || selectedSymbol === 'SPY'
                      )}
                      onRowClick={() => {}}
                    />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>

                <Tabs.Content value="gex">
                  {data.gammaExposure ? (
                    <GammaExposureChart data={data.gammaExposure} height={600} />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>

                <Tabs.Content value="darkpool">
                  {data.darkPoolPrints.length > 0 ? (
                    <DarkPoolMonitor
                      prints={data.darkPoolPrints}
                      accumulation={data.darkPoolAccumulation}
                      selectedSymbol={selectedSymbol}
                    />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>

                <Tabs.Content value="smartmoney">
                  {data.institutionalFlow.length > 0 ? (
                    <SmartMoneyTracker
                      flow={data.institutionalFlow}
                      metrics={data.smartMoneyMetrics}
                    />
                  ) : (
                    <EmptyState />
                  )}
                </Tabs.Content>
              </div>

              {/* Side Panel - Signals */}
              <div className="lg:col-span-1">
                {data.flowSignals.length > 0 ? (
                  <FlowSignalsPanel
                    signals={data.flowSignals}
                    onSignalClick={(signal) => {
                      if (signal.symbol) setSelectedSymbol(signal.symbol);
                    }}
                  />
                ) : (
                  <div className="card p-6 text-center text-gray-500 text-sm">
                    No flow signals available
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

export default OptionsFlowDashboard;
