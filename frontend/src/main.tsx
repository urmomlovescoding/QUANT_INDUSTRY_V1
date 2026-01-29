import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

console.log('🚀 QUANT INDUSTRY starting...')

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
  console.log('📦 Creating root...')
  const root = ReactDOM.createRoot(document.getElementById('root')!)
  
  console.log('🎨 Rendering app...')
  root.render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  )
  console.log('✅ Render called successfully')
} catch (error) {
  console.error('❌ Failed to render:', error)
  document.body.innerHTML = `<pre style="color:red;padding:20px;">Error: ${error}</pre>`
}
