/**
 * Arb Dashboard
 * Main arbitrage dashboard
 * QUANT_INDUSTRY_V1
 */

import React, { useState, useEffect } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { RefreshCw, Settings, Zap, TrendingUp } from 'lucide-react';
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

// Mock data generator
const generateMockData = () => {
  const exchanges = ['Binance', 'Coinbase', 'Kraken', 'FTX', 'Uniswap', 'SushiSwap'];
  const symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'MATIC/USD'];

  const priceMatrices: PriceMatrix[] = symbols.map(symbol => {
    const basePrice = symbol.includes('BTC') ? 42000 : symbol.includes('ETH') ? 2500 : 100;
    const prices = exchanges.map(exchange => ({
      exchange,
      exchangeType: ['Uniswap', 'SushiSwap'].includes(exchange) ? 'dex' as const : 'cex' as const,
      symbol,
      bid: basePrice * (1 - Math.random() * 0.003),
      ask: basePrice * (1 + Math.random() * 0.003),
      mid: basePrice,
      spread: basePrice * Math.random() * 0.002,
      spreadBps: Math.random() * 20,
      volume24h: Math.random() * 1000000000,
      lastUpdate: new Date().toISOString(),
      latencyMs: Math.floor(20 + Math.random() * 150),
    }));

    const bestBid = prices.reduce((max, p) => p.bid > max.bid ? p : max, prices[0]);
    const bestAsk = prices.reduce((min, p) => p.ask < min.ask ? p : min, prices[0]);

    return {
      symbol,
      timestamp: new Date().toISOString(),
      prices,
      bestBid: { exchange: bestBid.exchange, price: bestBid.bid },
      bestAsk: { exchange: bestAsk.exchange, price: bestAsk.ask },
      maxSpread: Math.abs(bestBid.bid - bestAsk.ask) / bestAsk.ask,
      avgSpread: prices.reduce((sum, p) => sum + p.spreadBps, 0) / prices.length / 10000,
    };
  });

  const opportunities: ArbOpportunity[] = Array.from({ length: 8 }, (_, i) => ({
    id: `opp_${i}`,
    timestamp: new Date().toISOString(),
    type: ['simple', 'triangular', 'cex_dex', 'statistical'][Math.floor(Math.random() * 4)] as any,
    symbol: symbols[Math.floor(Math.random() * symbols.length)],
    buyExchange: exchanges[Math.floor(Math.random() * 4)],
    sellExchange: exchanges[Math.floor(Math.random() * 4)],
    buyPrice: 42000 + Math.random() * 100,
    sellPrice: 42000 + 50 + Math.random() * 100,
    spreadPct: 0.001 + Math.random() * 0.005,
    profitEstimate: 50 + Math.random() * 500,
    profitAfterFees: Math.random() > 0.3 ? 20 + Math.random() * 400 : -10 - Math.random() * 50,
    size: 0.5 + Math.random() * 2,
    notional: 20000 + Math.random() * 80000,
    confidence: 0.6 + Math.random() * 0.4,
    risk: ['low', 'medium', 'high'][Math.floor(Math.random() * 3)] as any,
    expiresIn: Math.floor(5 + Math.random() * 25),
    status: 'pending' as const,
    executionWindow: 30,
    fees: {
      buyFee: 5 + Math.random() * 20,
      sellFee: 5 + Math.random() * 20,
      networkFee: Math.random() > 0.5 ? 2 + Math.random() * 10 : undefined,
      totalFees: 15 + Math.random() * 50,
    },
  }));

  const triangularPaths: TriangularArbPath[] = Array.from({ length: 4 }, (_, i) => ({
    id: `tri_${i}`,
    timestamp: new Date(Date.now() - Math.random() * 3600000).toISOString(),
    exchange: exchanges[Math.floor(Math.random() * 4)],
    leg1: { pair: 'BTC/USDT', side: 'buy' as const, price: 42000, amount: 0.5 },
    leg2: { pair: 'BTC/ETH', side: 'sell' as const, price: 16.5, amount: 0.5 },
    leg3: { pair: 'ETH/USDT', side: 'sell' as const, price: 2550, amount: 8.25 },
    startAmount: 21000,
    endAmount: 21000 * (1 + (Math.random() - 0.3) * 0.01),
    profitPct: (Math.random() - 0.3) * 0.01,
    profitAfterFees: Math.random() > 0.4 ? 10 + Math.random() * 100 : -5 - Math.random() * 20,
    executionTimeMs: Math.floor(50 + Math.random() * 200),
    status: ['pending', 'completed', 'executing', 'failed'][Math.floor(Math.random() * 4)] as any,
  }));

  const cexDexSpread: CexDexSpread = {
    symbol: 'ETH/USD',
    timestamp: new Date().toISOString(),
    cexPrice: 2500 + Math.random() * 10,
    cexExchange: 'Binance',
    dexPrice: 2500 - 5 + Math.random() * 10,
    dexExchange: 'Uniswap',
    spread: 5 + Math.random() * 15,
    spreadPct: 0.002 + Math.random() * 0.005,
    gasPrice: 30 + Math.random() * 50,
    gasCostUsd: 5 + Math.random() * 20,
    netProfit: Math.random() > 0.4 ? 10 + Math.random() * 50 : -5 - Math.random() * 20,
    profitable: Math.random() > 0.4,
    direction: Math.random() > 0.5 ? 'cex_to_dex' : 'dex_to_cex',
  };

  const spreadHistory: CexDexSpreadHistory = {
    symbol: 'ETH/USD',
    data: Array.from({ length: 100 }, (_, i) => ({
      timestamp: new Date(Date.now() - (100 - i) * 60000).toISOString(),
      spread: 5 + Math.sin(i * 0.1) * 10 + Math.random() * 5,
      spreadPct: 0.002 + Math.sin(i * 0.1) * 0.003 + Math.random() * 0.002,
      cexPrice: 2500 + Math.sin(i * 0.05) * 20,
      dexPrice: 2500 + Math.sin(i * 0.05) * 20 - 5 - Math.random() * 10,
    })),
  };

  const latencies: ExchangeLatency[] = exchanges.map(exchange => ({
    exchange,
    exchangeType: ['Uniswap', 'SushiSwap'].includes(exchange) ? 'dex' as const : 'cex' as const,
    avgLatencyMs: Math.floor(30 + Math.random() * 80),
    p50LatencyMs: Math.floor(25 + Math.random() * 60),
    p95LatencyMs: Math.floor(80 + Math.random() * 150),
    p99LatencyMs: Math.floor(150 + Math.random() * 250),
    maxLatencyMs: Math.floor(200 + Math.random() * 500),
    minLatencyMs: Math.floor(10 + Math.random() * 30),
    lastPingMs: Math.floor(20 + Math.random() * 100),
    status: Math.random() > 0.1 ? 'healthy' : Math.random() > 0.5 ? 'degraded' : 'down' as any,
    uptime: 0.95 + Math.random() * 0.05,
    lastCheck: new Date().toISOString(),
    history: [],
  }));

  const executions: ArbExecution[] = Array.from({ length: 20 }, (_, i) => ({
    id: `exec_${i}`,
    opportunityId: `opp_${i}`,
    timestamp: new Date(Date.now() - Math.random() * 86400000).toISOString(),
    type: ['simple', 'triangular', 'cex_dex'][Math.floor(Math.random() * 3)] as any,
    symbol: symbols[Math.floor(Math.random() * symbols.length)],
    buyExchange: exchanges[Math.floor(Math.random() * 4)],
    sellExchange: exchanges[Math.floor(Math.random() * 4)],
    buyOrderId: `order_buy_${i}`,
    sellOrderId: `order_sell_${i}`,
    intendedBuyPrice: 42000 + Math.random() * 100,
    actualBuyPrice: 42000 + Math.random() * 100 + (Math.random() - 0.5) * 20,
    intendedSellPrice: 42050 + Math.random() * 100,
    actualSellPrice: 42050 + Math.random() * 100 + (Math.random() - 0.5) * 20,
    size: 0.5 + Math.random() * 2,
    slippage: (Math.random() - 0.5) * 10,
    slippagePct: (Math.random() - 0.5) * 0.005,
    expectedProfit: 50 + Math.random() * 200,
    actualProfit: (Math.random() - 0.3) * 300,
    fees: 10 + Math.random() * 40,
    netProfit: (Math.random() - 0.3) * 250,
    executionTimeMs: Math.floor(50 + Math.random() * 300),
    status: ['success', 'partial', 'failed'][Math.floor(Math.random() * 3)] as any,
    legs: [
      {
        exchange: exchanges[Math.floor(Math.random() * 4)],
        side: 'buy' as const,
        status: 'filled' as const,
        filledQty: 0.5,
        avgPrice: 42000 + Math.random() * 50,
        latencyMs: Math.floor(30 + Math.random() * 100),
      },
      {
        exchange: exchanges[Math.floor(Math.random() * 4)],
        side: 'sell' as const,
        status: 'filled' as const,
        filledQty: 0.5,
        avgPrice: 42050 + Math.random() * 50,
        latencyMs: Math.floor(30 + Math.random() * 100),
      },
    ],
  }));

  return {
    priceMatrices,
    opportunities,
    triangularPaths,
    cexDexSpread,
    spreadHistory,
    latencies,
    executions,
  };
};

