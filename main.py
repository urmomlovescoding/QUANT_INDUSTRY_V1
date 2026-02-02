"""
QUANT INDUSTRY V1 - Unified Main Entry Point
=============================================
This is the unified FastAPI application that combines routes from both:
- api/routes/ (modular alpha routes)
- backend/routes/ (extracted from monolithic backend)

All functionality is preserved. Duplicate endpoints are resolved by preferring
api/routes/ versions (more modern/modular implementations).

Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global WebSocket manager reference
_ws_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown tasks."""
    global _ws_manager
    
    logger.info("[STARTUP] QUANT INDUSTRY V1 - Unified Backend starting...")
    
    # Initialize WebSocket manager
    try:
        from api.websocket.manager import get_ws_manager
        _ws_manager = get_ws_manager()
        await _ws_manager.start()
        logger.info("[OK] WebSocket manager started (api)")
    except Exception as e:
        logger.warning(f"Could not start api WebSocket manager: {e}")
    
    # Initialize data integrity layer
    try:
        from core.data_integrity import init_data_integrity, DataMode
        init_data_integrity(DataMode.PAPER)
        logger.info("[OK] Data integrity layer initialized (PAPER mode)")
    except Exception as e:
        logger.warning(f"Data integrity not available: {e}")
    
    # Start background market data refresh
    try:
        from backend.routes._shared import refresh_market_data
        asyncio.create_task(_background_refresh())
        logger.info("[OK] Background market data refresh started")
    except Exception as e:
        logger.warning(f"Background refresh not available: {e}")
    
    logger.info("[STARTUP] All services initialized")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("[SHUTDOWN] Shutting down...")
    if _ws_manager:
        await _ws_manager.stop()
        logger.info("WebSocket manager stopped")
    logger.info("[SHUTDOWN] Complete")


async def _background_refresh():
    """Background task to refresh market data."""
    from backend.routes._shared import refresh_market_data
    while True:
        try:
            await asyncio.sleep(30)
            refresh_market_data()
        except Exception as e:
            logger.debug(f"Background refresh error: {e}")


