/**
 * Backtest Visualization View
 * Wrapper that fetches data and renders BacktestVisualization component
 */

import React, { useState, useEffect } from 'react';
import { BacktestVisualization } from '../components/BacktestVisualization';

// Generate sample data for demonstration
function generateSampleData() {
  const equity: any[] = [];
  const trades: any[] = [];
  const rollingMetrics: any[] = [];
  const factorExposure: any[] = [];

  let equityValue = 100000;
  const startDate = new Date('2024-01-01');

  // Generate 252 trading days of data
  for (let i = 0; i < 252; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    const dateStr = date.toISOString().split('T')[0];

    // Random daily return between -3% and 3%
    const dailyReturn = (Math.random() - 0.48) * 0.03;
    equityValue *= (1 + dailyReturn);

    const peak = equity.reduce((max, e) => Math.max(max, e.equity), equityValue);
    const drawdown = ((equityValue - peak) / peak) * 100;

    equity.push({
      date: dateStr,
      equity: Math.round(equityValue * 100) / 100,
      benchmark: 100000 * (1 + i * 0.0004),
      drawdown: Math.round(drawdown * 100) / 100,
      returns: Math.round(dailyReturn * 10000) / 100,
    });

    // Generate some trades
    if (Math.random() > 0.9) {
      trades.push({
        date: dateStr,
        pnl: (Math.random() - 0.45) * 2000,
        holdingPeriod: Math.floor(Math.random() * 10) + 1,
        size: Math.floor(Math.random() * 1000) + 100,
        symbol: ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'][Math.floor(Math.random() * 5)],
        side: Math.random() > 0.5 ? 'long' : 'short',
      });
    }

    // Rolling metrics every 20 days
    if (i % 20 === 0 && i > 0) {
      rollingMetrics.push({
        date: dateStr,
        sharpe: Math.random() * 3 - 0.5,
        sortino: Math.random() * 4 - 0.5,
        calmar: Math.random() * 2,
        winRate: 0.4 + Math.random() * 0.3,
        profitFactor: 0.8 + Math.random() * 1.5,
        avgWin: 500 + Math.random() * 1000,
        avgLoss: -(300 + Math.random() * 700),
      });
    }
  }

  // Factor exposure
  const factors = ['Momentum', 'Value', 'Size', 'Quality', 'Volatility', 'Market'];
  factors.forEach(factor => {
    factorExposure.push({
      factor,
      exposure: Math.random() * 2 - 1,
      contribution: (Math.random() - 0.5) * 5,
    });
  });

  return { equity, trades, rollingMetrics, factorExposure };
}

export function BacktestViz() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate API call
    setTimeout(() => {
      setData(generateSampleData());
      setLoading(false);
    }, 500);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Advanced Backtest Visualization</h1>
      <BacktestVisualization
        equity={data.equity}
        trades={data.trades}
        rollingMetrics={data.rollingMetrics}
        factorExposures={data.factorExposure}
      />
    </div>
  );
}

export default BacktestViz;
