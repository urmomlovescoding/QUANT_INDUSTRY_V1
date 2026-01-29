/**
 * Order Book Heatmap
 * Visual order book depth
 * QUANT_INDUSTRY_V1
 */

import React, { useMemo } from 'react';
import { OrderBook, OrderBookLevel } from '@/types/microstructure';

interface OrderBookHeatmapProps {
  data: OrderBook | null;
  levels?: number;
  showDepth?: boolean;
}

const formatSize = (size: number): string => {
  if (size >= 1e6) return `${(size / 1e6).toFixed(1)}M`;
  if (size >= 1e3) return `${(size / 1e3).toFixed(0)}K`;
  return size.toFixed(0);
};

const LevelRow: React.FC<{
  level: OrderBookLevel;
  maxSize: number;
  side: 'bid' | 'ask';
}> = ({ level, maxSize, side }) => {
  const intensity = Math.min(1, level.size / maxSize);
  const bgColor = side === 'bid' 
    ? `rgba(16, 185, 129, ${intensity * 0.5})` 
    : `rgba(239, 68, 68, ${intensity * 0.5})`;
  
  return (
    <div 
      className="flex items-center justify-between px-2 py-1 text-xs font-mono hover:brightness-125 transition-all"
      style={{ backgroundColor: bgColor }}
    >
      <span className={`w-20 text-right ${side === 'bid' ? 'text-green-400' : 'text-red-400'}`}>
        {formatSize(level.size)}
      </span>
      <span className="text-white font-medium">${level.price.toFixed(2)}</span>
      <span className="w-16 text-right text-gray-400">{level.orders}</span>
    </div>
  );
};

const DepthBar: React.FC<{ 
  bidDepth: number; 
  askDepth: number; 
  total: number;
}> = ({ bidDepth, askDepth, total }) => {
  const bidPct = (bidDepth / total) * 100;
  const askPct = (askDepth / total) * 100;
  
  return (
    <div className="flex h-6 w-full rounded overflow-hidden">
      <div 
        className="bg-green-500/50 flex items-center justify-end px-2"
        style={{ width: `${bidPct}%` }}
      >
        <span className="text-xs text-green-300">{bidPct.toFixed(0)}%</span>
      </div>
      <div 
        className="bg-red-500/50 flex items-center px-2"
        style={{ width: `${askPct}%` }}
      >
        <span className="text-xs text-red-300">{askPct.toFixed(0)}%</span>
      </div>
    </div>
  );
};

export const OrderBookHeatmap: React.FC<OrderBookHeatmapProps> = ({
  data,
  levels = 15,
  showDepth = true,
}) => {
  const { bids, asks, maxSize, totalBid, totalAsk } = useMemo(() => {
    if (!data) {
      return { bids: [], asks: [], maxSize: 1, totalBid: 0, totalAsk: 0 };
    }
    
    const bids = data.bids.slice(0, levels);
    const asks = data.asks.slice(0, levels);
    const allSizes = [...bids, ...asks].map(l => l.size);
    const maxSize = Math.max(...allSizes, 1);
    const totalBid = bids.reduce((sum, l) => sum + l.size, 0);
    const totalAsk = asks.reduce((sum, l) => sum + l.size, 0);
    
    return { bids, asks, maxSize, totalBid, totalAsk };
  }, [data, levels]);

  if (!data) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-96">
        <p className="text-gray-500">No order book data available</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-gray-300 font-medium">Order Book</h3>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-400">
            Spread: <span className="text-white font-medium">${data.spread.toFixed(2)}</span>
            <span className="text-gray-500 ml-1">({data.spreadBps.toFixed(1)} bps)</span>
          </span>
          <span className={`font-medium ${data.imbalance > 0 ? 'text-green-400' : 'text-red-400'}`}>
            Imbalance: {(data.imbalance * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Depth Bar */}
      {showDepth && (
        <div className="mb-4">
          <DepthBar bidDepth={totalBid} askDepth={totalAsk} total={totalBid + totalAsk} />
        </div>
      )}

      {/* Order Book Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Bids */}
        <div>
          <div className="flex justify-between px-2 py-1 text-xs text-gray-400 border-b border-gray-700">
            <span className="w-20 text-right">Size</span>
            <span>Bid</span>
            <span className="w-16 text-right">Orders</span>
          </div>
          <div className="space-y-0.5 mt-1">
            {bids.map((level, i) => (
              <LevelRow 
                key={`bid-${i}`} 
                level={level} 
                maxSize={maxSize} 
                side="bid"
              />
            ))}
          </div>
        </div>

        {/* Asks */}
        <div>
          <div className="flex justify-between px-2 py-1 text-xs text-gray-400 border-b border-gray-700">
            <span className="w-20 text-right">Size</span>
            <span>Ask</span>
            <span className="w-16 text-right">Orders</span>
          </div>
          <div className="space-y-0.5 mt-1">
            {asks.map((level, i) => (
              <LevelRow 
                key={`ask-${i}`} 
                level={level} 
                maxSize={maxSize} 
                side="ask"
              />
            ))}
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-700">
        <div className="text-center">
          <p className="text-gray-400 text-xs">Mid Price</p>
          <p className="text-white font-bold">${data.midPrice.toFixed(2)}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Bid Depth (1%)</p>
          <p className="text-green-400 font-bold">{(data.depth.bid1Pct * 100).toFixed(0)}%</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Ask Depth (1%)</p>
          <p className="text-red-400 font-bold">{(data.depth.ask1Pct * 100).toFixed(0)}%</p>
        </div>
        <div className="text-center">
          <p className="text-gray-400 text-xs">Total Depth</p>
          <p className="text-white font-bold">{formatSize(totalBid + totalAsk)}</p>
        </div>
      </div>
    </div>
  );
};

export default OrderBookHeatmap;
