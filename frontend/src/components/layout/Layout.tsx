import { useEffect } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useAppStore } from '@/store'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Spinner } from '@/components/ui/Loading'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const fetchAll = useAppStore((s) => s.fetchAll)

  // Initial data fetch on mount
  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  return (
    <div className="flex h-screen bg-background-primary overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header />

        {/* Main content with error boundary */}
        <main className="flex-1 overflow-auto p-4">
          <ErrorBoundary
            fallback={
              <div className="flex flex-col items-center justify-center h-full">
                <p className="text-error mb-4">Something went wrong</p>
                <button
                  onClick={() => window.location.reload()}
                  className="btn-primary"
                >
                  Reload Page
                </button>
              </div>
            }
          >
            {children}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

// Loading layout for suspense fallback
export function LoadingLayout() {
  return (
    <div className="flex h-screen bg-background-primary items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p className="text-foreground-muted">Loading application...</p>
      </div>
    </div>
  )
}
