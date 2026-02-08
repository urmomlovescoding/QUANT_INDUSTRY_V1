import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15000,
      refetchInterval: 15000,
      refetchOnWindowFocus: true,
      retry: 2,
    },
  },
})

try {
  const root = ReactDOM.createRoot(document.getElementById('root')!)

  root.render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  )
} catch (error) {
  console.error('❌ Failed to render:', error)
  document.body.innerHTML = `<pre style="color:red;padding:20px;">Error: ${error}</pre>`
}
