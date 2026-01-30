import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from './components/ui/Toaster'
import { Layout } from './components/layout/Layout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { CommandPalette, useCommandPalette } from './components/CommandPalette'
import { NotificationProvider } from './components/NotificationSystem'
import { QuickTrade, useQuickTrade } from './components/QuickTrade'

// Market views
import { Dashboard } from './views/Dashboard'
import { Screener } from './views/Screener'
import { Charts } from './views/Charts'

// Options views
import { OptionsLab } from './views/OptionsLab'
import { GEXAnalysis } from './views/GEXAnalysis'
import { FlowScanner } from './views/FlowScanner'
import { Strategies } from './views/Strategies'

// Quant views
import { QuantPlatform } from './views/QuantPlatform'
import { TradeConfirm } from './views/TradeConfirm'
import { Benchmark } from './views/Benchmark'
import { RiskEngine } from './views/RiskEngine'
import { SlideDoctrine } from './views/SlideDoctrine'

// Analytics views
import { Backtesting } from './views/Backtesting'
import { MonteCarlo } from './views/MonteCarlo'
import { Correlation } from './views/Correlation'

// Neural AI views
import { NeuralAnalysis } from './views/NeuralAnalysis'
import { MLPredictions } from './views/MLPredictions'
import { RegimeDetect } from './views/RegimeDetect'
import { TradingBrain } from './views/TradingBrain'
import { AlgoBot } from './views/AlgoBot'
import { UnifiedBrain } from './views/UnifiedBrain'
import MLTraining from './views/MLTraining'
import { MarketMicrostructure } from './views/MarketMicrostructure'

// Prop Firm views
import { TPTDashboard } from './views/TPTDashboard'
import { FuturesBrain } from './views/FuturesBrain'

// Research views
import { Holdings13F } from './views/Holdings13F'
import { SECFilings } from './views/SECFilings'
import { DarkPool } from './views/DarkPool'
import { Earnings } from './views/Earnings'
import { News } from './views/News'

// Portfolio views
import { Portfolio } from './views/Portfolio'
import { PairsTrading } from './views/PairsTrading'
import { Reports } from './views/Reports'

// System views
import { APIConnector } from './views/APIConnector'
import { Settings } from './views/Settings'

// Legacy views for compatibility
import { Signals } from './views/Signals'
import { Positions } from './views/Positions'
import { Performance } from './views/Performance'
import { Analytics } from './views/Analytics'

function AppContent() {
  const commandPalette = useCommandPalette()
  const quickTrade = useQuickTrade()

  return (
    <>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Markets */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/screener" element={<Screener />} />
          <Route path="/charts" element={<Charts />} />

          {/* Options */}
          <Route path="/options-lab" element={<OptionsLab />} />
          <Route path="/gex-analysis" element={<GEXAnalysis />} />
          <Route path="/flow-scanner" element={<FlowScanner />} />
          <Route path="/strategies" element={<Strategies />} />

          {/* Quant */}
          <Route path="/quant-platform" element={<QuantPlatform />} />
          <Route path="/trade-confirm" element={<TradeConfirm />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/risk-engine" element={<RiskEngine />} />
          <Route path="/slide-doctrine" element={<SlideDoctrine />} />

          {/* Analytics */}
          <Route path="/backtesting" element={<Backtesting />} />
          <Route path="/monte-carlo" element={<MonteCarlo />} />
          <Route path="/correlation" element={<Correlation />} />

          {/* Neural AI */}
          <Route path="/neural-analysis" element={<NeuralAnalysis />} />
          <Route path="/ml-predictions" element={<MLPredictions />} />
          <Route path="/regime-detect" element={<RegimeDetect />} />
          <Route path="/trading-brain" element={<TradingBrain />} />
          <Route path="/algo-bot" element={<AlgoBot />} />
          <Route path="/unified-brain" element={<UnifiedBrain />} />
          <Route path="/ml-training" element={<MLTraining />} />
          <Route path="/market-microstructure" element={<MarketMicrostructure />} />

          {/* Prop Firm */}
          <Route path="/tpt-dashboard" element={<TPTDashboard />} />
          <Route path="/futures-brain" element={<FuturesBrain />} />

          {/* Research */}
          <Route path="/13f-holdings" element={<Holdings13F />} />
          <Route path="/sec-filings" element={<SECFilings />} />
          <Route path="/dark-pool" element={<DarkPool />} />
          <Route path="/earnings" element={<Earnings />} />
          <Route path="/news" element={<News />} />

          {/* Portfolio */}
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/pairs-trading" element={<PairsTrading />} />
          <Route path="/reports" element={<Reports />} />

          {/* System */}
          <Route path="/api-connector" element={<APIConnector />} />
          <Route path="/settings" element={<Settings />} />

          {/* Legacy routes */}
          <Route path="/signals" element={<Signals />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </Layout>
      <Toaster />
      <CommandPalette isOpen={commandPalette.isOpen} onClose={commandPalette.close} />
      <QuickTrade
        isOpen={quickTrade.isOpen}
        onClose={quickTrade.close}
        defaultSymbol={quickTrade.defaultSymbol}
        defaultSide={quickTrade.defaultSide}
      />
    </>
  )
}

export default function App() {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        console.error('Top-level error boundary caught:', error, errorInfo)
      }}
    >
      <BrowserRouter>
        <NotificationProvider>
          <AppContent />
        </NotificationProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
