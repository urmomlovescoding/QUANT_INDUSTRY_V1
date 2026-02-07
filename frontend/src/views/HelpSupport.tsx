/**
 * Help & Support View
 * ====================
 * Troubleshooting FAQ, email support form, and platform information.
 */

import { useState } from 'react'
import {
  HelpCircle,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Mail,
  Send,
  Info,
  Keyboard,
  Monitor,
  Server,
  Wifi,
  BarChart3,
  Brain,
  LineChart,
  Lock,
  Timer,
  Link,
  Cpu,
  Target,
  Globe,
  FileText,
  ExternalLink,
  Upload,
  Zap,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// -------------------------------------------------------------------
// Accordion primitive (same pattern as LearningCenter)
// -------------------------------------------------------------------

interface FaqItem {
  id: string
  icon: React.ComponentType<{ className?: string }>
  question: string
  answer: React.ReactNode
}

function FaqAccordionItem({
  item,
  isOpen,
  onToggle,
}: {
  item: FaqItem
  isOpen: boolean
  onToggle: () => void
}) {
  const Icon = item.icon

  return (
    <div className="border border-border/60 rounded-lg overflow-hidden transition-colors hover:border-border">
      <button
        onClick={onToggle}
        className={cn(
          'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
          isOpen
            ? 'bg-accent-primary/5 border-b border-border/40'
            : 'hover:bg-background-hover/40'
        )}
      >
        <div
          className={cn(
            'p-1.5 rounded-md flex-shrink-0',
            isOpen ? 'bg-accent-primary/15' : 'bg-background-tertiary'
          )}
        >
          <Icon
            className={cn(
              'w-4 h-4',
              isOpen ? 'text-accent-primary' : 'text-foreground-muted'
            )}
          />
        </div>
        <span
          className={cn(
            'flex-1 text-sm font-medium',
            isOpen ? 'text-accent-primary' : 'text-foreground-primary'
          )}
        >
          {item.question}
        </span>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-foreground-muted flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-foreground-muted flex-shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 py-4 text-sm text-foreground-secondary leading-relaxed space-y-2">
          {item.answer}
        </div>
      )}
    </div>
  )
}

function FaqAccordionGroup({ items }: { items: FaqItem[] }) {
  const [openIds, setOpenIds] = useState<string[]>([])

  const toggle = (id: string) => {
    setOpenIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [id]
    )
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <FaqAccordionItem
          key={item.id}
          item={item}
          isOpen={openIds.includes(item.id)}
          onToggle={() => toggle(item.id)}
        />
      ))}
    </div>
  )
}

// -------------------------------------------------------------------
// FAQ items
// -------------------------------------------------------------------

