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
    <div className="flex h-screen overflow-hidden bg-background-primary">
      {/* Ambient gradient overlay */}
      <div 
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(245, 158, 11, 0.04), transparent),
            radial-gradient(ellipse 60% 40% at 100% 100%, rgba(16, 185, 129, 0.03), transparent),
            radial-gradient(ellipse 40% 30% at 0% 80%, rgba(59, 130, 246, 0.02), transparent)
          `
        }}
      />

      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Header */}
        <Header />

        {/* Main content with error boundary */}
        <main className="flex-1 overflow-auto">
          <div className="p-5 animate-fade-in">
            <ErrorBoundary
              fallback={
                <div className="flex flex-col items-center justify-center h-full min-h-[60vh]">
                  <div className="card p-8 text-center max-w-md">
                    <div className="w-16 h-16 rounded-2xl bg-bearish/10 flex items-center justify-center mx-auto mb-4">
                      <svg className="w-8 h-8 text-bearish" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground-primary mb-2">Something went wrong</h3>
                    <p className="text-foreground-muted text-sm mb-6">An unexpected error occurred. Please try again.</p>
                    <button
                      onClick={() => window.location.reload()}
                      className="btn-primary"
                    >
                      Reload Page
                    </button>
                  </div>
                </div>
              }
            >
              {children}
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}

// Loading layout for suspense fallback
export function LoadingLayout() {
  return (
    <div className="flex h-screen bg-background-primary items-center justify-center">
      {/* Ambient gradient */}
      <div 
        className="fixed inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(245, 158, 11, 0.04), transparent),
            radial-gradient(ellipse 60% 40% at 100% 100%, rgba(16, 185, 129, 0.03), transparent)
          `
        }}
      />
      <div className="flex flex-col items-center gap-6 animate-fade-in">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-secondary to-accent-primary flex items-center justify-center shadow-glow-accent">
            <svg className="w-8 h-8 text-black animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <Spinner size="lg" className="absolute -inset-4 text-accent-primary/30" />
        </div>
        <div className="text-center">
          <p className="text-foreground-primary font-medium mb-1">Loading application...</p>
          <p className="text-foreground-muted text-sm">Initializing trading systems</p>
        </div>
      </div>
    </div>
  )
}