# Create FastAPI application
app = FastAPI(
    title="QUANT INDUSTRY V1 - Unified",
    description="Institutional-grade quantitative trading platform with ML/RL/DL brain",
    version="10.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware - SECURITY: Use environment-specific origins
try:
    from backend.middleware.security import get_cors_origins
    cors_origins = get_cors_origins()
except ImportError:
    # Fallback for development (without wildcard)
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3004",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Try to add security middleware
try:
    from middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    logger.info("[OK] Security middleware registered")
except ImportError as e:
    logger.warning(f"Security middleware not available: {e}")

# Try to add performance middleware
try:
    from middleware.performance import TimingMiddleware, ResponseCacheMiddleware
    app.add_middleware(TimingMiddleware)
    app.add_middleware(ResponseCacheMiddleware)
    logger.info("[OK] Performance middleware registered")
except ImportError as e:
    logger.warning(f"Performance middleware not available: {e}")


# ==============================================================================
# ROUTE REGISTRATION - API ROUTES (PREFERRED - MODULAR)
# ==============================================================================

def _safe_include_router(router_import, router_attr="router", prefix="", name=""):
    """Safely include a router with error handling."""
    try:
        module = __import__(router_import, fromlist=[router_attr])
        router = getattr(module, router_attr)
        app.include_router(router, prefix=prefix)
        logger.info(f"[OK] Loaded {name or router_import}")
        return True
    except Exception as e:
        logger.warning(f"[WARN]️ Could not load {name or router_import}: {e}")
        return False


# API Routes (from api/routes/ - modular alpha implementations)
logger.info("Loading api/routes/ (modular implementations)...")

_safe_include_router("api.routes.core_routes", name="core routes")
_safe_include_router("api.routes.brain_routes", name="brain routes (api)")
_safe_include_router("api.routes.tax_routes", name="tax routes")
_safe_include_router("api.routes.reconciliation_routes", name="reconciliation routes")
_safe_include_router("api.routes.mobile_api", name="mobile routes")
_safe_include_router("api.routes.decision_intelligence_routes", name="decision intelligence routes")
_safe_include_router("api.routes.options_flow_routes", name="options flow routes")
_safe_include_router("api.routes.microstructure_routes", name="microstructure routes")
_safe_include_router("api.routes.cross_exchange_routes", name="cross-exchange routes")
_safe_include_router("api.routes.news_events_routes", name="news events routes")
_safe_include_router("api.routes.prop_firm_routes", name="prop firm routes")

# WebSocket routes from api
try:
    from api.websocket.routes import router as api_ws_router
    app.include_router(api_ws_router)
    logger.info("[OK] Loaded WebSocket routes (api)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load api WebSocket routes: {e}")

# Backtest service routes
try:
    from services.backtest_service import BacktestService, create_backtest_routes
    backtest_service = BacktestService(max_workers=4)
    backtest_router = create_backtest_routes(backtest_service)
    app.include_router(backtest_router)
    logger.info("[OK] Loaded backtest routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load backtest routes: {e}")


# ==============================================================================
# ROUTE REGISTRATION - BACKEND ROUTES (EXTRACTED FROM MONOLITHIC)
# ==============================================================================

logger.info("Loading backend/routes/ (extracted routes)...")

try:
    from backend.routes.market_routes import router as market_router
    app.include_router(market_router)
    logger.info("[OK] Loaded market routes (backend)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load market routes: {e}")

try:
    from backend.routes.trading_routes import router as trading_router
    app.include_router(trading_router)
    logger.info("[OK] Loaded trading routes (backend)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load trading routes: {e}")

try:
    from backend.routes.brain_routes import router as brain_router_backend
    app.include_router(brain_router_backend)
    logger.info("[OK] Loaded brain routes (backend)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load brain routes (backend): {e}")

try:
    from backend.routes.risk_routes import router as risk_router
    app.include_router(risk_router)
    logger.info("[OK] Loaded risk routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load risk routes: {e}")

try:
    from backend.routes.options_routes import router as options_router
    app.include_router(options_router)
    logger.info("[OK] Loaded options routes (backend)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load options routes: {e}")

try:
    from backend.routes.system_routes import router as system_router
    app.include_router(system_router)
    logger.info("[OK] Loaded system routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load system routes: {e}")

try:
    from backend.routes.websocket_routes import router as ws_router_backend
    app.include_router(ws_router_backend)
    logger.info("[OK] Loaded WebSocket routes (backend)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load WebSocket routes (backend): {e}")

try:
    from backend.routes.research_routes import router as research_router
    app.include_router(research_router)
    logger.info("[OK] Loaded research routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load research routes: {e}")

try:
    from backend.routes.quant_routes import router as quant_router
    app.include_router(quant_router)
    logger.info("[OK] Loaded quant routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load quant routes: {e}")

try:
    from backend.routes.portfolio_routes import router as portfolio_router
    app.include_router(portfolio_router)
    logger.info("[OK] Loaded portfolio routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load portfolio routes: {e}")

try:
    from backend.routes.broker_routes import router as broker_router
    app.include_router(broker_router)
    logger.info("[OK] Loaded broker routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load broker routes: {e}")

try:
    from backend.routes.parity_routes import router as parity_router
    app.include_router(parity_router)
    logger.info("[OK] Loaded parity routes (ICT, Memory, Regime, TPT, Journal, Learning)")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load parity routes: {e}")

try:
    from backend.routes.algobot_routes import router as algobot_router
    app.include_router(algobot_router)
    logger.info("[OK] Loaded algobot routes")
except Exception as e:
    logger.warning(f"[WARN]️ Could not load algobot routes: {e}")


# ==============================================================================
# ROOT ENDPOINTS
# ==============================================================================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "QUANT INDUSTRY V1 - Unified",
        "version": "10.0",
        "status": "running",
        "docs": "/docs",
        "architecture": "unified",
        "endpoints": {
            "health": "/api/health",
            "market": "/api/market/*",
            "trading": "/api/signals/*, /api/positions, /api/orders",
            "brain": "/api/brain-v6/*",
            "risk": "/api/risk/*",
            "options": "/api/options/*",
            "research": "/api/research/*",
            "quant": "/api/quant/*, /api/backtest/*",
            "portfolio": "/api/portfolio/*",
            "websocket": "/ws/market, /ws/signals, /ws/brain, /ws/system"
        }
    }


@app.get("/health")
async def health():
    """Basic health check endpoint"""
    return {"status": "healthy"}


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
