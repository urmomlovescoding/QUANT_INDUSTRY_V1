/**
 * API V2 Types
 * Re-exports all types from the generated types file
 * 
 * @module api/v2/types
 */

// Re-export all types from the generated file
export * from '../../types/api-generated';

// Re-export the base API types from the main client
export type { ApiError, ApiResponse } from '../client';
