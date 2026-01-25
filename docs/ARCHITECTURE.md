# QUANT INDUSTRY Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUANT INDUSTRY v10.0                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │   Desktop App   │     │   Web Browser   │     │   Mobile App    │       │
│  │   (Electron)    │     │   (localhost)   │     │   (Future)      │       │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘       │
│           │                       │                       │                 │
│           └───────────────────────┼───────────────────────┘                 │
│                                   │                                         │
│                          HTTP/WebSocket                                     │
│                                   │                                         │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                        FRONTEND (React/TypeScript)                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │Dashboard │ │ Charts   │ │ Trading  │ │Portfolio │ │ Settings │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│                          REST API / WebSocket                               │
│                                   │                                         │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                        BACKEND (FastAPI/Python)                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                     API Layer (main.py)                      │   │   │
│  │  │  • REST Endpoints  • WebSocket Handlers  • Middleware       │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                      │   │
│  │  ┌───────────────────────────┴───────────────────────────────┐    │   │
│  │  │                    Service Layer                           │    │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │    │   │
│  │  │  │  Data   │  │ Trading │  │  Risk   │  │Research │      │    │   │
│  │  │  │ Service │  │ Service │  │ Service │  │ Service │      │    │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │    │   │
│  │  └───────────────────────────────────────────────────────────┘    │   │
│  │                              │                                      │   │
│  │  ┌───────────────────────────┴───────────────────────────────┐    │   │
│  │  │                     Brain Layer (ML/AI)                    │    │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │    │   │
│  │  │  │ PropFirm    │  │Reinforcement│  │    Deep     │       │    │   │
│  │  │  │ Brain V6    │  │  Learning   │  │  Learning   │       │    │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘       │    │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │    │   │
│  │  │  │   BEAST     │  │  Evolution  │  │   Neural    │       │    │   │
│  │  │  │    ML       │  │   Engine    │  │   Engine    │       │    │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘       │    │   │
│  │  └───────────────────────────────────────────────────────────┘    │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                        Data Layer                                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │   │
│  │  │  Alpaca │  │ Tradier │  │  Yahoo  │  │Fallback │               │   │
│  │  │   API   │  │   API   │  │ Finance │  │  Data   │               │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘               │   │
│  │                              │                                      │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                            │   │
│  │  │ SQLite  │  │  Cache  │  │  Files  │                            │   │
│  │  │   DB    │  │  Layer  │  │ Storage │                            │   │
│  │  └─────────┘  └─────────┘  └─────────┘                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Frontend (React/TypeScript)

```
frontend/
├── src/
│   ├── components/          # UI Components
│   │   ├── layout/          # Header, Sidebar, Footer
│   │   ├── charts/          # TradingView charts
│   │   ├── portfolio/       # Portfolio displays
│   │   └── trading/         # Trading interfaces
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API client services
│   ├── store/               # State management
│   ├── types/               # TypeScript types
│   └── utils/               # Utility functions
├── public/                  # Static assets
└── package.json
```

**Key Technologies:**
- React 18 with TypeScript
- Vite for bundling
- TailwindCSS for styling
- TradingView Lightweight Charts
- Zustand for state management

### Backend (FastAPI/Python)

```
backend/
├── main.py                  # FastAPI application
├── services/                # Business logic
│   ├── data_service.py      # Market data
│   ├── trading_service.py   # Order execution
│   ├── risk_service.py      # Risk management
│   └── market_hours.py      # Market hours detection
├── brain/                   # ML/AI modules
│   ├── propfirm_brain_v6.py # Main trading brain
│   ├── beast_ml.py          # BEAST ML engine
│   ├── reinforcement_loop.py# RL agent
│   ├── deep_learning.py     # DL models
│   └── evolution_engine.py  # Genetic algorithms
├── config/                  # Configuration
├── middleware/              # Security middleware
├── utils/                   # Utilities
└── tests/                   # Test suite
```

**Key Technologies:**
- FastAPI with async support
- PyTorch for deep learning
- NumPy/Pandas for data processing
- SQLite for persistence
- WebSockets for real-time data

### Desktop App (Electron)

```
desktop/
├── main.js                  # Electron main process
├── preload.js               # Preload script
├── package.json
└── assets/                  # App icons and assets
```

---

## Data Flow

