/**
 * Options Flow Dashboard
 * Main dashboard with tabs
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useEffect } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { RefreshCw, Settings, Filter, Download, Activity } from 'lucide-react';
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

// Mock data for demonstration
const generateMockData = () => {
  const symbols = ['SPY', 'AAPL', 'TSLA', 'NVDA', 'AMD', 'QQQ', 'META', 'GOOGL', 'AMZN', 'MSFT'];
  
  const unusualActivity: UnusualActivity[] = Array.from({ length: 50 }, (_, i) => ({
    id: `ua_${i}`,
    symbol: symbols[Math.floor(Math.random() * symbols.length)],
    timestamp: new Date(Date.now() - Math.random() * 3600000).toISOString(),
    optionType: Math.random() > 0.5 ? 'call' : 'put',
    strike: Math.floor(150 + Math.random() * 100),
    expiration: new Date(Date.now() + Math.random() * 30 * 24 * 3600000).toISOString(),
    premium: Math.floor(100000 + Math.random() * 5000000),
    volume: Math.floor(500 + Math.random() * 10000),
    openInterest: Math.floor(1000 + Math.random() * 50000),
    volumeOIRatio: 1 + Math.random() * 10,
    impliedVolatility: 0.2 + Math.random() * 0.6,
    delta: Math.random() * 0.8,
    flowType: ['sweep', 'block', 'split', 'regular'][Math.floor(Math.random() * 4)] as any,
    aggressor: ['buy', 'sell', 'mid'][Math.floor(Math.random() * 3)] as any,
    spot: 150 + Math.random() * 50,
    sentiment: ['bullish', 'bearish', 'neutral'][Math.floor(Math.random() * 3)] as any,
    unusualScore: 5 + Math.random() * 5,
    exchange: ['CBOE', 'NYSE', 'NASDAQ'][Math.floor(Math.random() * 3)],
  }));

  const gammaExposure: GammaExposureProfile = {
    symbol: 'SPY',
    spotPrice: 450,
    totalNetGamma: 1500000000,
    gammaFlip: 448,
    maxPainStrike: 445,
    levels: Array.from({ length: 30 }, (_, i) => ({
      strike: 420 + i * 2,
      callGamma: Math.random() * 1000000000,
      putGamma: -Math.random() * 1000000000,
      netGamma: (Math.random() - 0.5) * 2000000000,
      totalGamma: Math.random() * 2000000000,
      openInterest: Math.floor(10000 + Math.random() * 100000),
    })),
    zeroGammaLevel: 447,
    callWall: 460,
    putWall: 440,
    expectedMove: 0.02,
    timestamp: new Date().toISOString(),
  };

  const darkPoolPrints: DarkPoolPrint[] = Array.from({ length: 100 }, (_, i) => ({
    id: `dp_${i}`,
    symbol: symbols[Math.floor(Math.random() * symbols.length)],
    timestamp: new Date(Date.now() - Math.random() * 3600000).toISOString(),
    price: 150 + Math.random() * 100,
    size: Math.floor(1000 + Math.random() * 50000),
    notional: Math.floor(100000 + Math.random() * 10000000),
    exchange: 'DARK',
    condition: 'regular',
    aboveAsk: Math.random() > 0.6,
    belowBid: Math.random() > 0.7,
    blockTrade: Math.random() > 0.8,
    darkPoolType: ['dp', 'block', 'hidden'][Math.floor(Math.random() * 3)] as any,
  }));

  const darkPoolAccumulation: DarkPoolAccumulation[] = symbols.slice(0, 8).map(symbol => ({
    symbol,
    date: new Date().toISOString().split('T')[0],
    totalVolume: Math.floor(10000000 + Math.random() * 100000000),
    darkPoolVolume: Math.floor(1000000 + Math.random() * 50000000),
    darkPoolPct: 10 + Math.random() * 30,
    netAccumulation: (Math.random() - 0.5) * 10000000,
    avgPrice: 150 + Math.random() * 100,
    largestPrint: darkPoolPrints[0],
    prints: [],
  }));

  const institutionalFlow: InstitutionalFlow[] = Array.from({ length: 40 }, (_, i) => ({
    id: `if_${i}`,
    symbol: symbols[Math.floor(Math.random() * symbols.length)],
    timestamp: new Date(Date.now() - Math.random() * 7200000).toISOString(),
    flowType: Math.random() > 0.5 ? 'buy' : 'sell',
    size: Math.floor(10000 + Math.random() * 100000),
    notional: Math.floor(1000000 + Math.random() * 50000000),
    isBlock: Math.random() > 0.7,
    isSweep: Math.random() > 0.8,
    sentiment: ['bullish', 'bearish', 'neutral'][Math.floor(Math.random() * 3)] as any,
    confidence: 0.5 + Math.random() * 0.5,
  }));

  const smartMoneyMetrics: SmartMoneyMetrics[] = symbols.slice(0, 6).map(symbol => ({
    symbol,
    smartMoneyIndex: (Math.random() - 0.5) * 2,
    institutionalAccumulation: (Math.random() - 0.5) * 2,
    retailSentiment: ['bullish', 'bearish', 'neutral'][Math.floor(Math.random() * 3)] as any,
    smartMoneySentiment: ['bullish', 'bearish', 'neutral'][Math.floor(Math.random() * 3)] as any,
    divergence: (Math.random() - 0.5) * 0.8,
    flowImbalance: (Math.random() - 0.5) * 2,
    largeTraderActivity: Math.random(),
    timestamp: new Date().toISOString(),
  }));

  const flowSignals: FlowSignal[] = Array.from({ length: 15 }, (_, i) => ({
    id: `fs_${i}`,
    symbol: symbols[Math.floor(Math.random() * symbols.length)],
    timestamp: new Date(Date.now() - Math.random() * 1800000).toISOString(),
    signalType: ['unusual_activity', 'gamma_squeeze', 'dark_pool_block', 'smart_money_divergence', 'sweep_alert'][
      Math.floor(Math.random() * 5)
    ] as any,
    direction: ['bullish', 'bearish', 'neutral'][Math.floor(Math.random() * 3)] as any,
    strength: 0.3 + Math.random() * 0.7,
    description: `Significant ${Math.random() > 0.5 ? 'bullish' : 'bearish'} flow detected with unusual volume patterns.`,
    details: {
      premium: Math.floor(500000 + Math.random() * 2000000),
      volume: Math.floor(5000 + Math.random() * 20000),
      oi_ratio: (1 + Math.random() * 5).toFixed(1),
    },
    alertLevel: ['info', 'warning', 'critical'][Math.floor(Math.random() * 3)] as any,
  }));

  return {
    unusualActivity,
    gammaExposure,
    darkPoolPrints,
    darkPoolAccumulation,
    institutionalFlow,
    smartMoneyMetrics,
    flowSignals,
  };
};

interface OptionsFlowDashboardProps {
  symbol?: string;
}

export const OptionsFlowDashboard: React.FC<OptionsFlowDashboardProps> = ({ symbol = 'SPY' }) => {
  const [activeTab, setActiveTab] = useState('unusual');
  const [selectedSymbol, setSelectedSymbol] = useState(symbol);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [data, setData] = useState(generateMockData());
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500));
    setData(generateMockData());
    setLastUpdate(new Date());
    setIsRefreshing(false);
  };

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(handleRefresh, 30000);
    return () => clearInterval(interval);
  }, []);

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
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition"
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

        {/* Main Content */}
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
                <UnusualActivityTable 
                  data={data.unusualActivity.filter(
                    a => selectedSymbol === 'ALL' || a.symbol === selectedSymbol || selectedSymbol === 'SPY'
                  )}
                  onRowClick={(activity) => console.log('Clicked:', activity)}
                />
              </Tabs.Content>

              <Tabs.Content value="gex">
                <GammaExposureChart data={data.gammaExposure} height={600} />
              </Tabs.Content>

              <Tabs.Content value="darkpool">
                <DarkPoolMonitor
                  prints={data.darkPoolPrints}
                  accumulation={data.darkPoolAccumulation}
                  selectedSymbol={selectedSymbol}
                />
              </Tabs.Content>

              <Tabs.Content value="smartmoney">
                <SmartMoneyTracker
                  flow={data.institutionalFlow}
                  metrics={data.smartMoneyMetrics}
                />
              </Tabs.Content>
            </div>

            {/* Side Panel - Signals */}
            <div className="lg:col-span-1">
              <FlowSignalsPanel
                signals={data.flowSignals}
                onSignalClick={(signal) => {
                  console.log('Signal clicked:', signal);
                  if (signal.symbol) setSelectedSymbol(signal.symbol);
                }}
              />
            </div>
          </div>
        </Tabs.Root>
      </div>
    </div>
  );
};

export default OptionsFlowDashboard;
