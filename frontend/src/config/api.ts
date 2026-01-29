/**
 * API Configuration
 * Centralized configuration for API endpoints
 */

// In production, use relative paths (same origin)
// In development, use the backend URL directly
const isDev = import.meta.env.DEV;

export const API_BASE_URL = isDev ? 'http://localhost:8000' : '';

export const API_ENDPOINTS = {
  // ML Brain
  BRAIN: `${API_BASE_URL}/brain`,
  BRAIN_STATUS: `${API_BASE_URL}/brain/status`,
  BRAIN_SIGNALS: `${API_BASE_URL}/brain/signal`,
  BRAIN_BOTS: `${API_BASE_URL}/brain/bots`,
  
  // Options Flow
  OPTIONS_FLOW: `${API_BASE_URL}/api/v1/options-flow`,
  
  // Microstructure
  MICROSTRUCTURE: `${API_BASE_URL}/api/v1/microstructure`,
  
  // Cross-Exchange Arbitrage
  ARBITRAGE: `${API_BASE_URL}/api/v1/arbitrage`,
  
  // News & Events
  NEWS_EVENTS: `${API_BASE_URL}/api/v1/news-events`,
  
  // Core API
  MARKET: `${API_BASE_URL}/api/market`,
  HEALTH: `${API_BASE_URL}/api/health`,
} as const;

export default API_ENDPOINTS;
