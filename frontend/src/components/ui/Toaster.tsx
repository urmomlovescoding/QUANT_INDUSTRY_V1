/**
 * Toaster Component
 * Re-exports the ToastProvider for app-level usage
 */

export { ToastProvider, useToast, useToastSafe } from './Toast'

// Legacy alias for Toaster - just use ToastProvider
export function Toaster() {
  // The ToastProvider already renders the toast container
  // This component is kept for backwards compatibility but does nothing
  return null
}