export const ArbDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState('opportunities');
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

  // Auto refresh
  useEffect(() => {
    const interval = setInterval(() => {
      setData(generateMockData());
      setLastUpdate(new Date());
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const stats = {
    activeOpps: data.opportunities.filter(o => o.profitAfterFees > 0).length,
    totalProfit: data.executions.reduce((sum, e) => sum + Math.max(0, e.netProfit), 0),
    successRate: data.executions.filter(e => e.status === 'success').length / data.executions.length,
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
              value="opportunities"
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === 'opportunities' ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Opportunities
            </Tabs.Trigger>
            <Tabs.Trigger
              value="prices"
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === 'prices' ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Price Matrix
            </Tabs.Trigger>
            <Tabs.Trigger
              value="triangular"
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === 'triangular' ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Triangular
            </Tabs.Trigger>
            <Tabs.Trigger
              value="cexdex"
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === 'cexdex' ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              CEX-DEX
            </Tabs.Trigger>
            <Tabs.Trigger
              value="latency"
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === 'latency' ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Latency
            </Tabs.Trigger>
            <Tabs.Trigger
              value="history"
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === 'history' ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Execution Log
            </Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content value="opportunities">
            <ArbOpportunityList
              opportunities={data.opportunities}
              onExecute={(opp) => { /* TODO: wire to execution API */ }}
              onDismiss={(id) => { /* TODO: wire to dismiss API */ }}
            />
          </Tabs.Content>

          <Tabs.Content value="prices">
            <PriceMatrixTable data={data.priceMatrices} />
          </Tabs.Content>

          <Tabs.Content value="triangular">
            <TriangularArbVisualizer paths={data.triangularPaths} />
          </Tabs.Content>

          <Tabs.Content value="cexdex">
            <CexDexSpreadChart
              currentSpread={data.cexDexSpread}
              history={data.spreadHistory}
              symbol="ETH/USD"
            />
          </Tabs.Content>

          <Tabs.Content value="latency">
            <LatencyMonitor latencies={data.latencies} />
          </Tabs.Content>

          <Tabs.Content value="history">
            <ExecutionLog executions={data.executions} />
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  );
};

export default ArbDashboard;
