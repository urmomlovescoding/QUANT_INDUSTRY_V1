# QUANT INDUSTRY - Professional Trading UI

A modern React-based trading platform UI with professional charts, metrics, and real-time data visualization.

## Features

- **Professional Dark Theme** - Gold/yellow accent colors matching reference designs
- **Dashboard** - Portfolio overview with equity curves, P&L charts, and key metrics
- **Signals** - Active trading signals with confidence bars and execution controls
- **Positions** - Open positions management with P&L tracking
- **Performance** - Detailed trading statistics matching institutional standards
- **Analytics** - Strategy comparison, risk metrics, and monthly returns heatmap
- **Settings** - Full configuration panel for appearance, trading, and risk management

## Tech Stack

- **React 18** - Modern React with hooks
- **TypeScript** - Full type safety
- **Vite** - Fast development and building
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Professional charting
- **Zustand** - State management
- **React Query** - Data fetching and caching
- **Radix UI** - Accessible component primitives

## Prerequisites

1. **Node.js 18+** - Download from https://nodejs.org/
2. **npm** or **pnpm**

## Installation

```bash
# Navigate to frontend directory
cd C:\QUANT_INDUSTRY_V1\frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at http://localhost:3000

## Build for Production

```bash
npm run build
```

Output will be in the `dist` folder.

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/      # Layout components (Sidebar, Header, etc.)
│   │   ├── charts/      # Chart components (Area, Bar, Donut, Gauge)
│   │   ├── cards/       # Metric cards
│   │   ├── tables/      # Data tables
│   │   └── ui/          # Base UI components
│   ├── views/           # Page views
│   │   ├── Dashboard.tsx
│   │   ├── Signals.tsx
│   │   ├── Positions.tsx
│   │   ├── Performance.tsx
│   │   ├── Analytics.tsx
│   │   └── Settings.tsx
│   ├── hooks/           # Custom hooks
│   ├── store/           # State management
│   ├── types/           # TypeScript types
│   ├── utils/           # Utility functions
│   └── api/             # API client
├── public/              # Static assets
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Connecting to Backend

The frontend is configured to proxy API requests to `http://localhost:8000`.
Start your Python/FastAPI backend on port 8000.

## Screenshots

The UI matches professional trading platforms with:
- Dark theme with gold accents
- Real-time price tickers
- Professional data grids
- Interactive charts
- Risk gauges and meters
