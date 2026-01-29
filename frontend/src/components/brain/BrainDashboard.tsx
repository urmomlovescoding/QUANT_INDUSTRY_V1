/**
 * ML Brain Dashboard
 * ==================
 * Main dashboard for viewing brain status, signals, and bot performance.
 */

import React, { useState, useEffect } from 'react';
import { useBrain } from '../../hooks/useBrain';

// Types
interface Signal {
  signal_id: string;
  timestamp: string;
  symbol: string;
  horizon?: string;
  direction: number;
  action: string;
  strength: number;
  confidence: number;
  suggested_size: number;
  regime: string;
  stop_loss?: number;
  take_profit?: number;
}

interface BotStatus {
  bot_id: string;
  name: string;
  status: string;
  open_trades: number;
  closed_trades: number;
  total_pnl_pct: number;
  win_rate: number;
}

// Signal Card Component
const SignalCard: React.FC<{ signal: Signal; horizon: string }> = ({ signal, horizon }) => {
  const actionColor = {
    buy: 'bg-green-500',
    sell: 'bg-red-500',
    hold: 'bg-gray-500',
  }[signal.action] || 'bg-gray-500';

  const horizonLabels: Record<string, string> = {
    scalp: '⚡ Scalp',
    intraday: '📊 Intraday',
    swing: '📈 Swing',
    position: '🎯 Position',
    macro: '🌍 Macro',
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex justify-between items-center mb-3">
        <span className="text-lg font-bold text-white">
          {horizonLabels[horizon] || horizon}
        </span>
        <span className={`px-3 py-1 rounded-full text-white text-sm font-bold ${actionColor}`}>
          {signal.action.toUpperCase()}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-400">Confidence:</span>
          <div className="w-full bg-gray-700 rounded-full h-2 mt-1">
            <div 
              className="bg-blue-500 h-2 rounded-full" 
              style={{ width: `${signal.confidence * 100}%` }}
            />
          </div>
          <span className="text-white">{(signal.confidence * 100).toFixed(0)}%</span>
        </div>
        
        <div>
          <span className="text-gray-400">Strength:</span>
          <div className="w-full bg-gray-700 rounded-full h-2 mt-1">
            <div 
              className="bg-purple-500 h-2 rounded-full" 
              style={{ width: `${signal.strength * 100}%` }}
            />
          </div>
          <span className="text-white">{(signal.strength * 100).toFixed(0)}%</span>
        </div>
        
        <div>
          <span className="text-gray-400">Size:</span>
          <span className="text-white ml-2">{(signal.suggested_size * 100).toFixed(1)}%</span>
        </div>
        
        <div>
          <span className="text-gray-400">Regime:</span>
          <span className="text-yellow-400 ml-2">{signal.regime}</span>
        </div>
        
        {signal.stop_loss && (
          <div>
            <span className="text-gray-400">SL:</span>
            <span className="text-red-400 ml-2">${signal.stop_loss.toFixed(2)}</span>
          </div>
        )}
        
        {signal.take_profit && (
          <div>
            <span className="text-gray-400">TP:</span>
            <span className="text-green-400 ml-2">${signal.take_profit.toFixed(2)}</span>
          </div>
        )}
      </div>
    </div>
  );
};

