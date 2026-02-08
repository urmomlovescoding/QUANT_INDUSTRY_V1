import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './components/ui/Toast'
import { ApiErrorToastBridge } from './components/ApiErrorToastBridge'
import { Layout } from './components/layout/Layout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { CommandPalette, useCommandPalette } from './components/CommandPalette'
import { NotificationProvider } from './components/NotificationSystem'
import { QuickTrade, useQuickTrade } from './components/QuickTrade'
import { AlertProvider, AlertManager } from './components/AlertSystem'
import { ProtectedRoute } from './components/auth'
import { useAuthStore } from './store/authStore'

// Auth views
import { Login } from './views/Login'
import { Register } from './views/Register'

// Market views
import { Dashboard } from './views/Dashboard'
import { Screener } from './views/Screener'
import { Charts } from './views/Charts'
import { CommandCenter } from './views/CommandCenter'

// Advanced Trading views
import { CrossExchange } from './views/CrossExchange'
import { OptionsFlow } from './views/OptionsFlow'
import { BrainDashboardView } from './views/BrainDashboardView'

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
import { BacktestViz } from './views/BacktestViz'
import { PnlAttribution } from './views/PnlAttribution'
import { MonteCarlo } from './views/MonteCarlo'
import { Correlation } from './views/Correlation'
import { RiskDecomposition } from './views/RiskDecomposition'
import { ScenarioAnalysis } from './views/ScenarioAnalysis'

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
import { TaxLots } from './views/TaxLots'
import { Reports } from './views/Reports'

// System views
import { APIConnector } from './views/APIConnector'
import { Settings } from './views/Settings'

// Support views
import { LearningCenter } from './views/LearningCenter'
import { HelpSupport } from './views/HelpSupport'

// Legacy views for compatibility
import { Signals } from './views/Signals'
import { Positions } from './views/Positions'
import { Performance } from './views/Performance'
import { Analytics } from './views/Analytics'

function AppContent() {
  const commandPalette = useCommandPalette()
  const quickTrade = useQuickTrade()
  const [alertManagerOpen, setAlertManagerOpen] = useState(false)
  const { isAuthenticated, setLoading } = useAuthStore()

  // Initialize auth state on mount
  useEffect(() => {
    setLoading(false)
  }, [setLoading])

  // Listen for alert manager open events (from command palette or keyboard shortcut)
  useEffect(() => {
    const handler = () => setAlertManagerOpen(true)
    window.addEventListener('open-alert-manager', handler)
    return () => window.removeEventListener('open-alert-manager', handler)
  }, [])

  // Listen for quick trade open events (from command palette)
  useEffect(() => {
    const handler = () => quickTrade.open()
    window.addEventListener('open-quick-trade', handler)
    return () => window.removeEventListener('open-quick-trade', handler)
  }, [quickTrade])

  return (
    <>
      <Routes>
        {/* Public auth routes */}
        <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Login />} />
        <Route path="/register" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Register />} />

        {/* Protected routes wrapped in Layout */}
        <Route path="/*" element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />

                {/* Markets */}
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/command-center" element={<CommandCenter />} />
                <Route path="/screener" element={<Screener />} />
                <Route path="/charts" element={<Charts />} />

                {/* Advanced Trading */}
                <Route path="/cross-exchange" element={<CrossExchange />} />
                <Route path="/options-flow" element={<OptionsFlow />} />
                <Route path="/brain-dashboard" element={<BrainDashboardView />} />

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
                <Route path="/backtest-viz" element={<BacktestViz />} />
                <Route path="/pnl-attribution" element={<PnlAttribution />} />
                <Route path="/monte-carlo" element={<MonteCarlo />} />
                <Route path="/correlation" element={<Correlation />} />
                <Route path="/risk-decomposition" element={<RiskDecomposition />} />
                <Route path="/scenario-analysis" element={<ScenarioAnalysis />} />

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
                <Route path="/tax-lots" element={<TaxLots />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/tax-lots" element={<TaxLots />} />

                {/* System */}
                <Route path="/api-connector" element={<APIConnector />} />
                <Route path="/settings" element={<Settings />} />

                {/* Support */}
                <Route path="/learning" element={<LearningCenter />} />
                <Route path="/help" element={<HelpSupport />} />

                {/* Legacy routes */}
                <Route path="/signals" element={<Signals />} />
                <Route path="/positions" element={<Positions />} />
                <Route path="/performance" element={<Performance />} />
                <Route path="/analytics" element={<Analytics />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        } />
      </Routes>
      <ApiErrorToastBridge />
      <CommandPalette isOpen={commandPalette.isOpen} onClose={commandPalette.close} />
      <QuickTrade
        isOpen={quickTrade.isOpen}
        onClose={quickTrade.close}
        defaultSymbol={quickTrade.defaultSymbol}
        defaultSide={quickTrade.defaultSide}
      />
      <AlertManager isOpen={alertManagerOpen} onClose={() => setAlertManagerOpen(false)} />
    </>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <NotificationProvider>
            <AlertProvider>
              <AppContent />
            </AlertProvider>
          </NotificationProvider>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