const faqItems: FaqItem[] = [
  {
    id: 'faq-connection-refused',
    icon: Wifi,
    question: 'App shows "connection refused"',
    answer: (
      <>
        <p>
          This means the frontend cannot reach the backend API server. Ensure the backend is
          running on port 8000:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>
            Open a terminal and navigate to the <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">backend</code> directory.
          </li>
          <li>
            Activate the virtual environment:{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">
              venv\Scripts\activate
            </code>
          </li>
          <li>
            Start the server:{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">
              uvicorn main:app --host 0.0.0.0 --port 8000 --reload
            </code>
          </li>
          <li>
            Verify by visiting{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">
              http://localhost:8000/docs
            </code>{' '}
            in your browser.
          </li>
        </ol>
        <p>
          If using the desktop app, try restarting via <strong>START.bat</strong> which launches
          both backend and frontend together.
        </p>
      </>
    ),
  },
  {
    id: 'faq-no-data',
    icon: BarChart3,
    question: 'Market data shows $0 or no data',
    answer: (
      <>
        <p>This typically indicates missing or invalid API keys. To fix:</p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>
            Go to <strong>Settings &gt; Data Sources</strong> and verify your Alpaca Markets API
            key is entered and showing "Connected" status.
          </li>
          <li>
            Check if the market is currently open. US equity markets operate 9:30 AM - 4:00 PM ET
            on weekdays. Outside of market hours, real-time data will not update (historical data
            should still be available).
          </li>
          <li>
            Use the <strong>Test Connection</strong> button to verify each provider.
          </li>
          <li>
            If using Yahoo Finance as a fallback, note that it may have rate limits. Wait a minute
            and try again.
          </li>
        </ol>
      </>
    ),
  },
  {
    id: 'faq-not-trained',
    icon: Brain,
    question: 'ML Brain shows "not trained"',
    answer: (
      <>
        <p>
          The ML Brain needs an initial training session before it can generate signals:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>
            Navigate to <strong>Neural AI &gt; ML Training</strong>.
          </li>
          <li>Select a prop firm ruleset or use the default configuration.</li>
          <li>
            Click <strong>Start Training</strong>. Initial training takes 2-5 minutes depending on
            the amount of available historical data.
          </li>
          <li>
            Once complete, the brain status will change to "Active" and signals will begin
            appearing on the Dashboard.
          </li>
        </ol>
        <p>
          If training fails, check that you have sufficient historical data (minimum 50 bars per
          symbol) and that the backend is running with adequate memory.
        </p>
      </>
    ),
  },
  {
    id: 'faq-blank-charts',
    icon: LineChart,
    question: 'Charts are blank',
    answer: (
      <>
        <p>Blank charts usually result from one of these issues:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>No ticker entered</strong> — Make sure you have entered a valid ticker symbol
            in the chart view.
          </li>
          <li>
            <strong>API connection issue</strong> — Check the API Connector page to verify your
            data source is connected.
          </li>
          <li>
            <strong>Invalid ticker</strong> — Verify the ticker symbol is correct and actively
            traded on a US exchange.
          </li>
          <li>
            <strong>Browser cache</strong> — Try a hard refresh (Ctrl+Shift+R) to clear cached
            state.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'faq-login',
    icon: Lock,
    question: 'Login not working',
    answer: (
      <>
        <p>If you cannot log in:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Default credentials</strong> — The default username is{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">admin</code>{' '}
            and the default password is{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">admin</code>.
          </li>
          <li>
            <strong>Password reset</strong> — If you changed the password and forgot it, you can
            reset by deleting the auth database and restarting the backend.
          </li>
          <li>
            <strong>Backend not running</strong> — The login endpoint requires the backend to be
            active on port 8000. Check the terminal for errors.
          </li>
          <li>
            <strong>CORS issues</strong> — If running in a browser, ensure you are accessing the
            frontend via <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">http://localhost:3000</code>,
            not a different hostname.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'faq-backtest-no-results',
    icon: Timer,
    question: 'Backtest returns no results',
    answer: (
      <>
        <p>Backtests require sufficient data to produce results:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Minimum data</strong> — You need at least 50 bars of historical data for the
            selected ticker and timeframe.
          </li>
          <li>
            <strong>Check ticker</strong> — Ensure the ticker symbol is correct and has data for
            the selected date range.
          </li>
          <li>
            <strong>Strategy compatibility</strong> — Some strategies require specific indicators
            that need a minimum lookback period (e.g., 200-day SMA needs 200 bars).
          </li>
          <li>
            <strong>Date range</strong> — Make sure the start date is before the end date and that
            the range covers trading days.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'faq-options-empty',
    icon: Target,
    question: 'Options chain is empty',
    answer: (
      <>
        <p>
          The options chain requires a specialized data provider beyond the default equity feed:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>API key required</strong> — You need a Tradier or Polygon.io API key
            configured in Settings &gt; Data Sources to access options data.
          </li>
          <li>
            <strong>Ticker support</strong> — Not all tickers have listed options. Make sure you
            are looking at an optionable equity.
          </li>
          <li>
            <strong>Expiration selection</strong> — You may need to select a specific expiration
            date for the chain to populate.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'faq-websocket',
    icon: Link,
    question: 'WebSocket disconnected',
    answer: (
      <>
        <p>
          WebSocket connections can drop due to network issues or backend restarts:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Refresh the browser</strong> — Press F5 or Ctrl+R. The WebSocket will
            automatically reconnect.
          </li>
          <li>
            <strong>Check backend logs</strong> — Look at the terminal running uvicorn for any
            error messages.
          </li>
          <li>
            <strong>Network issues</strong> — If running on a remote server, check your network
            connection and ensure the WebSocket port is not blocked by a firewall.
          </li>
          <li>
            <strong>Too many connections</strong> — Close duplicate browser tabs to reduce the
            number of simultaneous WebSocket connections.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'faq-gpu',
    icon: Cpu,
    question: 'GPU not detected',
    answer: (
      <>
        <p>
          GPU acceleration is optional but significantly speeds up neural network training:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>CUDA toolkit</strong> — Install the NVIDIA CUDA toolkit (version 11.8 or
            later) from the NVIDIA website.
          </li>
          <li>
            <strong>PyTorch CUDA</strong> — Ensure PyTorch was installed with CUDA support:{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">
              pip install torch --index-url https://download.pytorch.org/whl/cu118
            </code>
          </li>
          <li>
            <strong>Verify</strong> — Run{' '}
            <code className="text-accent-primary bg-background-tertiary px-1.5 py-0.5 rounded text-xs">
              python -c "import torch; print(torch.cuda.is_available())"
            </code>{' '}
            — should print True.
          </li>
          <li>
            <strong>Driver version</strong> — Make sure your NVIDIA driver version is compatible
            with the installed CUDA version.
          </li>
        </ul>
        <p>
          The platform will fall back to CPU training if GPU is not available. CPU training is
          slower but fully functional.
        </p>
      </>
    ),
  },
  {
    id: 'faq-all-hold',
    icon: AlertTriangle,
    question: 'Signals are all HOLD',
    answer: (
      <>
        <p>
          If every signal shows HOLD, it usually means one of the following:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Insufficient training data</strong> — The brain may need more historical data
            or additional training iterations. Go to ML Training and run more training epochs.
          </li>
          <li>
            <strong>Regime uncertainty</strong> — If the regime detector shows low confidence
            across all regimes, the brain defaults to HOLD as a risk-management measure.
          </li>
          <li>
            <strong>Risk limits hit</strong> — Check if daily loss limits or max drawdown
            constraints have been triggered, which causes the system to halt signal generation.
          </li>
          <li>
            <strong>Market closed</strong> — During non-market hours, signals are not generated
            because there is no live data to process.
          </li>
          <li>
            <strong>Confidence threshold</strong> — The system only emits BUY/SELL signals when
            confidence exceeds a configurable threshold (default 60%). Lower the threshold in
            settings if needed.
          </li>
        </ul>
      </>
    ),
  },
]

// -------------------------------------------------------------------
// Support form
// -------------------------------------------------------------------

const SUBJECT_OPTIONS = [
  'Bug Report',
  'Feature Request',
  'Account Issue',
  'Data Issue',
  'Other',
]

function SupportForm() {
  const [subject, setSubject] = useState(SUBJECT_OPTIONS[0])
  const [description, setDescription] = useState('')
  const [screenshotName, setScreenshotName] = useState<string | null>(null)

  const systemInfo = {
    version: 'QUANT INDUSTRY v10.0',
    browser: typeof navigator !== 'undefined' ? navigator.userAgent.split(' ').slice(-2).join(' ') : 'Unknown',
    dataMode: 'Live (force_live=True)',
    gpu: 'Detection requires backend query',
  }

  const handleSend = () => {
    const body = encodeURIComponent(
      `${description}\n\n---\nSystem Info:\n- Version: ${systemInfo.version}\n- Browser: ${systemInfo.browser}\n- Data Mode: ${systemInfo.dataMode}\n- GPU: ${systemInfo.gpu}${screenshotName ? `\n- Screenshot: ${screenshotName} (attached separately)` : ''}`
    )
    const subjectEncoded = encodeURIComponent(`[${subject}] Support Request`)
    window.open(`mailto:support@quantindustry.com?subject=${subjectEncoded}&body=${body}`, '_self')
  }

  return (
    <div className="space-y-5">
      {/* Subject */}
      <div>
        <label className="block text-sm font-medium text-foreground-primary mb-2">
          Subject
        </label>
        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="input w-full sm:w-64"
        >
          {SUBJECT_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-foreground-primary mb-2">
          Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          placeholder="Describe your issue or request in detail..."
          className="input w-full resize-y"
        />
      </div>

      {/* Screenshot (UI only) */}
      <div>
        <label className="block text-sm font-medium text-foreground-primary mb-2">
          Screenshot (optional)
        </label>
        <label
          className={cn(
            'flex items-center justify-center gap-2 w-full py-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors',
            screenshotName
              ? 'border-accent-primary/40 bg-accent-primary/5'
              : 'border-border hover:border-foreground-muted hover:bg-background-hover/30'
          )}
        >
          <Upload className="w-4 h-4 text-foreground-muted" />
          <span className="text-sm text-foreground-muted">
            {screenshotName || 'Click to select a screenshot'}
          </span>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) =>
              setScreenshotName(e.target.files?.[0]?.name ?? null)
            }
          />
        </label>
      </div>

      {/* System info (auto-populated) */}
      <div>
        <label className="block text-sm font-medium text-foreground-primary mb-2">
          System Info (auto-populated)
        </label>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(systemInfo).map(([key, value]) => (
            <div
              key={key}
              className="flex items-center gap-2 px-3 py-2 bg-background-tertiary rounded-lg"
            >
              <span className="text-xs text-foreground-muted capitalize">{key}:</span>
              <span className="text-xs text-foreground-secondary truncate">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Send */}
      <button onClick={handleSend} className="btn-primary flex items-center gap-2 text-sm px-5 py-2.5">
        <Send className="w-4 h-4" />
        Send via Email
      </button>
      <p className="text-xs text-foreground-muted">
        This will open your default email client addressed to support@quantindustry.com.
      </p>
    </div>
  )
}

// -------------------------------------------------------------------
// Platform info
// -------------------------------------------------------------------

const shortcuts = [
  { keys: 'Ctrl + K', description: 'Open Command Palette' },
  { keys: 'Ctrl + T', description: 'Quick Trade' },
  { keys: 'F11', description: 'Toggle Fullscreen' },
  { keys: 'Ctrl + Shift + R', description: 'Hard Refresh' },
  { keys: 'Escape', description: 'Close dialogs / modals' },
]

function PlatformInfo() {
  return (
    <div className="space-y-6">
      {/* Version & Build */}
      <div>
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">
          Version & Build
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex items-center gap-3 px-4 py-3 bg-background-tertiary rounded-lg">
            <Zap className="w-4 h-4 text-accent-primary flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-foreground-primary">QUANT INDUSTRY v10.0</div>
              <div className="text-xs text-foreground-muted">Production Release</div>
            </div>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 bg-background-tertiary rounded-lg">
            <Server className="w-4 h-4 text-accent-primary flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-foreground-primary">FastAPI Backend</div>
              <div className="text-xs text-foreground-muted">Python 3.9+ / Uvicorn</div>
            </div>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 bg-background-tertiary rounded-lg">
            <Globe className="w-4 h-4 text-accent-primary flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-foreground-primary">React 18 Frontend</div>
              <div className="text-xs text-foreground-muted">TypeScript / Vite / Tailwind CSS</div>
            </div>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 bg-background-tertiary rounded-lg">
            <Monitor className="w-4 h-4 text-accent-primary flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-foreground-primary">Electron Desktop</div>
              <div className="text-xs text-foreground-muted">Windows / Cross-platform</div>
            </div>
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts */}
      <div>
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">
          Keyboard Shortcuts
        </h3>
        <div className="border border-border rounded-lg overflow-hidden">
          {shortcuts.map((shortcut, i) => (
            <div
              key={shortcut.keys}
              className={cn(
                'flex items-center justify-between px-4 py-2.5',
                i < shortcuts.length - 1 && 'border-b border-border/50'
              )}
            >
              <span className="text-sm text-foreground-secondary">{shortcut.description}</span>
              <kbd className="px-2 py-1 bg-background-tertiary border border-border rounded text-xs font-mono text-foreground-muted">
                {shortcut.keys}
              </kbd>
            </div>
          ))}
        </div>
      </div>

      {/* System Requirements */}
      <div>
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">
          System Requirements
        </h3>
        <div className="space-y-2 text-sm text-foreground-secondary">
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>OS:</strong> Windows 10+, macOS 12+, or Linux (Ubuntu 20.04+)</span>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>Python:</strong> 3.9 or later</span>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>Node.js:</strong> 18 or later</span>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>RAM:</strong> 8 GB minimum, 16 GB recommended</span>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>GPU:</strong> Optional. NVIDIA with CUDA 11.8+ for accelerated ML training</span>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>Browser:</strong> Chrome 90+, Edge 90+, Firefox 90+, Safari 15+</span>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-primary mt-1.5 flex-shrink-0" />
            <span><strong>Disk:</strong> 2 GB free space for application + data</span>
          </div>
        </div>
      </div>

      {/* Documentation Links */}
      <div>
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">
          Documentation
        </h3>
        <div className="space-y-2">
          {[
            { label: 'API Documentation', href: 'http://localhost:8000/docs', desc: 'Interactive Swagger UI for all backend endpoints' },
            { label: 'Learning Center', href: '/learning', desc: 'In-app educational content and guides' },
          ].map((link) => (
            <a
              key={link.label}
              href={link.href}
              target={link.href.startsWith('http') ? '_blank' : undefined}
              rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
              className="flex items-center gap-3 px-4 py-3 border border-border rounded-lg hover:border-accent-primary/40 hover:bg-accent-primary/5 transition-colors group"
            >
              <FileText className="w-4 h-4 text-foreground-muted group-hover:text-accent-primary flex-shrink-0" />
              <div className="flex-1">
                <div className="text-sm font-medium text-foreground-primary group-hover:text-accent-primary">
                  {link.label}
                </div>
                <div className="text-xs text-foreground-muted">{link.desc}</div>
              </div>
              <ExternalLink className="w-3.5 h-3.5 text-foreground-muted group-hover:text-accent-primary flex-shrink-0" />
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}

// -------------------------------------------------------------------
// Tabs
// -------------------------------------------------------------------

const tabs = [
  { id: 'troubleshooting', label: 'Troubleshooting', icon: AlertTriangle },
  { id: 'contact', label: 'Email Support', icon: Mail },
  { id: 'platform', label: 'Platform Info', icon: Info },
]

// -------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------

export function HelpSupport() {
  const [activeTab, setActiveTab] = useState('troubleshooting')

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <HelpCircle className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground-primary">Help & Support</h1>
          <p className="text-sm text-foreground-muted">
            Troubleshooting, support contact, and platform information
          </p>
        </div>
      </div>

      <div className="card">
        {/* Tab bar */}
        <div className="flex border-b border-border overflow-x-auto">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap',
                activeTab === id
                  ? 'text-accent-primary border-accent-primary'
                  : 'text-foreground-secondary border-transparent hover:text-foreground-primary'
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-6">
          {activeTab === 'troubleshooting' && (
            <div>
              <h2 className="text-base font-bold text-foreground-primary mb-1">
                Frequently Asked Questions
              </h2>
              <p className="text-xs text-foreground-muted mb-4">
                Common issues and how to resolve them.
              </p>
              <FaqAccordionGroup items={faqItems} />
            </div>
          )}

          {activeTab === 'contact' && (
            <div>
              <h2 className="text-base font-bold text-foreground-primary mb-1">
                Contact Support
              </h2>
              <p className="text-xs text-foreground-muted mb-4">
                Send us a message and we will get back to you as soon as possible.
              </p>
              <SupportForm />
            </div>
          )}

          {activeTab === 'platform' && (
            <div>
              <h2 className="text-base font-bold text-foreground-primary mb-1">
                Platform Information
              </h2>
              <p className="text-xs text-foreground-muted mb-4">
                Version details, shortcuts, system requirements, and documentation links.
              </p>
              <PlatformInfo />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