// Bot Status Card
const BotCard: React.FC<{ bot: BotStatus }> = ({ bot }) => {
  const statusColor = {
    running: 'text-green-400',
    stopped: 'text-gray-400',
    paused: 'text-yellow-400',
    error: 'text-red-400',
  }[bot.status] || 'text-gray-400';

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex justify-between items-center mb-2">
        <span className="font-bold text-white">{bot.name}</span>
        <span className={`text-sm ${statusColor}`}>● {bot.status}</span>
      </div>
      
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-400">Open:</span>
          <span className="text-white ml-2">{bot.open_trades}</span>
        </div>
        <div>
          <span className="text-gray-400">Closed:</span>
          <span className="text-white ml-2">{bot.closed_trades}</span>
        </div>
        <div>
          <span className="text-gray-400">PnL:</span>
          <span className={`ml-2 ${bot.total_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {bot.total_pnl_pct >= 0 ? '+' : ''}{(bot.total_pnl_pct * 100).toFixed(2)}%
          </span>
        </div>
        <div>
          <span className="text-gray-400">Win Rate:</span>
          <span className="text-white ml-2">{(bot.win_rate * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
};

// Feature Importance Chart
const FeatureChart: React.FC<{ features: Array<{ name: string; importance: number }> }> = ({ features }) => {
  const topFeatures = features.slice(0, 10);
  
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h3 className="text-lg font-bold text-white mb-3">🧠 Feature Importance</h3>
      <div className="space-y-2">
        {topFeatures.map((feat, idx) => (
          <div key={feat.name} className="flex items-center">
            <span className="text-gray-400 w-24 text-sm truncate">{feat.name}</span>
            <div className="flex-1 mx-2">
              <div className="w-full bg-gray-700 rounded-full h-3">
                <div 
                  className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full"
                  style={{ width: `${feat.importance * 100}%` }}
                />
              </div>
            </div>
            <span className="text-white text-sm w-12 text-right">
              {(feat.importance * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Main Dashboard Component
export const BrainDashboard: React.FC = () => {
  const {
    brainStatus,
    signals,
    bots,
    features,
    loading,
    error,
    initializeBrain,
    generateSignals,
    refreshAll,
  } = useBrain();

  const [selectedSymbol, setSelectedSymbol] = useState('BTC/USD');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        generateSignals(selectedSymbol);
      }, 30000); // Every 30 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh, selectedSymbol, generateSignals]);

  if (loading && !brainStatus) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-white text-xl">Loading ML Brain...</div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">🧠 ML Brain Dashboard</h1>
          <p className="text-gray-400">
            Multi-timeframe signals for scalp, intraday, swing, and macro trading
          </p>
        </div>
        
        <div className="flex gap-3">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-gray-800 text-white px-4 py-2 rounded border border-gray-700"
          >
            <option value="BTC/USD">BTC/USD</option>
            <option value="ETH/USD">ETH/USD</option>
            <option value="SPY">SPY</option>
          </select>
          
          {!brainStatus?.initialized ? (
            <button
              onClick={() => initializeBrain(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
            >
              Initialize Brain
            </button>
          ) : (
            <>
              <button
                onClick={() => generateSignals(selectedSymbol)}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
                disabled={loading}
              >
                {loading ? 'Generating...' : 'Generate Signals'}
              </button>
              
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-4 py-2 rounded ${
                  autoRefresh 
                    ? 'bg-yellow-600 hover:bg-yellow-700' 
                    : 'bg-gray-700 hover:bg-gray-600'
                } text-white`}
              >
                {autoRefresh ? '⏸️ Auto' : '▶️ Auto'}
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Brain Status */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-gray-400 text-sm">Status</div>
          <div className={`text-xl font-bold ${brainStatus?.initialized ? 'text-green-400' : 'text-gray-400'}`}>
            {brainStatus?.initialized ? '● Online' : '○ Offline'}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-gray-400 text-sm">Signals Generated</div>
          <div className="text-xl font-bold text-white">
            {brainStatus?.signals_generated || 0}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-gray-400 text-sm">Active Bots</div>
          <div className="text-xl font-bold text-white">
            {brainStatus?.registered_bots?.length || 0}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-gray-400 text-sm">Learning Rate</div>
          <div className="text-xl font-bold text-white">
            {brainStatus?.learning_rate?.toExponential(2) || '0'}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-3 gap-6">
        {/* Signals Column */}
        <div className="col-span-2">
          <h2 className="text-xl font-bold text-white mb-4">
            📡 Multi-Timeframe Signals - {selectedSymbol}
          </h2>
          
          {signals && Object.keys(signals).length > 0 ? (
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(signals).map(([horizon, signal]) => (
                <SignalCard key={horizon} signal={signal as Signal} horizon={horizon} />
              ))}
            </div>
          ) : (
            <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-400 border border-gray-700">
              No signals yet. Click "Generate Signals" to get started.
            </div>
          )}
          
          {/* Regime Indicator */}
          {signals && Object.values(signals)[0] && (
            <div className="mt-4 bg-gray-800 rounded-lg p-4 border border-gray-700">
              <span className="text-gray-400">Current Market Regime:</span>
              <span className="text-yellow-400 font-bold ml-2 text-lg">
                {(Object.values(signals)[0] as Signal).regime.replace('_', ' ').toUpperCase()}
              </span>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Feature Importance */}
          {features && features.length > 0 && (
            <FeatureChart features={features} />
          )}
          
          {/* Bots */}
          <div>
            <h3 className="text-lg font-bold text-white mb-3">🤖 Trading Bots</h3>
            <div className="space-y-3">
              {bots && bots.length > 0 ? (
                bots.map((bot) => (
                  <BotCard key={bot.bot_id} bot={bot} />
                ))
              ) : (
                <div className="bg-gray-800 rounded-lg p-4 text-center text-gray-400 border border-gray-700">
                  No bots active
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BrainDashboard;
