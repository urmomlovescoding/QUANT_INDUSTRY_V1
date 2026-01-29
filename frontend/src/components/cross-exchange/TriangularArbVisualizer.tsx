/**
 * Triangular Arb Visualizer
 * Triangle path visualization
 * QUANT_INDUSTRY_V1
 */

import React, { useMemo } from 'react';
import { TriangularArbPath } from '@/types/cross-exchange';

interface TriangularArbVisualizerProps {
  paths: TriangularArbPath[];
  onPathSelect?: (path: TriangularArbPath) => void;
}

const formatAmount = (value: number): string => {
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(2);
};

const TriangleDiagram: React.FC<{ path: TriangularArbPath }> = ({ path }) => {
  const { leg1, leg2, leg3 } = path;
  
  // Extract currencies from pairs
  const currencies = [
    leg1.pair.split('/')[0],
    leg1.pair.split('/')[1],
    leg2.pair.split('/')[1],
  ];

  const isProfitable = path.profitAfterFees > 0;

  return (
    <svg viewBox="0 0 200 180" className="w-full h-40">
      {/* Triangle vertices */}
      <g>
        {/* Top vertex */}
        <circle cx="100" cy="20" r="25" fill="#1F2937" stroke={isProfitable ? '#10B981' : '#6B7280'} strokeWidth="2" />
        <text x="100" y="24" textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">
          {currencies[0]}
        </text>
        
        {/* Bottom left vertex */}
        <circle cx="30" cy="150" r="25" fill="#1F2937" stroke={isProfitable ? '#10B981' : '#6B7280'} strokeWidth="2" />
        <text x="30" y="154" textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">
          {currencies[1]}
        </text>
        
        {/* Bottom right vertex */}
        <circle cx="170" cy="150" r="25" fill="#1F2937" stroke={isProfitable ? '#10B981' : '#6B7280'} strokeWidth="2" />
        <text x="170" y="154" textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">
          {currencies[2]}
        </text>
      </g>

      {/* Arrows */}
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill={isProfitable ? '#10B981' : '#6B7280'} />
        </marker>
      </defs>

      {/* Leg 1: Top to Bottom Left */}
      <line x1="80" y1="40" x2="50" y2="125" stroke={leg1.side === 'buy' ? '#10B981' : '#EF4444'} strokeWidth="2" markerEnd="url(#arrowhead)" />
      <text x="55" y="85" fill="#9CA3AF" fontSize="8" transform="rotate(-55 55 85)">
        {leg1.side.toUpperCase()} @ {leg1.price.toFixed(4)}
      </text>

      {/* Leg 2: Bottom Left to Bottom Right */}
      <line x1="55" y1="150" x2="145" y2="150" stroke={leg2.side === 'buy' ? '#10B981' : '#EF4444'} strokeWidth="2" markerEnd="url(#arrowhead)" />
      <text x="100" y="165" fill="#9CA3AF" fontSize="8" textAnchor="middle">
        {leg2.side.toUpperCase()} @ {leg2.price.toFixed(4)}
      </text>

      {/* Leg 3: Bottom Right to Top */}
      <line x1="150" y1="125" x2="120" y2="40" stroke={leg3.side === 'buy' ? '#10B981' : '#EF4444'} strokeWidth="2" markerEnd="url(#arrowhead)" />
      <text x="145" y="85" fill="#9CA3AF" fontSize="8" transform="rotate(55 145 85)">
        {leg3.side.toUpperCase()} @ {leg3.price.toFixed(4)}
      </text>
    </svg>
  );
};

const PathCard: React.FC<{
  path: TriangularArbPath;
  onSelect: () => void;
}> = ({ path, onSelect }) => {
  const isProfitable = path.profitAfterFees > 0;

  return (
    <div 
      className={`bg-gray-900/50 rounded-lg p-4 cursor-pointer transition-all border ${
        isProfitable ? 'border-green-500/30 hover:border-green-500/50' : 'border-gray-700/50 hover:border-gray-600'
      }`}
      onClick={onSelect}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <span className="text-white font-bold">{path.exchange}</span>
          <p className="text-gray-500 text-xs">
            {new Date(path.timestamp).toLocaleTimeString()}
          </p>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          path.status === 'completed' ? 'bg-green-500/20 text-green-400' :
          path.status === 'executing' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
          path.status === 'failed' ? 'bg-red-500/20 text-red-400' :
          'bg-gray-500/20 text-gray-400'
        }`}>
          {path.status.toUpperCase()}
        </span>
      </div>

      {/* Triangle Diagram */}
      <TriangleDiagram path={path} />

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2 mt-2">
        <div className="bg-gray-800/50 rounded p-2 text-center">
          <p className="text-gray-500 text-[10px]">Start</p>
          <p className="text-white text-sm font-medium">{formatAmount(path.startAmount)}</p>
        </div>
        <div className="bg-gray-800/50 rounded p-2 text-center">
          <p className="text-gray-500 text-[10px]">End</p>
          <p className={`text-sm font-medium ${path.endAmount > path.startAmount ? 'text-green-400' : 'text-red-400'}`}>
            {formatAmount(path.endAmount)}
          </p>
        </div>
      </div>

      <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-700">
        <div>
          <span className="text-gray-500 text-xs">Profit:</span>
          <span className={`ml-2 font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {path.profitPct > 0 ? '+' : ''}{(path.profitPct * 100).toFixed(3)}%
          </span>
        </div>
        <div>
          <span className="text-gray-500 text-xs">Net:</span>
          <span className={`ml-2 font-medium ${path.profitAfterFees > 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${path.profitAfterFees.toFixed(2)}
          </span>
        </div>
      </div>

      <p className="text-gray-500 text-xs mt-2 text-right">
        Exec time: {path.executionTimeMs}ms
      </p>
    </div>
  );
};

export const TriangularArbVisualizer: React.FC<TriangularArbVisualizerProps> = ({
  paths,
  onPathSelect,
}) => {
  const stats = useMemo(() => ({
    total: paths.length,
    profitable: paths.filter(p => p.profitAfterFees > 0).length,
    avgProfit: paths.length > 0 
      ? paths.reduce((sum, p) => sum + p.profitPct, 0) / paths.length 
      : 0,
  }), [paths]);

  if (paths.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-64">
        <p className="text-gray-500">No triangular arbitrage paths detected</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Triangular Arbitrage</h3>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-gray-400">{stats.total} paths</span>
          <span className="text-green-400">{stats.profitable} profitable</span>
          <span className={`font-medium ${stats.avgProfit > 0 ? 'text-green-400' : 'text-gray-400'}`}>
            Avg: {(stats.avgProfit * 100).toFixed(3)}%
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[500px] overflow-y-auto">
        {paths.map(path => (
          <PathCard
            key={path.id}
            path={path}
            onSelect={() => onPathSelect?.(path)}
          />
        ))}
      </div>
    </div>
  );
};

export default TriangularArbVisualizer;
