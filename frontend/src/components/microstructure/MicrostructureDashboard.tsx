/**
 * Microstructure Dashboard
 * Main dashboard for market microstructure analysis
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useEffect } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { RefreshCw, Settings, Activity, Layers } from 'lucide-react';
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

// Mock data generator
const generateMockData = () => {
  const orderBook: OrderBook = {
    symbol: 'SPY',
    timestamp: new Date().toISOString(),
    bids: Array.from({ length: 20 }, (_, i) => ({
      price: 450 - i * 0.05,
      size: Math.floor(5000 + Math.random() * 20000),
      orders: Math.floor(10 + Math.random() * 50),
      side: 'bid' as const,
      cumulative: 0,
    })),
    asks: Array.from({ length: 20 }, (_, i) => ({
      price: 450.05 + i * 0.05,
      size: Math.floor(5000 + Math.random() * 20000),
      orders: Math.floor(10 + Math.random() * 50),
      side: 'ask' as const,
      cumulative: 0,
    })),
    midPrice: 450.025,
    spread: 0.05,
    spreadBps: 1.1,
    imbalance: (Math.random() - 0.5) * 0.4,
    depth: {
      bid1Pct: 0.3 + Math.random() * 0.2,
      ask1Pct: 0.3 + Math.random() * 0.2,
      bid5Pct: 0.5 + Math.random() * 0.3,
      ask5Pct: 0.5 + Math.random() * 0.3,
    },
  };

  const imbalanceMetrics: ImbalanceMetrics = {
    symbol: 'SPY',
    timestamp: new Date().toISOString(),
    volumeImbalance: (Math.random() - 0.5) * 1.2,
    orderImbalance: (Math.random() - 0.5) * 1.0,
    tradeImbalance: (Math.random() - 0.5) * 0.8,
    vwapImbalance: (Math.random() - 0.5) * 0.6,
    direction: Math.random() > 0.6 ? 'buy' : Math.random() > 0.3 ? 'sell' : 'neutral',
    confidence: 0.5 + Math.random() * 0.5,
    predictedMove: (Math.random() - 0.5) * 0.02,
    historicalAccuracy: 0.55 + Math.random() * 0.25,
  };

  const tapeEntries: TapeEntry[] = Array.from({ length: 200 }, (_, i) => ({
    id: `tape_${i}`,
    symbol: 'SPY',
    timestamp: new Date(Date.now() - i * 50).toISOString(),
    price: 450 + (Math.random() - 0.5) * 0.2,
    size: Math.floor(100 + Math.random() * 5000),
    side: ['buy', 'sell', 'unknown'][Math.floor(Math.random() * 3)] as any,
    exchange: ['NYSE', 'ARCA', 'EDGX', 'BATS'][Math.floor(Math.random() * 4)],
    condition: 'regular',
    isBlock: Math.random() > 0.95,
    isSweep: Math.random() > 0.98,
    direction: ['uptick', 'downtick', 'zero'][Math.floor(Math.random() * 3)] as any,
    aggressorSide: ['buyer', 'seller', 'unknown'][Math.floor(Math.random() * 3)] as any,
  }));

  const tapeAnalysis: TapeAnalysis = {
    symbol: 'SPY',
    period: '5m',
    totalVolume: 5000000,
    buyVolume: 2500000 + Math.floor(Math.random() * 1000000),
    sellVolume: 2000000 + Math.floor(Math.random() * 800000),
    unknownVolume: 500000,
    vwap: 450.12,
    twap: 450.08,
    volumeProfile: Array.from({ length: 10 }, (_, i) => ({
      price: 449.5 + i * 0.1,
      volume: Math.floor(100000 + Math.random() * 500000),
      buyVolume: Math.floor(50000 + Math.random() * 200000),
      sellVolume: Math.floor(50000 + Math.random() * 200000),
    })),
    largestTrades: tapeEntries.slice(0, 5),
    tradeVelocity: 50 + Math.random() * 100,
  };

  const flowModelMetrics: FlowModelMetricsType[] = [
    {
      modelId: 'flow_lstm_v2',
      modelName: 'LSTM Flow Predictor',
      accuracy: 0.68,
      precision: 0.72,
      recall: 0.65,
      f1Score: 0.68,
      sharpeRatio: 1.85,
      hitRate: 0.58,
      avgPredictedMove: 0.0012,
      avgActualMove: 0.0008,
      mse: 0.0001,
      trainingDate: '2024-01-15',
      validationPeriod: '2024-01-01 to 2024-01-14',
      confusionMatrix: {
        truePositive: 420,
        falsePositive: 180,
        trueNegative: 350,
        falseNegative: 250,
      },
      performanceByRegime: {
        trending: { accuracy: 0.75, samples: 400 },
        ranging: { accuracy: 0.62, samples: 500 },
        volatile: { accuracy: 0.58, samples: 300 },
      },
    },
    {
      modelId: 'imbalance_xgb_v1',
      modelName: 'XGBoost Imbalance',
      accuracy: 0.64,
      precision: 0.68,
      recall: 0.61,
      f1Score: 0.64,
      sharpeRatio: 1.45,
      hitRate: 0.55,
      avgPredictedMove: 0.0015,
      avgActualMove: 0.0010,
      mse: 0.00015,
      trainingDate: '2024-01-10',
      validationPeriod: '2024-01-01 to 2024-01-09',
      confusionMatrix: {
        truePositive: 380,
        falsePositive: 200,
        trueNegative: 320,
        falseNegative: 300,
      },
      performanceByRegime: {
        trending: { accuracy: 0.70, samples: 380 },
        ranging: { accuracy: 0.60, samples: 520 },
        volatile: { accuracy: 0.55, samples: 300 },
      },
    },
  ];

  const backtestResults: OrderFlowBacktestResult[] = [
    {
      id: 'bt_1',
      strategyName: 'Imbalance Mean Reversion',
      startDate: '2023-01-01',
      endDate: '2023-12-31',
      symbol: 'SPY',
      totalReturn: 0.185,
      sharpeRatio: 1.92,
      maxDrawdown: -0.08,
      winRate: 0.58,
      profitFactor: 1.65,
      totalTrades: 245,
      avgTrade: 75,
      avgWinner: 180,
      avgLoser: -95,
      largestWin: 850,
      largestLoss: -420,
      avgHoldingTime: '2.5 hours',
      trades: Array.from({ length: 50 }, (_, i) => ({
        id: `trade_${i}`,
        entryTime: new Date(Date.now() - i * 86400000).toISOString(),
        exitTime: new Date(Date.now() - i * 86400000 + 9000000).toISOString(),
        symbol: 'SPY',
        side: Math.random() > 0.5 ? 'long' : 'short' as any,
        entryPrice: 450 + Math.random() * 10,
        exitPrice: 450 + Math.random() * 10,
        size: 100,
        pnl: (Math.random() - 0.4) * 400,
        pnlPct: (Math.random() - 0.4) * 0.02,
        signal: 'imbalance_reversal',
        signalStrength: 0.6 + Math.random() * 0.4,
        exitReason: ['target', 'stop', 'time'][Math.floor(Math.random() * 3)],
      })),
      equityCurve: Array.from({ length: 252 }, (_, i) => ({
        timestamp: new Date(Date.now() - (252 - i) * 86400000).toISOString(),
        equity: 100000 * (1 + 0.185 * (i / 252) + (Math.random() - 0.5) * 0.02),
        drawdown: Math.random() * -0.05,
      })),
      monthlyReturns: Array.from({ length: 12 }, (_, i) => ({
        month: new Date(2023, i, 1).toLocaleDateString('en-US', { month: 'short' }),
        return: (Math.random() - 0.3) * 0.05,
      })),
    },
  ];

  return {
    orderBook,
    imbalanceMetrics,
    tapeEntries,
    tapeAnalysis,
    flowModelMetrics,
    backtestResults,
  };
};

interface MicrostructureDashboardProps {
  symbol?: string;
}

export const MicrostructureDashboard: React.FC<MicrostructureDashboardProps> = ({
  symbol = 'SPY',
}) => {
  const [activeTab, setActiveTab] = useState('orderbook');
  const [selectedSymbol, setSelectedSymbol] = useState(symbol);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [data, setData] = useState(generateMockData());
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await new Promise(resolve => setTimeout(resolve, 300));
    setData(generateMockData());
    setLastUpdate(new Date());
    setIsRefreshing(false);
  };

  // Fast refresh for orderbook and tape
  useEffect(() => {
    const interval = setInterval(() => {
      if (activeTab === 'orderbook' || activeTab === 'tape') {
        setData(prev => ({
          ...prev,
          orderBook: generateMockData().orderBook,
          tapeEntries: [...generateMockData().tapeEntries.slice(0, 10), ...prev.tapeEntries.slice(0, 190)],
          imbalanceMetrics: generateMockData().imbalanceMetrics,
        }));
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [activeTab]);

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
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tabs */}
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
                <OrderBookHeatmap data={data.orderBook} />
              </Tabs.Content>

              <Tabs.Content value="tape">
                <TapeReader 
                  entries={data.tapeEntries} 
                  analysis={data.tapeAnalysis}
                />
              </Tabs.Content>

              <Tabs.Content value="models">
                <FlowModelMetrics metrics={data.flowModelMetrics} />
              </Tabs.Content>

              <Tabs.Content value="backtest">
                <BacktestResults results={data.backtestResults} />
              </Tabs.Content>
            </div>

            {/* Side Panel - Imbalance */}
            <div className="lg:col-span-1">
              <ImbalanceIndicator data={data.imbalanceMetrics} />
            </div>
          </div>
        </Tabs.Root>
      </div>
    </div>
  );
};

export default MicrostructureDashboard;
