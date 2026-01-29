/**
 * useBrain Hook
 * =============
 * React hook for interacting with the ML Brain API.
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config/api';

// Types
interface BrainStatus {
  initialized: boolean;
  multi_timeframe: boolean;
  signals_generated: number;
  performance_received: number;
  active_strategies: number;
  registered_bots: string[];
  learning_rate: number;
  top_features: Array<{ name: string; importance: number }>;
}

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
  open_pnl_pct: number;
  closed_pnl_pct: number;
  total_pnl_pct: number;
  win_rate: number;
}

interface FeatureImportance {
  name: string;
  importance: number;
  stability: number;
  regime_dependency: Record<string, number>;
}

interface UseBrainReturn {
  brainStatus: BrainStatus | null;
  signals: Record<string, Signal> | null;
  signalHistory: Signal[];
  bots: BotStatus[];
  features: FeatureImportance[];
  loading: boolean;
  error: string | null;
  initializeBrain: (multiTimeframe?: boolean) => Promise<void>;
  generateSignals: (symbol: string) => Promise<void>;
  refreshAll: () => Promise<void>;
  startPipeline: () => Promise<void>;
  stopPipeline: () => Promise<void>;
}

export const useBrain = (): UseBrainReturn => {
  const [brainStatus, setBrainStatus] = useState<BrainStatus | null>(null);
  const [signals, setSignals] = useState<Record<string, Signal> | null>(null);
  const [signalHistory, setSignalHistory] = useState<Signal[]>([]);
  const [bots, setBots] = useState<BotStatus[]>([]);
  const [features, setFeatures] = useState<FeatureImportance[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch brain status
  const fetchBrainStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/brain/status`);
      if (response.ok) {
        const data = await response.json();
        setBrainStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch brain status:', err);
    }
  }, []);

  // Fetch bots
  const fetchBots = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/brain/bots`);
      if (response.ok) {
        const data = await response.json();
        setBots(data);
      }
    } catch (err) {
      console.error('Failed to fetch bots:', err);
    }
  }, []);

  // Fetch features
  const fetchFeatures = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/brain/features/importance`);
      if (response.ok) {
        const data = await response.json();
        setFeatures(data);
      }
    } catch (err) {
      console.error('Failed to fetch features:', err);
    }
  }, []);

  // Fetch signal history
  const fetchSignalHistory = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/brain/signals/history?limit=50`);
      if (response.ok) {
        const data = await response.json();
        setSignalHistory(data);
      }
    } catch (err) {
      console.error('Failed to fetch signal history:', err);
    }
  }, []);

  // Initialize brain
  const initializeBrain = useCallback(async (multiTimeframe: boolean = true) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/brain/initialize?multi_timeframe=${multiTimeframe}`,
        { method: 'POST' }
      );
      
      if (!response.ok) {
        throw new Error('Failed to initialize brain');
      }
      
      await fetchBrainStatus();
      await fetchFeatures();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [fetchBrainStatus, fetchFeatures]);

  // Generate signals
  const generateSignals = useCallback(async (symbol: string) => {
    if (!brainStatus?.initialized) {
      setError('Brain not initialized');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const endpoint = brainStatus.multi_timeframe 
        ? `${API_BASE_URL}/brain/signal/multi-timeframe?symbol=${encodeURIComponent(symbol)}`
        : `${API_BASE_URL}/brain/signal/generate?symbol=${encodeURIComponent(symbol)}`;
      
      const response = await fetch(endpoint, { method: 'POST' });
      
      if (!response.ok) {
        throw new Error('Failed to generate signals');
      }
      
      const data = await response.json();
      
      if (brainStatus.multi_timeframe) {
        setSignals(data.signals);
      } else {
        setSignals({ single: data });
      }
      
      // Refresh related data
      await fetchBrainStatus();
      await fetchSignalHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [brainStatus, fetchBrainStatus, fetchSignalHistory]);

  // Refresh all data
  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchBrainStatus(),
        fetchBots(),
        fetchFeatures(),
        fetchSignalHistory(),
      ]);
    } finally {
      setLoading(false);
    }
  }, [fetchBrainStatus, fetchBots, fetchFeatures, fetchSignalHistory]);

  // Start pipeline
  const startPipeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/brain/pipeline/start`, { method: 'POST' });
      
      if (!response.ok) {
        throw new Error('Failed to start pipeline');
      }
      
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [refreshAll]);

  // Stop pipeline
  const stopPipeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/brain/pipeline/stop`, { method: 'POST' });
      
      if (!response.ok) {
        throw new Error('Failed to stop pipeline');
      }
      
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [refreshAll]);

  // Initial load
  useEffect(() => {
    fetchBrainStatus();
    fetchBots();
    fetchFeatures();
  }, [fetchBrainStatus, fetchBots, fetchFeatures]);

  // Polling for updates when brain is active
  useEffect(() => {
    if (brainStatus?.initialized) {
      const interval = setInterval(() => {
        fetchBrainStatus();
        fetchBots();
      }, 10000); // Every 10 seconds
      
      return () => clearInterval(interval);
    }
  }, [brainStatus?.initialized, fetchBrainStatus, fetchBots]);

  return {
    brainStatus,
    signals,
    signalHistory,
    bots,
    features,
    loading,
    error,
    initializeBrain,
    generateSignals,
    refreshAll,
    startPipeline,
    stopPipeline,
  };
};

export default useBrain;
