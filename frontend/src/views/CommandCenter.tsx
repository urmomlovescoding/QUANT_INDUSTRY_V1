/**
 * Command Center View
 * Trading command center with multi-panel layout, signal feed, and real-time metrics.
 * The central hub for active trading sessions.
 */

import { PanelLayout } from '@/components/PanelLayout'

export function CommandCenter() {
  return (
    <div className="h-[calc(100vh-6.5rem)] -m-4">
      <PanelLayout />
    </div>
  )
}
