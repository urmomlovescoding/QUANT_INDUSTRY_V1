/**
 * Gamma Exposure Chart
 * GEX profile visualization (area chart)
 * QUANT_INDUSTRY_V1
 */

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
  ComposedChart,
  Bar,
} from 'recharts';
import { GammaExposureProfile, GammaExposureLevel } from '@/types/options-flow';

interface GammaExposureChartProps {
  data: GammaExposureProfile | null;
  height?: number;
}

const formatGamma = (value: number): string => {
  const absValue = Math.abs(value);
  if (absValue >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (absValue >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (absValue >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toFixed(0);
};

const CustomTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload as GammaExposureLevel;
  if (!data) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl">
      <p className="text-white font-bold">${label}</p>
      <div className="space-y-1 mt-2 text-sm">
        <div className="flex justify-between gap-4">
          <span className="text-green-400">Call Gamma:</span>
          <span className="text-green-400 font-medium">{formatGamma(data.callGamma)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-red-400">Put Gamma:</span>
          <span className="text-red-400 font-medium">{formatGamma(data.putGamma)}</span>
        </div>
        <div className="flex justify-between gap-4 border-t border-gray-700 pt-1">
          <span className="text-gray-300">Net Gamma:</span>
          <span className={data.netGamma >= 0 ? 'text-green-400' : 'text-red-400'}>
            {formatGamma(data.netGamma)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-300">Open Interest:</span>
          <span className="text-gray-300">{data.openInterest?.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
};

export const GammaExposureChart: React.FC<GammaExposureChartProps> = ({ data, height = 400 }) => {
  if (!data || !data.levels || data.levels.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center" style={{ height }}>
        <p className="text-gray-500">No gamma exposure data available</p>
      </div>
    );
  }

  const { levels, spotPrice, gammaFlip, maxPainStrike, callWall, putWall } = data;

  // Sort levels by strike
  const sortedLevels = [...levels].sort((a, b) => a.strike - b.strike);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Gamma Exposure Profile</h3>
        <div className="flex gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Spot:</span>
            <span className="text-white font-bold">${spotPrice?.toFixed(2)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">GEX Flip:</span>
            <span className="text-yellow-400 font-bold">${gammaFlip?.toFixed(0)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Max Pain:</span>
            <span className="text-purple-400 font-bold">${maxPainStrike?.toFixed(0)}</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={height - 60}>
        <ComposedChart data={sortedLevels} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="strike" 
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            tickFormatter={(v) => `$${v}`}
          />
          <YAxis 
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            tickFormatter={formatGamma}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />

          {/* Call and Put Gamma Bars */}
          <Bar dataKey="callGamma" name="Call GEX" fill="#10B981" fillOpacity={0.6} />
          <Bar dataKey="putGamma" name="Put GEX" fill="#EF4444" fillOpacity={0.6} />

          {/* Net Gamma Area */}
          <Area
            type="monotone"
            dataKey="netGamma"
            name="Net GEX"
            stroke="#3B82F6"
            fill="#3B82F6"
            fillOpacity={0.3}
            strokeWidth={2}
          />

          {/* Reference Lines */}
          <ReferenceLine
            x={spotPrice}
            stroke="#FFFFFF"
            strokeWidth={2}
            strokeDasharray="5 5"
            label={{ value: 'Spot', fill: '#FFFFFF', fontSize: 11 }}
          />
          {gammaFlip && (
            <ReferenceLine
              x={gammaFlip}
              stroke="#FBBF24"
              strokeWidth={2}
              strokeDasharray="3 3"
              label={{ value: 'Flip', fill: '#FBBF24', fontSize: 11 }}
            />
          )}
          {callWall && (
            <ReferenceLine
              x={callWall}
              stroke="#10B981"
              strokeWidth={1}
              strokeDasharray="3 3"
              label={{ value: 'Call Wall', fill: '#10B981', fontSize: 10 }}
            />
          )}
          {putWall && (
            <ReferenceLine
              x={putWall}
              stroke="#EF4444"
              strokeWidth={1}
              strokeDasharray="3 3"
              label={{ value: 'Put Wall', fill: '#EF4444', fontSize: 10 }}
            />
          )}
          <ReferenceLine y={0} stroke="#6B7280" strokeWidth={1} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-700">
        <div className="text-center">
          <p className="text-gray-400 text-xs">Total Net GEX</p>
          <p className={`text-lg font-bold ${data.totalNetGamma >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatGamma(data.totalNetGamma)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Call Wall</p>
          <p className="text-green-400 text-lg font-bold">${callWall?.toFixed(0) || '—'}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Put Wall</p>
          <p className="text-red-400 text-lg font-bold">${putWall?.toFixed(0) || '—'}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Expected Move</p>
          <p className="text-blue-400 text-lg font-bold">±{(data.expectedMove * 100).toFixed(1)}%</p>
        </div>
      </div>
    </div>
  );
};

export default GammaExposureChart;
