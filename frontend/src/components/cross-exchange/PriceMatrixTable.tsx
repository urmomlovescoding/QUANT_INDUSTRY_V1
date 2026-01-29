/**
 * Price Matrix Table
 * Cross-exchange price comparison
 * QUANT_INDUSTRY_V1
 */

import React, { useMemo } from 'react';
import { PriceMatrix, ExchangePrice } from '@/types/cross-exchange';

interface PriceMatrixTableProps {
  data: PriceMatrix[];
  onSymbolClick?: (symbol: string) => void;
}

const formatPrice = (price: number, decimals: number = 2): string => {
  return `$${price.toFixed(decimals)}`;
};

const SpreadBadge: React.FC<{ spreadBps: number }> = ({ spreadBps }) => {
  const getColor = () => {
    if (spreadBps < 5) return 'bg-green-500/20 text-green-400';
    if (spreadBps < 15) return 'bg-yellow-500/20 text-yellow-400';
    return 'bg-red-500/20 text-red-400';
  };

  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${getColor()}`}>
      {spreadBps.toFixed(1)} bps
    </span>
  );
};

const ExchangeTypeBadge: React.FC<{ type: 'cex' | 'dex' }> = ({ type }) => (
  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
    type === 'cex' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
  }`}>
    {type.toUpperCase()}
  </span>
);

const PriceCell: React.FC<{ 
  price: ExchangePrice; 
  isBestBid: boolean; 
  isBestAsk: boolean;
}> = ({ price, isBestBid, isBestAsk }) => (
  <td className="p-2 text-center">
    <div className="space-y-1">
      <div className="flex justify-between items-center px-2">
        <span className={`text-xs ${isBestBid ? 'text-green-400 font-bold' : 'text-green-300'}`}>
          {formatPrice(price.bid)}
        </span>
        <span className="text-gray-500 text-[10px] mx-1">/</span>
        <span className={`text-xs ${isBestAsk ? 'text-red-400 font-bold' : 'text-red-300'}`}>
          {formatPrice(price.ask)}
        </span>
      </div>
      <div className="flex justify-center items-center gap-1">
        <SpreadBadge spreadBps={price.spreadBps} />
        {price.latencyMs > 100 && (
          <span className="text-yellow-500 text-[10px]">⚠ {price.latencyMs}ms</span>
        )}
      </div>
    </div>
  </td>
);

export const PriceMatrixTable: React.FC<PriceMatrixTableProps> = ({
  data,
  onSymbolClick,
}) => {
  const exchanges = useMemo(() => {
    const allExchanges = new Set<string>();
    data.forEach(matrix => {
      matrix.prices.forEach(p => allExchanges.add(p.exchange));
    });
    return Array.from(allExchanges);
  }, [data]);

  const exchangeTypes = useMemo(() => {
    const types: Record<string, 'cex' | 'dex'> = {};
    data.forEach(matrix => {
      matrix.prices.forEach(p => {
        types[p.exchange] = p.exchangeType;
      });
    });
    return types;
  }, [data]);

  if (data.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 flex items-center justify-center h-64">
        <p className="text-gray-500">No price data available</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-gray-300 font-medium mb-4">Cross-Exchange Price Matrix</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left p-2 text-gray-400">Symbol</th>
              <th className="text-center p-2 text-gray-400">Best Bid</th>
              <th className="text-center p-2 text-gray-400">Best Ask</th>
              <th className="text-center p-2 text-gray-400">Max Spread</th>
              {exchanges.map(exchange => (
                <th key={exchange} className="text-center p-2">
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-gray-300">{exchange}</span>
                    <ExchangeTypeBadge type={exchangeTypes[exchange]} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((matrix) => (
              <tr 
                key={matrix.symbol} 
                className="border-b border-gray-700/50 hover:bg-gray-700/30 cursor-pointer"
                onClick={() => onSymbolClick?.(matrix.symbol)}
              >
                <td className="p-2">
                  <span className="text-white font-bold">{matrix.symbol}</span>
                </td>
                <td className="p-2 text-center">
                  <div>
                    <span className="text-green-400 font-medium">{formatPrice(matrix.bestBid.price)}</span>
                    <p className="text-gray-500 text-xs">{matrix.bestBid.exchange}</p>
                  </div>
                </td>
                <td className="p-2 text-center">
                  <div>
                    <span className="text-red-400 font-medium">{formatPrice(matrix.bestAsk.price)}</span>
                    <p className="text-gray-500 text-xs">{matrix.bestAsk.exchange}</p>
                  </div>
                </td>
                <td className="p-2 text-center">
                  <span className={`font-medium ${
                    matrix.maxSpread > 0.002 ? 'text-yellow-400' : 'text-gray-400'
                  }`}>
                    {(matrix.maxSpread * 100).toFixed(2)}%
                  </span>
                </td>
                {exchanges.map(exchange => {
                  const price = matrix.prices.find(p => p.exchange === exchange);
                  if (!price) {
                    return (
                      <td key={exchange} className="p-2 text-center text-gray-600">
                        —
                      </td>
                    );
                  }
                  return (
                    <PriceCell
                      key={exchange}
                      price={price}
                      isBestBid={matrix.bestBid.exchange === exchange}
                      isBestAsk={matrix.bestAsk.exchange === exchange}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PriceMatrixTable;
