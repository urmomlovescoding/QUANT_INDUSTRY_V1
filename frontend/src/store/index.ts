/**
 * Global State Management with Zustand
 * 
 * Migrated to use apiV2 client for type-safe API calls.
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type {
  BrainStatus,
  FeedbackStatus,
  Signal,
  Position,
  Portfolio,
  RiskMetrics,
  MarketStatus,
  MarketTicker,
  Quote,
  SafetyStatus,
} from '@/api'

// V2 API Client - Domain-based structure
import { apiV2 } from '@/api/v2'

// OLD API imports (kept as fallback reference)
// import {
//   brainApi,
//   feedbackApi,
//   signalsApi,
//   portfolioApi,
//   riskApi,
//   marketApi,
// } from '@/api'

// ==================== TYPES ====================

interface AppState {
  // UI State
  sidebarCollapsed: boolean
  commandPaletteOpen: boolean
  quickTradeOpen: boolean
  quickTradeSymbol: string
  quickTradeSide: 'BUY' | 'SELL'
  selectedSymbol: string | null
  activeView: string

  // Market State
  marketStatus: MarketStatus | null
  tickers: MarketTicker[]
  quotes: Record<string, Quote>

  // Trading State
  signals: Signal[]
  positions: Position[]
  portfolio: Portfolio | null

  // Brain State
  brainStatus: BrainStatus | null
  feedbackStatus: FeedbackStatus | null

  // Risk State
  riskMetrics: RiskMetrics | null
  safetyStatus: SafetyStatus | null

  // Loading States
  isLoading: Record<string, boolean>
  errors: Record<string, string | null>

  // Last Update Timestamps
  lastUpdated: Record<string, number>
}

interface AppActions {
  // UI Actions
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  openCommandPalette: () => void
  closeCommandPalette: () => void
  openQuickTrade: (symbol?: string, side?: 'BUY' | 'SELL') => void
  closeQuickTrade: () => void
  setSelectedSymbol: (symbol: string | null) => void
  setActiveView: (view: string) => void

  // Data Actions
  setMarketStatus: (status: MarketStatus) => void
  setTickers: (tickers: MarketTicker[]) => void
  updateTicker: (ticker: MarketTicker) => void
  setQuote: (symbol: string, quote: Quote) => void
  setSignals: (signals: Signal[]) => void
  addSignal: (signal: Signal) => void
  updateSignal: (id: string, updates: Partial<Signal>) => void
  removeSignal: (id: string) => void
  setPositions: (positions: Position[]) => void
  setPortfolio: (portfolio: Portfolio) => void
  setBrainStatus: (status: BrainStatus) => void
  setFeedbackStatus: (status: FeedbackStatus) => void
  setRiskMetrics: (metrics: RiskMetrics) => void
  setSafetyStatus: (status: SafetyStatus) => void

  // Loading/Error Actions
  setLoading: (key: string, loading: boolean) => void
  setError: (key: string, error: string | null) => void
  clearErrors: () => void

  // Fetch Actions
  fetchMarketStatus: () => Promise<void>
  fetchTickers: () => Promise<void>
  fetchSignals: () => Promise<void>
  fetchPositions: () => Promise<void>
  fetchPortfolio: () => Promise<void>
  fetchBrainStatus: () => Promise<void>
  fetchFeedbackStatus: () => Promise<void>
  fetchRiskMetrics: () => Promise<void>
  fetchAll: () => Promise<void>

  // Utility
  reset: () => void
}

type AppStore = AppState & AppActions

// ==================== INITIAL STATE ====================

const initialState: AppState = {
  // UI
  sidebarCollapsed: false,
  commandPaletteOpen: false,
  quickTradeOpen: false,
  quickTradeSymbol: '',
  quickTradeSide: 'BUY',
  selectedSymbol: null,
  activeView: 'dashboard',

  // Market
  marketStatus: null,
  tickers: [],
  quotes: {},

  // Trading
  signals: [],
  positions: [],
  portfolio: null,

  // Brain
  brainStatus: null,
  feedbackStatus: null,

  // Risk
  riskMetrics: null,
  safetyStatus: null,

  // Meta
  isLoading: {},
  errors: {},
  lastUpdated: {},
}

// ==================== STORE ====================

export const useAppStore = create<AppStore>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        // UI Actions
        toggleSidebar: () =>
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
        setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
        openCommandPalette: () => set({ commandPaletteOpen: true }),
        closeCommandPalette: () => set({ commandPaletteOpen: false }),
        openQuickTrade: (symbol = '', side = 'BUY') =>
          set({
            quickTradeOpen: true,
            quickTradeSymbol: symbol,
            quickTradeSide: side,
          }),
        closeQuickTrade: () => set({ quickTradeOpen: false }),
        setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
        setActiveView: (view) => set({ activeView: view }),

        // Data Actions
        setMarketStatus: (status) =>
          set({
            marketStatus: status,
            lastUpdated: { ...get().lastUpdated, marketStatus: Date.now() },
          }),
        setTickers: (tickers) =>
          set({
            tickers,
            lastUpdated: { ...get().lastUpdated, tickers: Date.now() },
          }),
        updateTicker: (ticker) =>
          set((state) => ({
            tickers: state.tickers.map((t) =>
              t.symbol === ticker.symbol ? ticker : t
            ),
          })),
        setQuote: (symbol, quote) =>
          set((state) => ({
            quotes: { ...state.quotes, [symbol]: quote },
          })),
        setSignals: (signals) =>
          set({
            signals,
            lastUpdated: { ...get().lastUpdated, signals: Date.now() },
          }),
        addSignal: (signal) =>
          set((state) => ({
            signals: [signal, ...state.signals],
          })),
        updateSignal: (id, updates) =>
          set((state) => ({
            signals: state.signals.map((s) =>
              s.id === id ? { ...s, ...updates } : s
            ),
          })),
        removeSignal: (id) =>
          set((state) => ({
            signals: state.signals.filter((s) => s.id !== id),
          })),
        setPositions: (positions) =>
          set({
            positions,
            lastUpdated: { ...get().lastUpdated, positions: Date.now() },
          }),
        setPortfolio: (portfolio) =>
          set({
            portfolio,
            lastUpdated: { ...get().lastUpdated, portfolio: Date.now() },
          }),
        setBrainStatus: (status) =>
          set({
            brainStatus: status,
            lastUpdated: { ...get().lastUpdated, brainStatus: Date.now() },
          }),
        setFeedbackStatus: (status) =>
          set({
            feedbackStatus: status,
            lastUpdated: { ...get().lastUpdated, feedbackStatus: Date.now() },
          }),
        setRiskMetrics: (metrics) =>
          set({
            riskMetrics: metrics,
            lastUpdated: { ...get().lastUpdated, riskMetrics: Date.now() },
          }),
        setSafetyStatus: (status) =>
          set({
            safetyStatus: status,
            lastUpdated: { ...get().lastUpdated, safetyStatus: Date.now() },
          }),

        // Loading/Error Actions
        setLoading: (key, loading) =>
          set((state) => ({
            isLoading: { ...state.isLoading, [key]: loading },
          })),
        setError: (key, error) =>
          set((state) => ({
            errors: { ...state.errors, [key]: error },
          })),
        clearErrors: () => set({ errors: {} }),

        // Fetch Actions
        // ==================== FETCH ACTIONS (using apiV2) ====================
        
        fetchMarketStatus: async () => {
          const { setLoading, setError, setMarketStatus } = get()
          setLoading('marketStatus', true)
          try {
            // V2: apiV2.market.getStatus() instead of marketApi.getMarketStatus()
            const response = await apiV2.market.getStatus()
            if (response.ok && response.data) {
              setMarketStatus(response.data)
              setError('marketStatus', null)
            } else {
              setError('marketStatus', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('marketStatus', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('marketStatus', false)
        },

        fetchTickers: async () => {
          const { setLoading, setError, setTickers } = get()
          setLoading('tickers', true)
          try {
            // V2: apiV2.market.getTickers() instead of marketApi.getTickers()
            const response = await apiV2.market.getTickers()
            if (response.ok && response.data) {
              setTickers(response.data as MarketTicker[])
              setError('tickers', null)
            } else {
              setError('tickers', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('tickers', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('tickers', false)
        },

        fetchSignals: async () => {
          const { setLoading, setError, setSignals } = get()
          setLoading('signals', true)
          try {
            // V2: apiV2.signals.getActive() instead of signalsApi.getActive()
            const response = await apiV2.signals.getActive()
            if (response.ok && response.data) {
              setSignals(response.data)
              setError('signals', null)
            } else {
              setError('signals', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('signals', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('signals', false)
        },

        fetchPositions: async () => {
          const { setLoading, setError, setPositions } = get()
          setLoading('positions', true)
          try {
            // V2: apiV2.positions.getAll() instead of portfolioApi.getPositions()
            const response = await apiV2.positions.getAll()
            if (response.ok && response.data) {
              setPositions(response.data)
              setError('positions', null)
            } else {
              setError('positions', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('positions', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('positions', false)
        },

        fetchPortfolio: async () => {
          const { setLoading, setError, setPortfolio } = get()
          setLoading('portfolio', true)
          try {
            // V2: apiV2.portfolio.get() instead of portfolioApi.getPortfolio()
            const response = await apiV2.portfolio.get()
            if (response.ok && response.data) {
              setPortfolio(response.data)
              setError('portfolio', null)
            } else {
              setError('portfolio', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('portfolio', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('portfolio', false)
        },

        fetchBrainStatus: async () => {
          const { setLoading, setError, setBrainStatus } = get()
          setLoading('brainStatus', true)
          try {
            // V2: apiV2.brain.getStatus() instead of brainApi.getStatus()
            const response = await apiV2.brain.getStatus()
            if (response.ok && response.data) {
              setBrainStatus(response.data)
              setError('brainStatus', null)
            } else {
              setError('brainStatus', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('brainStatus', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('brainStatus', false)
        },

        fetchFeedbackStatus: async () => {
          const { setLoading, setError, setFeedbackStatus } = get()
          setLoading('feedbackStatus', true)
          try {
            // V2: apiV2.brain.getFeedbackStatus() instead of feedbackApi.getStatus()
            const response = await apiV2.brain.getFeedbackStatus()
            if (response.ok && response.data) {
              setFeedbackStatus(response.data)
              setError('feedbackStatus', null)
            } else {
              setError('feedbackStatus', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('feedbackStatus', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('feedbackStatus', false)
        },

        fetchRiskMetrics: async () => {
          const { setLoading, setError, setRiskMetrics } = get()
          setLoading('riskMetrics', true)
          try {
            // V2: apiV2.risk.getMetrics() instead of riskApi.getMetrics()
            const response = await apiV2.risk.getMetrics()
            if (response.ok && response.data) {
              setRiskMetrics(response.data)
              setError('riskMetrics', null)
            } else {
              setError('riskMetrics', response.error?.message || 'Failed to fetch')
            }
          } catch (e) {
            setError('riskMetrics', e instanceof Error ? e.message : 'Unknown error')
          }
          setLoading('riskMetrics', false)
        },

        fetchAll: async () => {
          const actions = get()
          await Promise.allSettled([
            actions.fetchMarketStatus(),
            actions.fetchTickers(),
            actions.fetchSignals(),
            actions.fetchPositions(),
            actions.fetchPortfolio(),
            actions.fetchBrainStatus(),
            actions.fetchFeedbackStatus(),
            actions.fetchRiskMetrics(),
          ])
        },

        reset: () => set(initialState),
      }),
      {
        name: 'quant-industry-store',
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
          selectedSymbol: state.selectedSymbol,
          activeView: state.activeView,
        }),
      }
    ),
    { name: 'AppStore' }
  )
)

// ==================== SELECTORS ====================

export const selectUI = (state: AppStore) => ({
  sidebarCollapsed: state.sidebarCollapsed,
  commandPaletteOpen: state.commandPaletteOpen,
  quickTradeOpen: state.quickTradeOpen,
  quickTradeSymbol: state.quickTradeSymbol,
  quickTradeSide: state.quickTradeSide,
  selectedSymbol: state.selectedSymbol,
  activeView: state.activeView,
})

export const selectMarket = (state: AppStore) => ({
  marketStatus: state.marketStatus,
  tickers: state.tickers,
  quotes: state.quotes,
})

export const selectTrading = (state: AppStore) => ({
  signals: state.signals,
  positions: state.positions,
  portfolio: state.portfolio,
})

export const selectBrain = (state: AppStore) => ({
  brainStatus: state.brainStatus,
  feedbackStatus: state.feedbackStatus,
})

export const selectRisk = (state: AppStore) => ({
  riskMetrics: state.riskMetrics,
  safetyStatus: state.safetyStatus,
})

export const selectLoading = (key: string) => (state: AppStore) =>
  state.isLoading[key] ?? false

export const selectError = (key: string) => (state: AppStore) =>
  state.errors[key] ?? null

export const selectLastUpdated = (key: string) => (state: AppStore) =>
  state.lastUpdated[key] ?? 0

// ==================== HOOKS ====================

export function useMarketStatus() {
  const marketStatus = useAppStore((s) => s.marketStatus)
  const isLoading = useAppStore(selectLoading('marketStatus'))
  const error = useAppStore(selectError('marketStatus'))
  const fetch = useAppStore((s) => s.fetchMarketStatus)
  return { marketStatus, isLoading, error, fetch }
}

export function useTickers() {
  const tickers = useAppStore((s) => s.tickers)
  const isLoading = useAppStore(selectLoading('tickers'))
  const error = useAppStore(selectError('tickers'))
  const fetch = useAppStore((s) => s.fetchTickers)
  return { tickers, isLoading, error, fetch }
}

export function useSignals() {
  const signals = useAppStore((s) => s.signals)
  const isLoading = useAppStore(selectLoading('signals'))
  const error = useAppStore(selectError('signals'))
  const fetch = useAppStore((s) => s.fetchSignals)
  return { signals, isLoading, error, fetch }
}

export function usePositions() {
  const positions = useAppStore((s) => s.positions)
  const isLoading = useAppStore(selectLoading('positions'))
  const error = useAppStore(selectError('positions'))
  const fetch = useAppStore((s) => s.fetchPositions)
  return { positions, isLoading, error, fetch }
}

export function usePortfolio() {
  const portfolio = useAppStore((s) => s.portfolio)
  const isLoading = useAppStore(selectLoading('portfolio'))
  const error = useAppStore(selectError('portfolio'))
  const fetch = useAppStore((s) => s.fetchPortfolio)
  return { portfolio, isLoading, error, fetch }
}

export function useBrainStatus() {
  const brainStatus = useAppStore((s) => s.brainStatus)
  const isLoading = useAppStore(selectLoading('brainStatus'))
  const error = useAppStore(selectError('brainStatus'))
  const fetch = useAppStore((s) => s.fetchBrainStatus)
  return { brainStatus, isLoading, error, fetch }
}

export function useFeedbackStatus() {
  const feedbackStatus = useAppStore((s) => s.feedbackStatus)
  const isLoading = useAppStore(selectLoading('feedbackStatus'))
  const error = useAppStore(selectError('feedbackStatus'))
  const fetch = useAppStore((s) => s.fetchFeedbackStatus)
  return { feedbackStatus, isLoading, error, fetch }
}

export function useRiskMetrics() {
  const riskMetrics = useAppStore((s) => s.riskMetrics)
  const isLoading = useAppStore(selectLoading('riskMetrics'))
  const error = useAppStore(selectError('riskMetrics'))
  const fetch = useAppStore((s) => s.fetchRiskMetrics)
  return { riskMetrics, isLoading, error, fetch }
}

export function useQuickTrade() {
  const isOpen = useAppStore((s) => s.quickTradeOpen)
  const symbol = useAppStore((s) => s.quickTradeSymbol)
  const side = useAppStore((s) => s.quickTradeSide)
  const open = useAppStore((s) => s.openQuickTrade)
  const close = useAppStore((s) => s.closeQuickTrade)
  return { isOpen, symbol, side, open, close }
}

export function useCommandPalette() {
  const isOpen = useAppStore((s) => s.commandPaletteOpen)
  const open = useAppStore((s) => s.openCommandPalette)
  const close = useAppStore((s) => s.closeCommandPalette)
  return { isOpen, open, close }
}
