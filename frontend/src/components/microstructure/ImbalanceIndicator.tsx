/**
 * Imbalance Indicator
 * Real-time imbalance gauge
 * QUANT_INDUSTRY_V1
 */

import React from 'react';
import { ImbalanceMetrics } from '@/types/microstructure';

interface ImbalanceIndicatorProps {
  data: ImbalanceMetrics | null;
  size?: 'sm' | 'md' | 'lg';
}

const GaugeIndicator: React.FC<{
  value: number;
  label: string;
  min?: number;
  max?: number;
  thresholds?: { warning: number; critical: number };
}> = ({ value, label, min = -1, max = 1, thresholds = { warning: 0.3, critical: 0.6 } }) => {
  const normalizedValue = ((value - min) / (max - min)) * 100;
  const clampedValue = Math.max(0, Math.min(100, normalizedValue));
  
  const getColor = (v: number) => {
    const absV = Math.abs(v);
    if (absV >= thresholds.critical) return v > 0 ? 'text-green-400' : 'text-red-400';
    if (absV >= thresholds.warning) return v > 0 ? 'text-green-300' : 'text-red-300';
    return 'text-gray-400';
  };

  const getBgColor = (v: number) => {
    const absV = Math.abs(v);
    if (absV >= thresholds.critical) return v > 0 ? 'bg-green-500' : 'bg-red-500';
    if (absV >= thresholds.warning) return v > 0 ? 'bg-green-400' : 'bg-red-400';
    return 'bg-gray-500';
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-gray-400 text-sm">{label}</span>
        <span className={`font-medium ${getColor(value)}`}>
          {(value * 100).toFixed(1)}%
        </span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div 
          className={`h-full ${getBgColor(value)} transition-all duration-300`}
          style={{ 
            width: `${clampedValue}%`,
            marginLeft: value < 0 ? 'auto' : 0,
            marginRight: value > 0 ? 'auto' : 0,
          }}
        />
      </div>
    </div>
  );
};

const CircularGauge: React.FC<{
  value: number;
  size: number;
  strokeWidth?: number;
}> = ({ value, size, strokeWidth = 8 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const normalizedValue = (value + 1) / 2; // -1 to 1 -> 0 to 1
  const offset = circumference * (1 - normalizedValue);
  
  const getColor = () => {
    if (value > 0.3) return '#10B981';
    if (value < -0.3) return '#EF4444';
    return '#6B7280';
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#374151"
          strokeWidth={strokeWidth}
        />
        {/* Value circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getColor()}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-2xl font-bold ${value > 0 ? 'text-green-400' : value < 0 ? 'text-red-400' : 'text-gray-400'}`}>
          {(value * 100).toFixed(0)}%
        </span>
        <span className="text-gray-500 text-xs">
          {value > 0.1 ? 'BUY' : value < -0.1 ? 'SELL' : 'NEUTRAL'}
        </span>
      </div>
    </div>
  );
};

export const ImbalanceIndicator: React.FC<ImbalanceIndicatorProps> = ({
  data,
  size = 'md',
}) => {
  if (!data) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-64">
        <p className="text-gray-500">No imbalance data available</p>
      </div>
    );
  }

  const gaugeSize = size === 'sm' ? 120 : size === 'lg' ? 200 : 160;

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Order Imbalance</h3>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          data.direction === 'buy' ? 'bg-green-500/20 text-green-400' :
          data.direction === 'sell' ? 'bg-red-500/20 text-red-400' :
          'bg-gray-500/20 text-gray-400'
        }`}>
          {data.direction.toUpperCase()}
        </span>
      </div>

      <div className="flex items-center justify-center gap-8">
        {/* Main Gauge */}
        <CircularGauge value={data.volumeImbalance} size={gaugeSize} />

        {/* Metrics */}
        <div className="flex-1 space-y-4">
          <GaugeIndicator 
            value={data.volumeImbalance} 
            label="Volume Imbalance"
          />
          <GaugeIndicator 
            value={data.orderImbalance} 
            label="Order Imbalance"
          />
          <GaugeIndicator 
            value={data.tradeImbalance} 
            label="Trade Imbalance"
          />
          <GaugeIndicator 
            value={data.vwapImbalance} 
            label="VWAP Imbalance"
          />
        </div>
      </div>

      {/* Prediction Section */}
      <div className="mt-4 pt-4 border-t border-gray-700">
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-gray-400 text-xs">Predicted Move</p>
            <p className={`text-lg font-bold ${
              data.predictedMove > 0 ? 'text-green-400' : 
              data.predictedMove < 0 ? 'text-red-400' : 'text-gray-400'
            }`}>
              {data.predictedMove > 0 ? '+' : ''}{(data.predictedMove * 100).toFixed(2)}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-gray-400 text-xs">Confidence</p>
            <p className="text-white font-bold text-lg">{(data.confidence * 100).toFixed(0)}%</p>
          </div>
          <div className="text-center">
            <p className="text-gray-400 text-xs">Historical Accuracy</p>
            <p className="text-blue-400 font-bold text-lg">{(data.historicalAccuracy * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImbalanceIndicator;
