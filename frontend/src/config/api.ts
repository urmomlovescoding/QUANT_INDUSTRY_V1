/**
 * API Configuration
 * Centralized configuration for API endpoints
 */

// In production, use relative paths (same origin)
// In development, use the backend URL directly
const isDev = import.meta.env.DEV;

export const API_BASE_URL = isDev ? 'http://localhost:8000' : '';

export const API_ENDPOINTS = {
  // ML Brain — mapped to real /api/brain-v6/* endpoints
  BRAIN: `${API_BASE_URL}/api/brain-v6`,
  BRAIN_STATUS: `${API_BASE_URL}/api/brain-v6/status`,
  BRAIN_SIGNALS: `${API_BASE_URL}/api/brain-v6/signals`,
  BRAIN_BOTS: `${API_BASE_URL}/api/brain/modules`,

  // Options Flow — mapped to real /api/options/* endpoints
  OPTIONS_FLOW: `${API_BASE_URL}/api/options/flow`,

  // Microstructure — mapped to real /api/microstructure/* endpoints
  MICROSTRUCTURE: `${API_BASE_URL}/api/microstructure`,

  // Cross-Exchange Arbitrage — mapped to real /api/pairs/* endpoints
  ARBITRAGE: `${API_BASE_URL}/api/pairs`,

  // News & Events — mapped to real /api/news/* and /api/research/* endpoints
  NEWS_EVENTS: `${API_BASE_URL}/api/news`,

  // Core API
  MARKET: `${API_BASE_URL}/api/market`,
  HEALTH: `${API_BASE_URL}/api/health`,
} as const;

export default API_ENDPOINTS;
