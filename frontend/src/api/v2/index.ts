/**
 * API V2 Module
 * 
 * Type-safe API client for QUANT INDUSTRY V1
 * 
 * @example
 * ```ts
 * import { apiV2 } from '@/api/v2';
 * 
 * // Fetch market data
 * const { data, error, ok } = await apiV2.market.getQuote('SPY');
 * 
 * // Submit an order
 * const result = await apiV2.orders.submit({
 *   symbol: 'AAPL',
 *   side: 'buy',
 *   quantity: 100,
 *   order_type: 'limit',
 *   limit_price: 150.00
 * });
 * 
 * // Fetch microstructure data
 * const orderBook = await apiV2.microstructure.getOrderBook('AAPL');
 * 
 * // Get arbitrage opportunities
 * const arb = await apiV2.arbitrage.getOpportunities();
 * ```
 * 
 * @module api/v2
 */

// Export the unified client
export { apiV2, default } from './client';

// Export individual API modules for tree-shaking
export {
  healthApi,
  marketApi,
  signalsApi,
  ordersApi,
  positionsApi,
  portfolioApi,
  riskApi,
  brainApi,
  brainLegacyApi,
  optionsApi,
  optionsFlowApi,
  backtestApi,
  researchApi,
  settingsApi,
  microstructureApi,
  arbitrageApi,
  newsEventsApi,
} from './client';

// Re-export all types
export * from './types';
