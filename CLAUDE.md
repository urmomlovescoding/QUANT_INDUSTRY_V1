# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QUANT INDUSTRY v10.0 is an institutional-grade quantitative trading platform with:
- **Frontend**: React 18/TypeScript/Vite (port 3000)
- **Backend**: FastAPI/Python REST API (port 8000)
- **Desktop**: Electron wrapper with system monitoring

## Development Commands

### Backend (C:\quant_industry_v1\backend)
```bash
python -m venv venv                    # Create virtual environment
venv\Scripts\activate                  # Activate venv (Windows)
pip install -r requirements.txt        # Install dependencies
uvicorn main:app --host 0.0.0.0 --port 8000 --reload  # Start server
```
API docs: http://localhost:8000/docs

### Frontend (C:\quant_industry_v1\frontend)
```bash
npm install          # Install dependencies
npm run dev          # Start dev server (localhost:3000)
npm run build        # Production build to dist/
npm run lint         # Run ESLint
```

### Desktop (C:\quant_industry_v1\desktop)
```bash
npm install          # Install Electron dependencies
npm run dev          # Dev mode (connects to localhost:3000)
npm run build:win    # Build Windows installer
```

### Quick Start Scripts
- `START.bat` - **DEFAULT**: Launches Electron desktop app (backend + frontend + Electron)
- `START_BROWSER.bat` - Browser mode (backend + frontend in browser)

### Testing
```bash
python run_tests.py                    # Run all tests
python run_tests.py --quick            # Skip slow/integration tests
python run_tests.py --coverage         # With coverage report
python run_tests.py --module brain     # Test specific module
python run_tests.py --failfast         # Stop on first failure
python run_tests.py --parallel         # Run tests in parallel

# Direct pytest (from backend/)
cd backend && python -m pytest tests/ -v --tb=short
pytest tests/test_brain.py -k "test_specific"  # Single test
```

### Linting & Formatting
```bash
ruff check .                           # Lint with ruff
ruff format .                          # Format with ruff
black --line-length 100 .              # Format with black
isort .                                # Sort imports
mypy .                                 # Type checking
```

## Architecture

### Data Flow
1. **Market Data**: External APIs → Rate Limiter → Data Fetcher → Validator → Cache → SQLite
2. **Signal Generation**: Market Data → Features → Regime Detector → ML Models → Meta-Learner → Signal
3. **Execution**: Signal → Risk Check → Position Sizer → Order → Broker → Audit Log

### Module Dependencies
```
core (types, interfaces)
  ↓
utils, config, db
  ↓
data ← brain ← (models, features, RL)
  ↓
execution, risk, services
  ↓
ui
```

### Key Backend Structure
- `main.py` - FastAPI entry point with all routes (~3,600 lines, 100+ endpoints)
- `services/` - Business logic (data_service, trading_service, risk_service)
- `brain/` - ML/RL/DL trading engines (propfirm_brain_v6, beast_ml, algo_bot)
- `execution/` - Trade execution, broker adapters, kill switch
- `middleware/` - Security, rate limiting, performance

### Key Frontend Structure
- `src/views/` - Page components (38+ views)
- `src/components/` - Reusable UI (layout, charts, cards, tables)
- `src/hooks/` - Custom React hooks including WebSocket
- `src/store/` - Zustand state management
- `src/api/` - API client with authentication

## Technology Stack

**Frontend**: React 18, TypeScript 5.3, Vite 5.1, Tailwind CSS 3.4, Recharts, Zustand, Socket.io-client

**Backend**: FastAPI 0.109, Uvicorn, Pydantic 2.5, SQLAlchemy 2.0, Python 3.9+

**ML/Data**: NumPy, Pandas, scikit-learn, XGBoost, LightGBM, PyTorch, stable-baselines3, pandas-ta

**Data Sources**: Alpaca Markets (primary), Yahoo Finance (fallback), Polygon.io

## WebSocket

Real-time data via `/ws/unified` endpoint:
- `market` - Price ticks
- `signals` - Trading signals
- `trades` - Trade updates
- `brain` - AI brain status
- `system` - System health
- `flow` - Options flow

## PropFirm Brain V6

The main ML/RL/DL trading brain at `backend/brain/propfirm_brain_v6.py`:

**Components**:
- TradingTransformer: Multi-head attention + LSTM hybrid encoder
- PPOAgent: Proximal Policy Optimization for trading decisions
- StrategyEnsemble: 20+ strategies with dynamic weighting
- BayesianRegimeDetector: 7-regime market classification
- FeatureEngine: 64+ technical indicators

**Key Methods**:
```python
brain = get_propfirm_brain_v6(ruleset=TPT_50K)
brain.generate_signal(df, symbol)     # Generate trading signal
brain.train_step(trades)              # Manual training step
brain.record_trade(trade)             # Record trade for learning
brain.start_auto_training()           # Background training
brain.get_status()                    # Full status report
```

**Prop Firm Rulesets**: TPT_50K, TPT_100K, APEX_50K

## Feedback Loop System

Closed-loop learning at `backend/brain/feedback_loop.py`:
```
ML Brain → Signals → Trading Brain → Execution → Outcomes → Feedback → ML Brain (Adapt)
```

Convergence targets: 65% win rate, 1.5 profit factor, 1.5 Sharpe ratio

## Important Patterns

- Frontend proxies `/api/*` to port 8000 (vite.config.ts)
- SQLite with WAL mode for concurrency
- Electron IPC via `window.electronAPI` (preload.js)
- Keyboard shortcuts: `Ctrl+K` (command palette), `Ctrl+T` (quick trade), `F11` (fullscreen)
- Live data mode enabled by default (force_live=True)

## Theme System

Bloomberg Terminal-inspired dark theme (configured in `frontend/tailwind.config.js`):
- Primary accent: `#00d4aa` (cyan/teal)
- Bullish: `#00c853` (green)
- Bearish: `#ff5252` (red)
- Background: `#0a0a12` (deep blue-black)

## Database

- **trading.db** - Main trading database
- **propfirm_brain_v6.db** - ML model checkpoints, training logs, trade records

Schema includes: trades, model_checkpoints, training_logs tables

## Key API Endpoint Groups

- `/api/brain-v6/*` - PropFirm Brain V6 (status, signals, training, config)
- `/api/feedback/*` - Feedback loop (status, metrics, strategies, record)
- `/api/market/*` - Market data (tickers, quotes, sectors, movers)
- `/api/options/*` - Options (chain, GEX analysis)
- `/api/neural/*` - Neural AI (analysis, predictions, regime)
- `/api/portfolio/*` - Portfolio (holdings, performance)
- `/api/research/*` - Research (13F, SEC, dark pool, earnings)
- `/api/pairs/*` - Pairs trading (cointegration analysis)
- `/api/news/*` - News with sentiment
- `/api/reports/*` - Report generation
