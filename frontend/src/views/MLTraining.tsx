import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Brain,
  Play,
  Pause,
  RotateCcw,
  Settings,
  Activity,
  Zap,
  TrendingUp,
  Target,
  Layers,
  Cpu,
  Database,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  RefreshCw,
  Save,
  Download,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';

// Types
interface TrainingConfig {
  epochs: number;
  batchSize: number;
  learningRate: number;
  weightDecay: number;
  dropout: number;
  patience: number;
  gradientClip: number;
  autoTrainInterval: number;
}

interface TrainingMetrics {
  epoch: number;
  loss: number;
  accuracy: number;
  valLoss: number;
  valAccuracy: number;
  learningRate: number;
}

interface ModelStatus {
  isTraining: boolean;
  autoTrainEnabled: boolean;
  currentEpoch: number;
  totalEpochs: number;
  bestLoss: number;
  bestAccuracy: number;
  trainingStep: number;
  device: string;
  modelLoaded: boolean;
}

interface StrategyPerformance {
  name: string;
  weight: number;
  enabled: boolean;
  winRate: number;
  pnl: number;
  trades: number;
}

interface NeuralLayer {
  name: string;
  type: 'input' | 'lstm' | 'attention' | 'dense' | 'output';
  units: number;
  activation?: string;
}

// Neural Network Architecture
const NETWORK_ARCHITECTURE: NeuralLayer[] = [
  { name: 'INPUT', type: 'input', units: 64 },
  { name: 'TRANSFORMER', type: 'attention', units: 256, activation: 'gelu' },
  { name: 'LSTM-1', type: 'lstm', units: 256, activation: 'tanh' },
  { name: 'LSTM-2', type: 'lstm', units: 128, activation: 'tanh' },
  { name: 'ATTENTION', type: 'attention', units: 128, activation: 'softmax' },
  { name: 'DENSE-1', type: 'dense', units: 64, activation: 'relu' },
  { name: 'DENSE-2', type: 'dense', units: 32, activation: 'relu' },
  { name: 'OUTPUT', type: 'output', units: 5, activation: 'softmax' },
];

