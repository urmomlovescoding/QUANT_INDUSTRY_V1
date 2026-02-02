/**
 * Backtest Visualization View
 * Full-featured backtest runner and visualization dashboard
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { BacktestVisualization } from '../components/BacktestVisualization';
import { PnLAttribution } from '../components/PnLAttribution';
import {
  submitBacktest,
  getBacktestJob,
  getBacktestResult,
  getQueueStatus,
  waitForBacktestCompletion,
  transformResultToVisualization,
  sampleStrategies,
  BacktestJob,
  BacktestResult,
  QueueStatus,
} from '../services/backtestApi';
import {
  Play,
  Square,
  RefreshCw,
  Settings,
  TrendingUp,
  BarChart3,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
  ChevronDown,
  Code,
  Calendar,
  DollarSign,
  Activity,
} from 'lucide-react';

// Sample symbols
const SYMBOL_PRESETS = {
  'Tech Giants': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA'],
  'FAANG': ['META', 'AAPL', 'AMZN', 'NFLX', 'GOOGL'],
  'Indices': ['SPY', 'QQQ', 'IWM', 'DIA'],
  'Semiconductors': ['NVDA', 'AMD', 'INTC', 'TSM', 'AVGO'],
  'Custom': [],
};

type StrategyType = 'momentum' | 'meanReversion' | 'trendFollowing' | 'custom';

export function BacktestViz() {
  // Form state
  const [symbols, setSymbols] = useState<string[]>(['AAPL', 'MSFT', 'GOOGL']);
  const [symbolPreset, setSymbolPreset] = useState<string>('Tech Giants');
  const [customSymbols, setCustomSymbols] = useState<string>('');
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState('2024-01-01');
  const [initialCapital, setInitialCapital] = useState(100000);
  const [strategyType, setStrategyType] = useState<StrategyType>('momentum');
  const [customCode, setCustomCode] = useState(sampleStrategies.momentum);
  const [strategyParams, setStrategyParams] = useState<Record<string, any>>({
    lookback: 20,
  });

  // Execution state
  const [isRunning, setIsRunning] = useState(false);
  const [currentJob, setCurrentJob] = useState<BacktestJob | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [visualizationData, setVisualizationData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);

  // UI state
  const [showSettings, setShowSettings] = useState(true);
  const [activeTab, setActiveTab] = useState<'visualization' | 'pnl' | 'trades'>('visualization');

  // Load queue status
  useEffect(() => {
    const loadQueueStatus = async () => {
      try {
        const status = await getQueueStatus();
        setQueueStatus(status);
      } catch (e) {
        console.warn('Could not load queue status:', e);
      }
    };
    loadQueueStatus();
    const interval = setInterval(loadQueueStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Handle symbol preset change
  useEffect(() => {
    if (symbolPreset !== 'Custom') {
      setSymbols(SYMBOL_PRESETS[symbolPreset as keyof typeof SYMBOL_PRESETS]);
    }
  }, [symbolPreset]);

  // Handle strategy type change
  useEffect(() => {
    if (strategyType !== 'custom') {
      setCustomCode(sampleStrategies[strategyType]);
      // Set default params for each strategy
      switch (strategyType) {
        case 'momentum':
          setStrategyParams({ lookback: 20 });
          break;
        case 'meanReversion':
          setStrategyParams({ window: 20, threshold: 2 });
          break;
        case 'trendFollowing':
          setStrategyParams({ fast: 10, slow: 30 });
          break;
      }
    }
  }, [strategyType]);

  // Run backtest
  const runBacktest = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    setVisualizationData(null);

    try {
      // Submit job
      const job = await submitBacktest({
        tenant_id: 'web-user',
        strategy_code: customCode,
        symbols: symbolPreset === 'Custom' 
          ? customSymbols.split(',').map(s => s.trim().toUpperCase())
          : symbols,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        strategy_params: strategyParams,
        priority: 'normal',
      });

      setCurrentJob(job);

      // Wait for completion with progress updates
      const finalResult = await waitForBacktestCompletion(
        job.job_id,
        (updatedJob) => setCurrentJob(updatedJob),
        1000,
        300000
      );

      setResult(finalResult);
      setVisualizationData(transformResultToVisualization(finalResult));
      setShowSettings(false);

    } catch (e: any) {
      setError(e.message || 'Backtest failed');
    } finally {
      setIsRunning(false);
    }
  }, [customCode, symbols, symbolPreset, customSymbols, startDate, endDate, initialCapital, strategyParams]);

  // Generate sample data for demo
  const loadSampleData = useCallback(() => {
    const sampleResult: BacktestResult = {
      job_id: 'sample',
      config_hash: 'sample',
      performance: {
        total_return: 0.234,
        annualized_return: 0.187,
        sharpe_ratio: 1.45,
        sortino_ratio: 2.1,
        max_drawdown: 0.12,
        calmar_ratio: 1.56,
        volatility: 0.18,
      },
      trades: {
        total: 156,
        winning: 89,
        losing: 67,
        win_rate: 0.57,
        avg_win: 1250,
        avg_loss: -780,
        profit_factor: 1.82,
        avg_holding_period: 5.3,
      },
      risk: {
        var_95: -0.023,
        cvar_95: -0.034,
        beta: 0.85,
        alpha: 0.052,
      },
      curves: {
        equity: Array.from({ length: 252 }, (_, i) => ({
          date: new Date(2023, 0, 1 + i).toISOString().split('T')[0],
          equity: 100000 * (1 + 0.001 * i + Math.sin(i / 20) * 0.03),
        })),
        drawdown: Array.from({ length: 252 }, (_, i) => ({
          date: new Date(2023, 0, 1 + i).toISOString().split('T')[0],
          drawdown: Math.abs(Math.sin(i / 30) * 0.08),
        })),
        monthly_returns: [
          { month: '2023-01', return: 0.032 },
          { month: '2023-02', return: -0.015 },
          { month: '2023-03', return: 0.045 },
          { month: '2023-04', return: 0.021 },
          { month: '2023-05', return: -0.008 },
          { month: '2023-06', return: 0.038 },
        ],
      },
      trade_log: [],
      execution: { time_seconds: 2.5, data_points: 50400 },
      warnings: [],
    };

    setResult(sampleResult);
    setVisualizationData(transformResultToVisualization(sampleResult));
    setShowSettings(false);
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900/95 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-blue-600 rounded-lg">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Backtest Laboratory</h1>
                <p className="text-sm text-gray-400">
                  Strategy backtesting with real-time visualization
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Queue Status */}
              {queueStatus && (
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Activity className="w-4 h-4" />
                  <span>
                    {queueStatus.running_jobs}/{queueStatus.max_workers} workers
                  </span>
                  {queueStatus.queue_size > 0 && (
                    <span className="text-yellow-400">
                      ({queueStatus.queue_size} queued)
                    </span>
                  )}
                </div>
              )}

              <button
                onClick={() => setShowSettings(!showSettings)}
                className={`p-2 rounded-lg transition-colors ${
                  showSettings ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
                }`}
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Settings Panel */}
          {showSettings && (
            <div className="col-span-12 lg:col-span-4">
              <div className="bg-gray-800 rounded-lg p-6 space-y-6">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  Backtest Configuration
                </h2>

                {/* Symbol Selection */}
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-gray-400">
                    Universe
                  </label>
                  <select
                    value={symbolPreset}
                    onChange={(e) => setSymbolPreset(e.target.value)}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2"
                  >
                    {Object.keys(SYMBOL_PRESETS).map((preset) => (
                      <option key={preset} value={preset}>{preset}</option>
                    ))}
                  </select>
                  
                  {symbolPreset === 'Custom' ? (
                    <input
                      type="text"
                      value={customSymbols}
                      onChange={(e) => setCustomSymbols(e.target.value)}
                      placeholder="AAPL, MSFT, GOOGL..."
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2"
                    />
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {symbols.map((symbol) => (
                        <span
                          key={symbol}
                          className="px-2 py-1 bg-blue-600/20 text-blue-400 rounded text-sm"
                        >
                          {symbol}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Date Range */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">
                      <Calendar className="w-4 h-4 inline mr-1" />
                      Start Date
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">
                      End Date
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2"
                    />
                  </div>
                </div>

                {/* Capital */}
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">
                    <DollarSign className="w-4 h-4 inline mr-1" />
                    Initial Capital
                  </label>
                  <input
                    type="number"
                    value={initialCapital}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2"
                  />
                </div>

                {/* Strategy Selection */}
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-gray-400">
                    <Code className="w-4 h-4 inline mr-1" />
                    Strategy
                  </label>
                  <select
                    value={strategyType}
                    onChange={(e) => setStrategyType(e.target.value as StrategyType)}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2"
                  >
                    <option value="momentum">Momentum</option>
                    <option value="meanReversion">Mean Reversion</option>
                    <option value="trendFollowing">Trend Following</option>
                    <option value="custom">Custom Code</option>
                  </select>

                  {/* Strategy Parameters */}
                  {strategyType === 'momentum' && (
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Lookback Period</label>
                      <input
                        type="number"
                        value={strategyParams.lookback || 20}
                        onChange={(e) => setStrategyParams({ ...strategyParams, lookback: Number(e.target.value) })}
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                  )}

                  {strategyType === 'meanReversion' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Window</label>
                        <input
                          type="number"
                          value={strategyParams.window || 20}
                          onChange={(e) => setStrategyParams({ ...strategyParams, window: Number(e.target.value) })}
                          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Z-Score Threshold</label>
                        <input
                          type="number"
                          step="0.1"
                          value={strategyParams.threshold || 2}
                          onChange={(e) => setStrategyParams({ ...strategyParams, threshold: Number(e.target.value) })}
                          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  )}

                  {strategyType === 'trendFollowing' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Fast MA</label>
                        <input
                          type="number"
                          value={strategyParams.fast || 10}
                          onChange={(e) => setStrategyParams({ ...strategyParams, fast: Number(e.target.value) })}
                          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Slow MA</label>
                        <input
                          type="number"
                          value={strategyParams.slow || 30}
                          onChange={(e) => setStrategyParams({ ...strategyParams, slow: Number(e.target.value) })}
                          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  )}

                  {strategyType === 'custom' && (
                    <textarea
                      value={customCode}
                      onChange={(e) => setCustomCode(e.target.value)}
                      rows={10}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 font-mono text-xs"
                      placeholder="def generate_signals(data, params):&#10;    # Your strategy code here&#10;    return {}"
                    />
                  )}
                </div>

                {/* Error Display */}
                {error && (
                  <div className="p-3 bg-red-900/30 border border-red-700 rounded-lg flex items-start gap-2">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-red-300">{error}</span>
                  </div>
                )}

                {/* Job Progress */}
                {currentJob && isRunning && (
                  <div className="p-3 bg-blue-900/30 border border-blue-700 rounded-lg space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-blue-300">{currentJob.current_step || 'Processing...'}</span>
                      <span className="text-sm text-blue-400">{Math.round(currentJob.progress * 100)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${currentJob.progress * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={runBacktest}
                    disabled={isRunning}
                    className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-colors ${
                      isRunning
                        ? 'bg-gray-600 cursor-not-allowed'
                        : 'bg-green-600 hover:bg-green-500'
                    }`}
                  >
                    {isRunning ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Running...
                      </>
                    ) : (
                      <>
                        <Play className="w-5 h-5" />
                        Run Backtest
                      </>
                    )}
                  </button>

                  <button
                    onClick={loadSampleData}
                    className="px-4 py-3 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
                    title="Load sample data"
                  >
                    <BarChart3 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Results Panel */}
          <div className={showSettings ? 'col-span-12 lg:col-span-8' : 'col-span-12'}>
            {visualizationData ? (
              <div className="space-y-6">
                {/* Summary Cards */}
                {result && (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <SummaryCard
                      label="Total Return"
                      value={`${(result.performance.total_return * 100).toFixed(2)}%`}
                      positive={result.performance.total_return >= 0}
                    />
                    <SummaryCard
                      label="Sharpe Ratio"
                      value={result.performance.sharpe_ratio.toFixed(2)}
                      positive={result.performance.sharpe_ratio > 0}
                    />
                    <SummaryCard
                      label="Max Drawdown"
                      value={`${(result.performance.max_drawdown * 100).toFixed(2)}%`}
                      positive={false}
                    />
                    <SummaryCard
                      label="Win Rate"
                      value={`${(result.trades.win_rate * 100).toFixed(1)}%`}
                      positive={result.trades.win_rate > 0.5}
                    />
                    <SummaryCard
                      label="Total Trades"
                      value={result.trades.total.toString()}
                    />
                  </div>
                )}

                {/* Tab Navigation - Using Radix UI */}
                <Tabs.Root defaultValue="visualization">
                  <Tabs.List className="flex gap-2 border-b border-gray-700" aria-label="Backtest analysis">
                    <Tabs.Trigger
                      value="visualization"
                      className="flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors border-transparent text-gray-400 hover:text-white data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                    >
                      <TrendingUp className="w-4 h-4" />
                      Performance
                    </Tabs.Trigger>
                    <Tabs.Trigger
                      value="pnl"
                      className="flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors border-transparent text-gray-400 hover:text-white data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                    >
                      <BarChart3 className="w-4 h-4" />
                      P&L Attribution
                    </Tabs.Trigger>
                  </Tabs.List>

                  {/* Tab Content */}
                  <Tabs.Content value="visualization" className="focus:outline-none mt-4">
                    <BacktestVisualization
                      equity={visualizationData.equity}
                      trades={visualizationData.trades}
                      rollingMetrics={visualizationData.rollingMetrics}
                      factorExposures={visualizationData.factorExposures}
                    />
                  </Tabs.Content>

                  <Tabs.Content value="pnl" className="focus:outline-none mt-4">
                    <PnLAttribution autoRefresh={false} />
                  </Tabs.Content>
                </Tabs.Root>
              </div>
            ) : (
              /* Empty State */
              <div className="bg-gray-800 rounded-lg p-12 text-center">
                <div className="max-w-md mx-auto">
                  <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
                    <TrendingUp className="w-8 h-8 text-gray-500" />
                  </div>
                  <h3 className="text-xl font-bold mb-2">No Backtest Results</h3>
                  <p className="text-gray-400 mb-6">
                    Configure your strategy and run a backtest to see performance analysis and visualizations.
                  </p>
                  <div className="flex gap-3 justify-center">
                    <button
                      onClick={runBacktest}
                      disabled={isRunning}
                      className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-500 rounded-lg font-medium"
                    >
                      <Play className="w-5 h-5" />
                      Run Backtest
                    </button>
                    <button
                      onClick={loadSampleData}
                      className="flex items-center gap-2 px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium"
                    >
                      <BarChart3 className="w-5 h-5" />
                      Load Sample
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper Components
function SummaryCard({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400 uppercase mb-1">{label}</div>
      <div
        className={`text-xl font-bold font-mono ${
          positive === undefined
            ? 'text-white'
            : positive
            ? 'text-green-400'
            : 'text-red-400'
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-blue-500 text-blue-400'
          : 'border-transparent text-gray-400 hover:text-white'
      }`}
    >
      {children}
    </button>
  );
}

export default BacktestViz;
