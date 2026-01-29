/**
 * Flow Model Metrics
 * ML model performance metrics
 * QUANT_INDUSTRY_V1
 */

import React, { useState } from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Cell,
} from 'recharts';
import { FlowModelMetrics as FlowModelMetricsType } from '@/types/microstructure';

interface FlowModelMetricsProps {
  metrics: FlowModelMetricsType[];
  onModelSelect?: (modelId: string) => void;
}

const MetricBadge: React.FC<{ value: number; threshold: { good: number; bad: number }; format?: string }> = ({
  value,
  threshold,
  format = 'percent',
}) => {
  const getColor = () => {
    if (value >= threshold.good) return 'bg-green-500/20 text-green-400';
    if (value >= threshold.bad) return 'bg-yellow-500/20 text-yellow-400';
    return 'bg-red-500/20 text-red-400';
  };

  const formatValue = () => {
    if (format === 'percent') return `${(value * 100).toFixed(1)}%`;
    if (format === 'ratio') return value.toFixed(2);
    return value.toFixed(3);
  };

  return (
    <span className={`px-2 py-1 rounded text-sm font-medium ${getColor()}`}>
      {formatValue()}
    </span>
  );
};

const ConfusionMatrixChart: React.FC<{ matrix: FlowModelMetricsType['confusionMatrix'] }> = ({ matrix }) => {
  const total = matrix.truePositive + matrix.falsePositive + matrix.trueNegative + matrix.falseNegative;
  
  const data = [
    { name: 'TP', value: matrix.truePositive, fill: '#10B981' },
    { name: 'FP', value: matrix.falsePositive, fill: '#EF4444' },
    { name: 'TN', value: matrix.trueNegative, fill: '#3B82F6' },
    { name: 'FN', value: matrix.falseNegative, fill: '#F59E0B' },
  ];

  return (
    <div className="bg-gray-900/50 rounded p-3">
      <p className="text-gray-400 text-sm mb-2">Confusion Matrix</p>
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={data} layout="vertical">
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" tick={{ fill: '#9CA3AF', fontSize: 11 }} width={30} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
            formatter={(value: number) => [`${value} (${((value/total)*100).toFixed(1)}%)`, 'Count']}
          />
          <Bar dataKey="value" radius={4}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

const RadarChartComponent: React.FC<{ metrics: FlowModelMetricsType }> = ({ metrics }) => {
  const radarData = [
    { subject: 'Accuracy', value: metrics.accuracy },
    { subject: 'Precision', value: metrics.precision },
    { subject: 'Recall', value: metrics.recall },
    { subject: 'F1 Score', value: metrics.f1Score },
    { subject: 'Hit Rate', value: metrics.hitRate },
  ];

  return (
    <ResponsiveContainer width="100%" height={200}>
      <RadarChart data={radarData}>
        <PolarGrid stroke="#374151" />
        <PolarAngleAxis dataKey="subject" tick={{ fill: '#9CA3AF', fontSize: 11 }} />
        <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: '#9CA3AF', fontSize: 9 }} />
        <Radar
          name="Performance"
          dataKey="value"
          stroke="#3B82F6"
          fill="#3B82F6"
          fillOpacity={0.4}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
};

const ModelCard: React.FC<{ 
  model: FlowModelMetricsType; 
  isSelected: boolean;
  onSelect: () => void;
}> = ({ model, isSelected, onSelect }) => (
  <div 
    className={`bg-gray-900/50 rounded-lg p-4 cursor-pointer transition-all ${
      isSelected ? 'ring-2 ring-blue-500' : 'hover:bg-gray-700/50'
    }`}
    onClick={onSelect}
  >
    <div className="flex justify-between items-start mb-3">
      <div>
        <h4 className="text-white font-medium">{model.modelName}</h4>
        <p className="text-gray-500 text-xs">{model.modelId}</p>
      </div>
      <MetricBadge 
        value={model.accuracy} 
        threshold={{ good: 0.7, bad: 0.5 }}
      />
    </div>

    <div className="grid grid-cols-4 gap-2 text-center mb-3">
      <div>
        <p className="text-gray-500 text-[10px]">Precision</p>
        <p className="text-white text-sm font-medium">{(model.precision * 100).toFixed(1)}%</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">Recall</p>
        <p className="text-white text-sm font-medium">{(model.recall * 100).toFixed(1)}%</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">F1</p>
        <p className="text-white text-sm font-medium">{(model.f1Score * 100).toFixed(1)}%</p>
      </div>
      <div>
        <p className="text-gray-500 text-[10px]">Sharpe</p>
        <p className="text-white text-sm font-medium">{model.sharpeRatio.toFixed(2)}</p>
      </div>
    </div>

    <div className="text-xs text-gray-500">
      Trained: {new Date(model.trainingDate).toLocaleDateString()}
    </div>
  </div>
);

export const FlowModelMetrics: React.FC<FlowModelMetricsProps> = ({
  metrics,
  onModelSelect,
}) => {
  const [selectedModelId, setSelectedModelId] = useState<string | null>(
    metrics.length > 0 ? metrics[0].modelId : null
  );

  const selectedModel = metrics.find(m => m.modelId === selectedModelId);

  const handleSelect = (modelId: string) => {
    setSelectedModelId(modelId);
    onModelSelect?.(modelId);
  };

  if (metrics.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-64">
        <p className="text-gray-500">No model metrics available</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-gray-300 font-medium mb-4">Flow Model Performance</h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Model List */}
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {metrics.map((model) => (
            <ModelCard
              key={model.modelId}
              model={model}
              isSelected={model.modelId === selectedModelId}
              onSelect={() => handleSelect(model.modelId)}
            />
          ))}
        </div>

        {/* Selected Model Details */}
        {selectedModel && (
          <div className="space-y-4">
            {/* Radar Chart */}
            <div className="bg-gray-900/50 rounded-lg p-3">
              <p className="text-gray-400 text-sm mb-2">Performance Overview</p>
              <RadarChartComponent metrics={selectedModel} />
            </div>

            {/* Confusion Matrix */}
            <ConfusionMatrixChart matrix={selectedModel.confusionMatrix} />

            {/* Performance by Regime */}
            {selectedModel.performanceByRegime && (
              <div className="bg-gray-900/50 rounded-lg p-3">
                <p className="text-gray-400 text-sm mb-2">Performance by Regime</p>
                <div className="space-y-2">
                  {Object.entries(selectedModel.performanceByRegime).map(([regime, data]) => (
                    <div key={regime} className="flex justify-between items-center">
                      <span className="text-gray-300 text-sm capitalize">{regime}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-gray-500 text-xs">{data.samples} samples</span>
                        <MetricBadge 
                          value={data.accuracy} 
                          threshold={{ good: 0.7, bad: 0.5 }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Additional Metrics */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-gray-900/50 rounded p-2 text-center">
                <p className="text-gray-500 text-[10px]">Avg Predicted</p>
                <p className={`text-sm font-medium ${
                  selectedModel.avgPredictedMove > 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {(selectedModel.avgPredictedMove * 100).toFixed(2)}%
                </p>
              </div>
              <div className="bg-gray-900/50 rounded p-2 text-center">
                <p className="text-gray-500 text-[10px]">Avg Actual</p>
                <p className={`text-sm font-medium ${
                  selectedModel.avgActualMove > 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {(selectedModel.avgActualMove * 100).toFixed(2)}%
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FlowModelMetrics;
