/**
 * useBrain Hook
 * =============
 * React hook for interacting with the ML Brain API.
 * Uses the v2 API client for type-safe requests.
 */

import { useState, useEffect, useCallback } from 'react';
import { apiV2 } from '@/api/v2';
import type { ApiResponse } from '@/api/v2';

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

/**
 * Helper to extract error message from ApiResponse
 */
function getErrorMessage(response: ApiResponse<unknown>): string {
  return response.error?.message || 'Unknown error';
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
      const response = await apiV2.brainLegacy.getStatus();
      if (response.ok && response.data) {
        setBrainStatus(response.data as unknown as BrainStatus);
        setError(null);
      }
    } catch {
      setError('Failed to fetch brain status');
    }
  }, []);

  // Fetch bots
  const fetchBots = useCallback(async () => {
    try {
      const response = await apiV2.brainLegacy.getBots();
      if (response.ok && response.data) {
        setBots(response.data as unknown as BotStatus[]);
      }
    } catch {
      // Silent fail for secondary data
    }
  }, []);

  // Fetch features
  const fetchFeatures = useCallback(async () => {
    try {
      const response = await apiV2.brainLegacy.getFeatures();
      if (response.ok && response.data) {
        setFeatures(response.data as unknown as FeatureImportance[]);
      }
    } catch {
      // Silent fail for secondary data
    }
  }, []);

  // Fetch signal history
  const fetchSignalHistory = useCallback(async () => {
    try {
      const response = await apiV2.brainLegacy.getSignalHistory(50);
      if (response.ok && response.data) {
        setSignalHistory(response.data as unknown as Signal[]);
      }
    } catch {
      // Silent fail for secondary data
    }
  }, []);

  // Initialize brain
  const initializeBrain = useCallback(async (multiTimeframe: boolean = true) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiV2.brainLegacy.initialize(multiTimeframe);
      
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
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
      const response = brainStatus.multi_timeframe 
        ? await apiV2.brainLegacy.generateMultiTimeframeSignal(symbol)
        : await apiV2.brainLegacy.generateSignal(symbol);
      
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
      }
      
      if (brainStatus.multi_timeframe && response.data) {
        setSignals((response.data as unknown as { signals: Record<string, Signal> }).signals);
      } else if (response.data) {
        setSignals({ single: response.data as unknown as Signal });
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
      const response = await apiV2.brainLegacy.startPipeline();
      
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
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
      const response = await apiV2.brainLegacy.stopPipeline();
      
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
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