### Market Data Flow
```
External APIs (Alpaca/Tradier/Yahoo)
         │
         ▼
    DataService
         │
    ┌────┴────┐
    │  Cache  │ ◄── SQLite (persistence)
    └────┬────┘
         │
         ▼
    API Endpoints
         │
    ┌────┴────┐
    │WebSocket│ ◄── Real-time updates
    └────┬────┘
         │
         ▼
    Frontend Components
```

### Trading Signal Flow
```
Market Data
    │
    ▼
Feature Engine (64+ indicators)
    │
    ▼
PropFirm Brain V6
    │
    ├── Transformer + LSTM
    ├── PPO RL Agent
    └── Regime Detection
    │
    ▼
Signal Generation
    │
    ▼
Risk Manager
    │
    ▼
Order Execution
```

---

## Brain Architecture (PropFirm Brain V6)

```
                    ┌─────────────────────────────────────┐
                    │         PropFirm Brain V6           │
                    └─────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│  Feature Engine │        │ Regime Detector │        │ Strategy Engine │
│  (64 indicators)│        │   (7 regimes)   │        │ (5 strategies)  │
└────────┬────────┘        └────────┬────────┘        └────────┬────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────┐
                    │      Transformer + LSTM Hybrid      │
                    │   ┌─────────────────────────────┐   │
                    │   │     Attention Mechanism     │   │
                    │   │     ┌───┐ ┌───┐ ┌───┐     │   │
                    │   │     │ Q │ │ K │ │ V │     │   │
                    │   │     └───┘ └───┘ └───┘     │   │
                    │   └─────────────────────────────┘   │
                    │   ┌─────────────────────────────┐   │
                    │   │      LSTM Memory Layer      │   │
                    │   └─────────────────────────────┘   │
                    └─────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
             ┌──────────┐   ┌──────────┐   ┌──────────┐
             │   PPO    │   │ Signal   │   │Position  │
             │  Agent   │   │Generator │   │  Sizer   │
             └──────────┘   └──────────┘   └──────────┘
```

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Rate Limit Middleware                   │   │
│  │  • Per-IP tracking  • Burst protection              │   │
│  │  • Endpoint-specific limits                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Security Headers Middleware               │   │
│  │  • X-Content-Type-Options  • X-Frame-Options        │   │
│  │  • X-XSS-Protection        • Referrer-Policy        │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Input Sanitizer                         │   │
│  │  • Symbol validation  • XSS prevention              │   │
│  │  • SQL injection protection                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              CORS Middleware                         │   │
│  │  • Environment-based origins                        │   │
│  │  • Credential support                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### SQLite Tables

```sql
-- Last known prices (for market-closed periods)
CREATE TABLE last_prices (
    symbol TEXT PRIMARY KEY,
    price REAL,
    change REAL,
    change_pct REAL,
    volume INTEGER,
    high REAL,
    low REAL,
    open REAL,
    prev_close REAL,
    timestamp TEXT,
    source TEXT
);

-- Cache entries
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    value TEXT,
    timestamp REAL,
    ttl INTEGER
);

-- Trade history
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    action TEXT,
    quantity REAL,
    price REAL,
    timestamp TEXT,
    pnl REAL,
    source TEXT
);

-- Brain training history
CREATE TABLE training_history (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    epochs INTEGER,
    loss REAL,
    accuracy REAL,
    config TEXT
);
```

---

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/health | GET | Health check |
| /api/market/status | GET | Market hours status |
| /api/market/quote/{symbol} | GET | Get quote |
| /api/brain-v6/signal/{symbol} | GET | AI signal |
| /api/brain-v6/train | POST | Train brain |
| /api/backtest/run | POST | Run backtest |
| /api/settings | GET/POST | Settings |
| /ws/market | WS | Market stream |
| /ws/brain | WS | Brain signals |

---

## Deployment Architecture

```
Production Deployment (Future)

┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer                            │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  API Server 1   │  │  API Server 2   │  │  API Server 3   │
│  (FastAPI)      │  │  (FastAPI)      │  │  (FastAPI)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
           ┌─────────────────┐  ┌─────────────────┐
           │     Redis       │  │   PostgreSQL    │
           │    (Cache)      │  │   (Database)    │
           └─────────────────┘  └─────────────────┘
```

Current local deployment uses SQLite and in-memory caching.
