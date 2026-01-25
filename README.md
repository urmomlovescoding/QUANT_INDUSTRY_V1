# QUANT INDUSTRY v10.0 - Professional Trading Platform

A comprehensive institutional-grade trading platform with React frontend and FastAPI backend.

## Features

### Markets
- **Dashboard** - Portfolio overview with equity curves, P&L charts, and key metrics
- **Stock Screener** - Multi-ticker scanner with technical analysis (RSI, trend, signals)
- **Charts & Technicals** - Interactive candlestick charts with multiple timeframes and indicators

### Options
- **Options Lab** - Smart options analysis with Greeks, IV analysis, and option rating
- **GEX Analysis** - Gamma Exposure analysis by strike with visualization
- **Flow Scanner** - Smart money flow detection
- **Strategies** - Pre-built strategy library

### Quant
- **Quant Platform** - Institutional grade with 6 tabs:
  - Portfolio Optimizer (Max Sharpe, Min Variance, Risk Parity)
  - Strategy Registry
  - Walk-Forward Testing
  - Performance Metrics
  - Experiments
  - ML Brain Visualization
- **Trade Confirm** - AI trade confirmation with scoring and analysis
- **Benchmark** - Portfolio benchmark management
- **Risk Engine** - Real-time risk monitoring with limits and alerts
- **Slide Doctrine** - ML model compliance

### Analytics
- **Backtesting** - Institutional backtester with equity curves and metrics
- **Monte Carlo** - Portfolio simulation and risk analysis
- **Correlation** - Asset correlation matrix and analysis

### Neural AI
- **Neural Analysis** - AI-powered pattern recognition
- **ML Predictions** - Machine learning price forecasting with multiple models
- **Regime Detect** - Market regime classification (Bull/Bear/Ranging)
- **Trading Brain** - Multi-cycle intelligence system
- **Algo Bot** - Quant Brain v10.0 algorithmic trading bot

### Prop Firm
- **TPT Dashboard** - Prop firm trading dashboard
- **Futures Brain** - Futures trading AI

### Research
- **13F Holdings** - Institutional investor holdings tracker
- **SEC Filings** - SEC EDGAR database search
- **Dark Pool** - Off-exchange trading activity analysis
- **Earnings** - Earnings calendar and surprise tracking
- **News Center** - Market news and sentiment analysis

### Portfolio
- **Holdings** - Portfolio management with P&L tracking
- **Pairs Trading** - Statistical arbitrage pair detection
- **Reports** - Trading report generation

### System
- **API Connector** - Broker and data API connections
- **Settings** - Platform configuration

## Tech Stack

### Frontend
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Recharts (charting)
- React Router (navigation)
- Zustand (state management)

### Backend
- FastAPI (Python)
- Pydantic (data validation)
- WebSockets (real-time data)
- Uvicorn (ASGI server)

## Prerequisites

1. **Python 3.9+** - Download from https://python.org/
2. **Node.js 18+** - Download from https://nodejs.org/

## Quick Start

### Option 1: Start Everything
```bash
# From the QUANT_INDUSTRY_V1 directory
START.bat
```

### Option 2: Start Separately

**Backend:**
```bash
cd backend
start.bat
```
Backend will be available at: http://localhost:8000
API Documentation at: http://localhost:8000/docs

**Frontend:**
```bash
cd frontend
start.bat
```
Frontend will be available at: http://localhost:3000

## Project Structure

```
QUANT_INDUSTRY_V1/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── start.bat           # Backend startup script
├── frontend/
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   │   ├── layout/     # Layout components (Sidebar, Header)
│   │   │   ├── charts/     # Chart components
│   │   │   ├── cards/      # Metric cards
│   │   │   └── ui/         # Base UI components
│   │   ├── views/          # Page views (30+ views)
│   │   ├── hooks/          # Custom React hooks
│   │   ├── store/          # State management
│   │   ├── types/          # TypeScript types
│   │   ├── utils/          # Utility functions
│   │   └── api/            # API client
│   ├── package.json        # Node dependencies
│   ├── tailwind.config.js  # Tailwind configuration
│   ├── vite.config.ts      # Vite configuration
│   └── start.bat          # Frontend startup script
├── START.bat              # Master startup script
└── README.md              # This file
```

## API Endpoints

### Market Data
- `GET /api/market/tickers` - Get live ticker prices
- `GET /api/market/quote/{symbol}` - Get detailed quote
- `GET /api/market/sectors` - Get sector performance
- `GET /api/market/movers` - Get top gainers/losers

### Screener
- `GET /api/screener/scan` - Scan stocks with technical analysis

### Charts
- `GET /api/charts/ohlcv/{symbol}` - Get OHLCV data
- `GET /api/charts/indicators/{symbol}` - Get technical indicators

### Options
- `GET /api/options/chain/{symbol}` - Get options chain
- `GET /api/options/gex/{symbol}` - Get GEX analysis

### Trading
- `GET /api/signals/active` - Get active trading signals
- `GET /api/positions` - Get open positions
- `POST /api/ai/confirm-trade` - AI trade confirmation

### Analytics
- `POST /api/backtest/run` - Run backtest
- `GET /api/risk/metrics` - Get risk metrics

### Neural AI
- `GET /api/neural/analysis/{symbol}` - Get neural analysis
- `GET /api/neural/predictions/{symbol}` - Get ML predictions
- `GET /api/neural/regime` - Get regime detection

### Research
- `GET /api/research/13f/{symbol}` - Get 13F holdings
- `GET /api/research/sec/{symbol}` - Get SEC filings
- `GET /api/research/darkpool/{symbol}` - Get dark pool data
- `GET /api/research/earnings` - Get earnings calendar

### Portfolio
- `GET /api/portfolio/holdings` - Get holdings
- `GET /api/portfolio/performance` - Get performance metrics

### WebSocket
- `WS /ws/market` - Real-time market data stream

## Keyboard Shortcuts

- `F11` - Toggle fullscreen
- `Ctrl+K` - Command palette (coming soon)

## Theme

The platform uses a Bloomberg Terminal-inspired dark theme with:
- Deep blue-black background (#0a0a12)
- Cyan/teal accent color (#00d4aa)
- Green for bullish (#00c853)
- Red for bearish (#ff5252)

## License

Proprietary - All rights reserved