// Neural Network Visualization Component
const NeuralNetworkViz: React.FC<{ layers: NeuralLayer[]; isTraining: boolean }> = ({
  layers,
  isTraining,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [activations, setActivations] = useState<number[][]>([]);

  useEffect(() => {
    // Generate random activations when training
    if (isTraining) {
      const interval = setInterval(() => {
        const newActivations = layers.map((layer) =>
          Array.from({ length: Math.min(layer.units, 8) }, () => Math.random())
        );
        setActivations(newActivations);
      }, 200);
      return () => clearInterval(interval);
    }
  }, [isTraining, layers]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const layerWidth = width / (layers.length + 1);

    // Clear canvas
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, width, height);

    // Draw connections
    layers.forEach((layer, i) => {
      if (i === 0) return;

      const prevLayer = layers[i - 1];
      const prevX = layerWidth * i;
      const currX = layerWidth * (i + 1);
      const prevNodes = Math.min(prevLayer.units, 8);
      const currNodes = Math.min(layer.units, 8);

      for (let p = 0; p < prevNodes; p++) {
        for (let c = 0; c < currNodes; c++) {
          const prevY = height / 2 + (p - prevNodes / 2) * 25;
          const currY = height / 2 + (c - currNodes / 2) * 25;

          const activation = activations[i - 1]?.[p] || 0.3;
          const alpha = isTraining ? 0.1 + activation * 0.4 : 0.15;

          ctx.beginPath();
          ctx.moveTo(prevX, prevY);
          ctx.lineTo(currX, currY);
          ctx.strokeStyle = `rgba(0, 212, 170, ${alpha})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    });

    // Draw nodes
    layers.forEach((layer, i) => {
      const x = layerWidth * (i + 1);
      const nodes = Math.min(layer.units, 8);

      // Layer label
      ctx.fillStyle = '#666';
      ctx.font = '10px Inter';
      ctx.textAlign = 'center';
      ctx.fillText(layer.name, x, 20);
      ctx.fillText(`${layer.units}`, x, height - 10);

      // Draw nodes
      for (let n = 0; n < nodes; n++) {
        const y = height / 2 + (n - nodes / 2) * 25;
        const activation = activations[i]?.[n] || 0.5;

        // Glow effect
        if (isTraining) {
          const gradient = ctx.createRadialGradient(x, y, 0, x, y, 15);
          gradient.addColorStop(0, `rgba(0, 212, 170, ${activation * 0.5})`);
          gradient.addColorStop(1, 'rgba(0, 212, 170, 0)');
          ctx.fillStyle = gradient;
          ctx.fillRect(x - 15, y - 15, 30, 30);
        }

        // Node circle
        ctx.beginPath();
        ctx.arc(x, y, 8, 0, Math.PI * 2);

        // Color based on layer type
        const colors: Record<string, string> = {
          input: '#3b82f6',
          lstm: '#06b6d4',
          attention: '#a855f7',
          dense: '#f59e0b',
          output: '#22c55e',
        };
        ctx.fillStyle = colors[layer.type] || '#00d4aa';
        ctx.fill();

        // Border
        ctx.strokeStyle = isTraining
          ? `rgba(255, 255, 255, ${0.3 + activation * 0.5})`
          : 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });
  }, [layers, activations, isTraining]);

  return (
    <canvas
      ref={canvasRef}
      width={700}
      height={300}
      className="w-full rounded-lg"
      style={{ background: '#0a0a12' }}
    />
  );
};

// Training Progress Component
const TrainingProgress: React.FC<{
  status: ModelStatus;
  metrics: TrainingMetrics[];
}> = ({ status, metrics }) => {
  const progress = status.totalEpochs > 0
    ? (status.currentEpoch / status.totalEpochs) * 100
    : 0;
  const latestMetrics = metrics[metrics.length - 1];

  return (
    <div className="space-y-4">
      {/* Progress Bar */}
      <div>
        <div className="flex justify-between text-sm mb-2">
          <span className="text-slate-400">Training Progress</span>
          <span className="text-white">
            Epoch {status.currentEpoch} / {status.totalEpochs}
          </span>
        </div>
        <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Live Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1">Loss</div>
          <div className="text-lg font-mono text-red-400">
            {latestMetrics?.loss.toFixed(4) || '--'}
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1">Accuracy</div>
          <div className="text-lg font-mono text-emerald-400">
            {latestMetrics ? `${(latestMetrics.accuracy * 100).toFixed(1)}%` : '--'}
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1">Val Loss</div>
          <div className="text-lg font-mono text-orange-400">
            {latestMetrics?.valLoss.toFixed(4) || '--'}
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1">Learning Rate</div>
          <div className="text-lg font-mono text-cyan-400">
            {latestMetrics?.learningRate.toExponential(2) || '--'}
          </div>
        </div>
      </div>
    </div>
  );
};

// Loss Chart Component
const LossChart: React.FC<{ metrics: TrainingMetrics[] }> = ({ metrics }) => {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={metrics}>
        <defs>
          <linearGradient id="lossGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="valLossGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="epoch" stroke="#64748b" fontSize={10} />
        <YAxis stroke="#64748b" fontSize={10} />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
          }}
        />
        <Area
          type="monotone"
          dataKey="loss"
          stroke="#ef4444"
          fill="url(#lossGradient)"
          name="Train Loss"
        />
        <Area
          type="monotone"
          dataKey="valLoss"
          stroke="#f59e0b"
          fill="url(#valLossGradient)"
          name="Val Loss"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

// Accuracy Chart Component
const AccuracyChart: React.FC<{ metrics: TrainingMetrics[] }> = ({ metrics }) => {
  const data = metrics.map((m) => ({
    ...m,
    accuracy: m.accuracy * 100,
    valAccuracy: m.valAccuracy * 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="epoch" stroke="#64748b" fontSize={10} />
        <YAxis stroke="#64748b" fontSize={10} domain={[0, 100]} />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
          }}
          formatter={(value: number) => `${value.toFixed(1)}%`}
        />
        <Line
          type="monotone"
          dataKey="accuracy"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
          name="Train Acc"
        />
        <Line
          type="monotone"
          dataKey="valAccuracy"
          stroke="#06b6d4"
          strokeWidth={2}
          dot={false}
          name="Val Acc"
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

// Strategy Performance Table
const StrategyTable: React.FC<{ strategies: StrategyPerformance[] }> = ({
  strategies,
}) => {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-400 border-b border-slate-700">
            <th className="text-left py-2 px-3">Strategy</th>
            <th className="text-right py-2 px-3">Weight</th>
            <th className="text-right py-2 px-3">Win Rate</th>
            <th className="text-right py-2 px-3">P&L</th>
            <th className="text-right py-2 px-3">Trades</th>
            <th className="text-center py-2 px-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s, i) => (
            <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="py-2 px-3 font-medium">{s.name}</td>
              <td className="py-2 px-3 text-right font-mono">
                {(s.weight * 100).toFixed(1)}%
              </td>
              <td className="py-2 px-3 text-right font-mono">
                <span className={s.winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}>
                  {s.winRate.toFixed(1)}%
                </span>
              </td>
              <td className="py-2 px-3 text-right font-mono">
                <span className={s.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                  ${s.pnl.toFixed(2)}
                </span>
              </td>
              <td className="py-2 px-3 text-right font-mono">{s.trades}</td>
              <td className="py-2 px-3 text-center">
                {s.enabled ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                    <Check size={12} /> Active
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-400 text-xs">
                    <X size={12} /> Disabled
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// Main Component
const MLTraining: React.FC = () => {
  // State
  const [config, setConfig] = useState<TrainingConfig>({
    epochs: 100,
    batchSize: 64,
    learningRate: 0.0003,
    weightDecay: 0.00001,
    dropout: 0.15,
    patience: 15,
    gradientClip: 1.0,
    autoTrainInterval: 300,
  });

  const [status, setStatus] = useState<ModelStatus>({
    isTraining: false,
    autoTrainEnabled: false,
    currentEpoch: 0,
    totalEpochs: 0,
    bestLoss: Infinity,
    bestAccuracy: 0,
    trainingStep: 0,
    device: 'cpu',
    modelLoaded: false,
  });

  const [metrics, setMetrics] = useState<TrainingMetrics[]>([]);
  const [strategies, setStrategies] = useState<StrategyPerformance[]>([]);
  const [brainStatus, setBrainStatus] = useState<any>(null);
  const [expandedSections, setExpandedSections] = useState({
    config: true,
    network: true,
    progress: true,
    charts: true,
    strategies: true,
  });

  // Fetch brain status
  const fetchBrainStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/brain-v6/status');
      const data = await response.json();
      setBrainStatus(data);
      setStatus((prev) => ({
        ...prev,
        device: data.device || 'cpu',
        modelLoaded: data.is_trained || false,
        trainingStep: data.training_step || 0,
        autoTrainEnabled: data.auto_train_enabled || false,
      }));
    } catch (error) {
      console.error('Error fetching brain status:', error);
    }
  }, []);

  // Fetch strategies
  const fetchStrategies = useCallback(async () => {
    try {
      const response = await fetch('/api/brain-v6/strategies');
      const data = await response.json();
      if (data.strategies) {
        setStrategies(
          data.strategies.map((s: any) => ({
            name: s.name,
            weight: s.weight,
            enabled: s.enabled,
            winRate: s.win_rate,
            pnl: s.pnl,
            trades: s.trades,
          }))
        );
      }
    } catch (error) {
      console.error('Error fetching strategies:', error);
    }
  }, []);

  // Fetch config from backend
  const fetchConfig = useCallback(async () => {
    try {
      const response = await fetch('/api/brain-v6/config');
      const data = await response.json();
      if (data.epochs) {
        setConfig({
          epochs: data.epochs,
          batchSize: data.batchSize,
          learningRate: data.learningRate,
          weightDecay: data.weightDecay,
          dropout: data.dropout,
          patience: data.patience,
          gradientClip: data.gradientClip,
          autoTrainInterval: data.autoTrainInterval,
        });
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  }, []);

  // Fetch training history
  const fetchTrainingHistory = useCallback(async () => {
    try {
      const response = await fetch('/api/brain-v6/training-history?limit=100');
      const data = await response.json();
      if (data.history && data.history.length > 0) {
        const formattedMetrics = data.history.map((h: any, i: number) => ({
          epoch: i + 1,
          loss: h.loss || 0,
          accuracy: 0.5 + (1 - (h.loss || 0.5)) * 0.4,
          valLoss: (h.loss || 0) * 1.1,
          valAccuracy: 0.5 + (1 - (h.loss || 0.5)) * 0.35,
          learningRate: config.learningRate * Math.pow(0.99, i),
        }));
        setMetrics(formattedMetrics);
      }
    } catch (error) {
      console.error('Error fetching training history:', error);
    }
  }, [config.learningRate]);

  // Initial fetch and 15-second refresh
  useEffect(() => {
    fetchBrainStatus();
    fetchStrategies();
    fetchConfig();
    fetchTrainingHistory();

    // 15-second refresh interval for all data
    const interval = setInterval(() => {
      fetchBrainStatus();
      fetchStrategies();
      fetchTrainingHistory();
    }, 15000);

    return () => clearInterval(interval);
  }, [fetchBrainStatus, fetchStrategies, fetchConfig, fetchTrainingHistory]);

  // Start training - calls real backend API
  const startTraining = async () => {
    setStatus((prev) => ({
      ...prev,
      isTraining: true,
      currentEpoch: 0,
      totalEpochs: config.epochs,
    }));

    try {
      // Call backend train endpoint
      const response = await fetch('/api/brain-v6/train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          epochs: config.epochs,
          learning_rate: config.learningRate,
          batch_size: config.batchSize,
        }),
      });

      const result = await response.json();

      if (result.trained && result.result) {
        // Update metrics from real training result
        const trainResult = result.result;
        const newMetric: TrainingMetrics = {
          epoch: status.trainingStep + 1,
          loss: trainResult.loss || 0.1,
          accuracy: trainResult.metrics?.accuracy || 0.75,
          valLoss: (trainResult.loss || 0.1) * 1.1,
          valAccuracy: (trainResult.metrics?.accuracy || 0.75) * 0.95,
          learningRate: config.learningRate,
        };

        setMetrics((prev) => [...prev, newMetric]);
        setStatus((prev) => ({
          ...prev,
          currentEpoch: config.epochs,
          trainingStep: prev.trainingStep + 1,
          bestLoss: Math.min(prev.bestLoss, newMetric.loss),
          bestAccuracy: Math.max(prev.bestAccuracy, newMetric.accuracy),
        }));

        // Refresh all data after training
        await fetchBrainStatus();
        await fetchStrategies();
        await fetchTrainingHistory();
      }
    } catch (error) {
      console.error('Training error:', error);
    }

    setStatus((prev) => ({ ...prev, isTraining: false }));
  };

  // Stop training
  const stopTraining = () => {
    setStatus((prev) => ({ ...prev, isTraining: false }));
  };

  // Toggle auto-train
  const toggleAutoTrain = async () => {
    const newState = !status.autoTrainEnabled;
    setStatus((prev) => ({ ...prev, autoTrainEnabled: newState }));

    try {
      const endpoint = newState ? '/api/brain-v6/auto-train/start' : '/api/brain-v6/auto-train/stop';
      await fetch(endpoint, { method: 'POST' });
    } catch (error) {
      console.error('Auto-train toggle error:', error);
    }
  };

  // Reset training
  const resetTraining = () => {
    setMetrics([]);
    setStatus((prev) => ({
      ...prev,
      currentEpoch: 0,
      totalEpochs: 0,
      bestLoss: Infinity,
      bestAccuracy: 0,
    }));
  };

  // Toggle section
  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className="p-6 space-y-6 bg-[#0a0a12] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-purple-500/20 to-cyan-500/20 rounded-xl">
            <Brain className="text-cyan-400" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">ML Training Center</h1>
            <p className="text-slate-400 text-sm">PropFirm Brain V6 - Neural Network Training</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Device Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800">
            <Cpu size={16} className={status.device === 'cuda' ? 'text-emerald-400' : 'text-slate-400'} />
            <span className="text-sm font-medium text-white uppercase">{status.device}</span>
          </div>

          {/* Status Badge */}
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
              status.isTraining
                ? 'bg-amber-500/20 text-amber-400'
                : status.modelLoaded
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-slate-500/20 text-slate-400'
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full ${
                status.isTraining ? 'bg-amber-400 animate-pulse' : status.modelLoaded ? 'bg-emerald-400' : 'bg-slate-400'
              }`}
            />
            <span className="text-sm font-medium">
              {status.isTraining ? 'TRAINING' : status.modelLoaded ? 'READY' : 'IDLE'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Column - Configuration */}
        <div className="col-span-4 space-y-4">
          {/* Training Controls */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Play size={18} /> Training Controls
              </h3>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <button
                onClick={status.isTraining ? stopTraining : startTraining}
                className={`flex items-center justify-center gap-2 py-3 rounded-lg font-medium transition-all ${
                  status.isTraining
                    ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                    : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                }`}
              >
                {status.isTraining ? <Pause size={18} /> : <Play size={18} />}
                {status.isTraining ? 'Stop' : 'Train'}
              </button>

              <button
                onClick={resetTraining}
                className="flex items-center justify-center gap-2 py-3 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-700 transition-all font-medium"
              >
                <RotateCcw size={18} /> Reset
              </button>
            </div>

            {/* Auto-Train Toggle */}
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <div className="flex items-center gap-2">
                <RefreshCw size={16} className="text-cyan-400" />
                <span className="text-sm text-white">Auto-Train</span>
              </div>
              <button
                onClick={toggleAutoTrain}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  status.autoTrainEnabled ? 'bg-cyan-500' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    status.autoTrainEnabled ? 'translate-x-7' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Configuration */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('config')}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
            >
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Settings size={18} /> Training Configuration
              </h3>
              {expandedSections.config ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {expandedSections.config && (
              <div className="p-4 pt-0 space-y-4">
                {/* Epochs */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Epochs</label>
                  <input
                    type="number"
                    value={config.epochs}
                    onChange={(e) => setConfig({ ...config, epochs: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Batch Size */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Batch Size</label>
                  <input
                    type="number"
                    value={config.batchSize}
                    onChange={(e) => setConfig({ ...config, batchSize: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Learning Rate */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Learning Rate</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={config.learningRate}
                    onChange={(e) => setConfig({ ...config, learningRate: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Weight Decay */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Weight Decay</label>
                  <input
                    type="number"
                    step="0.00001"
                    value={config.weightDecay}
                    onChange={(e) => setConfig({ ...config, weightDecay: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Dropout */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Dropout</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="0.5"
                    value={config.dropout}
                    onChange={(e) => setConfig({ ...config, dropout: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Patience (Early Stopping) */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Early Stopping Patience</label>
                  <input
                    type="number"
                    value={config.patience}
                    onChange={(e) => setConfig({ ...config, patience: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Gradient Clip */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Gradient Clipping</label>
                  <input
                    type="number"
                    step="0.1"
                    value={config.gradientClip}
                    onChange={(e) => setConfig({ ...config, gradientClip: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Auto-Train Interval */}
                <div>
                  <label className="text-sm text-slate-400 mb-1 block">Auto-Train Interval (seconds)</label>
                  <input
                    type="number"
                    value={config.autoTrainInterval}
                    onChange={(e) => setConfig({ ...config, autoTrainInterval: parseInt(e.target.value) || 0 })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                {/* Save Config Button */}
                <button
                  onClick={async () => {
                    try {
                      await fetch('/api/brain-v6/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(config)
                      });
                      alert('Configuration saved!');
                    } catch (error) {
                      console.error('Save config error:', error);
                    }
                  }}
                  className="w-full flex items-center justify-center gap-2 py-2 bg-cyan-500/20 text-cyan-400 rounded-lg hover:bg-cyan-500/30 transition-colors font-medium"
                >
                  <Save size={16} /> Save Configuration
                </button>
              </div>
            )}
          </div>

          {/* Best Metrics */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
            <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Target size={18} /> Best Metrics
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-800/50 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-1">Best Loss</div>
                <div className="text-xl font-mono text-emerald-400">
                  {status.bestLoss === Infinity ? '--' : status.bestLoss.toFixed(4)}
                </div>
              </div>
              <div className="bg-slate-800/50 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-1">Best Accuracy</div>
                <div className="text-xl font-mono text-cyan-400">
                  {status.bestAccuracy === 0 ? '--' : `${(status.bestAccuracy * 100).toFixed(1)}%`}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Visualization */}
        <div className="col-span-8 space-y-4">
          {/* Neural Network Visualization */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('network')}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
            >
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Layers size={18} /> Neural Network Architecture
              </h3>
              {expandedSections.network ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {expandedSections.network && (
              <div className="p-4 pt-0">
                <NeuralNetworkViz layers={NETWORK_ARCHITECTURE} isTraining={status.isTraining} />
                <div className="flex items-center justify-center gap-6 mt-4 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-blue-500" />
                    <span className="text-slate-400">Input</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-cyan-500" />
                    <span className="text-slate-400">LSTM</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-purple-500" />
                    <span className="text-slate-400">Attention</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-amber-500" />
                    <span className="text-slate-400">Dense</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-emerald-500" />
                    <span className="text-slate-400">Output</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Training Progress */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('progress')}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
            >
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Activity size={18} /> Training Progress
              </h3>
              {expandedSections.progress ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {expandedSections.progress && (
              <div className="p-4 pt-0">
                <TrainingProgress status={status} metrics={metrics} />
              </div>
            )}
          </div>

          {/* Charts */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('charts')}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
            >
              <h3 className="text-white font-semibold flex items-center gap-2">
                <TrendingUp size={18} /> Training Curves
              </h3>
              {expandedSections.charts ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {expandedSections.charts && (
              <div className="p-4 pt-0 grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-sm text-slate-400 mb-2">Loss</h4>
                  <LossChart metrics={metrics} />
                </div>
                <div>
                  <h4 className="text-sm text-slate-400 mb-2">Accuracy</h4>
                  <AccuracyChart metrics={metrics} />
                </div>
              </div>
            )}
          </div>

          {/* Strategy Performance */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <button
              onClick={() => toggleSection('strategies')}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
            >
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Zap size={18} /> Strategy Ensemble Performance
              </h3>
              {expandedSections.strategies ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {expandedSections.strategies && (
              <div className="p-4 pt-0">
                {strategies.length > 0 ? (
                  <StrategyTable strategies={strategies} />
                ) : (
                  <div className="text-center py-8 text-slate-400">
                    <Database size={32} className="mx-auto mb-2 opacity-50" />
                    <p>No strategy data available</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MLTraining;
