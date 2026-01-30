"""
QUANT INDUSTRY V1 - Main API Application
========================================
FastAPI application bringing together all routes.
"""

# Load environment variables from .env file
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket manager reference for lifecycle management
_ws_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown tasks."""
    global _ws_manager
    # Startup
    try:
        from api.websocket.manager import get_ws_manager
        _ws_manager = get_ws_manager()
        await _ws_manager.start()
        logger.info("✅ WebSocket manager started")
    except Exception as e:
        logger.warning(f"Could not start WebSocket manager: {e}")
    
    yield
    
    # Shutdown
    if _ws_manager:
        await _ws_manager.stop()
        logger.info("WebSocket manager stopped")

# Create app
app = FastAPI(
    title="QUANT INDUSTRY V1",
    description="Institutional-grade quantitative trading platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Deprecation middleware for v1 → v2 migration
try:
    from api.middleware.deprecation import (
        add_deprecation_middleware,
        create_metrics_routes,
    )
    add_deprecation_middleware(app, log_warnings=True, track_metrics=True)
    logger.info("✅ Deprecation middleware enabled")
    
    # Mount deprecation metrics routes under /admin
    metrics_router = create_metrics_routes()
    app.include_router(metrics_router, prefix="/admin", tags=["admin"])
    logger.info("✅ Deprecation metrics routes mounted at /admin/deprecation/*")
except Exception as e:
    logger.warning(f"Could not load deprecation middleware: {e}")

# Import and register routes
try:
    from api.routes.core_routes import router as core_router
    app.include_router(core_router)
    logger.info("Loaded core routes")
except Exception as e:
    logger.warning(f"Could not load core routes: {e}")

# WebSocket routes
try:
    from api.websocket.routes import router as ws_router
    app.include_router(ws_router)
    logger.info("Loaded WebSocket routes")
except Exception as e:
    logger.warning(f"Could not load WebSocket routes: {e}")

try:
    from api.routes.tax_routes import router as tax_router
    app.include_router(tax_router)
    logger.info("Loaded tax routes")
except Exception as e:
    logger.warning(f"Could not load tax routes: {e}")

try:
    from api.routes.reconciliation_routes import router as recon_router
    app.include_router(recon_router)
    logger.info("Loaded reconciliation routes")
except Exception as e:
    logger.warning(f"Could not load reconciliation routes: {e}")

try:
    from api.routes.mobile_api import router as mobile_router
    app.include_router(mobile_router)
    logger.info("Loaded mobile routes")
except Exception as e:
    logger.warning(f"Could not load mobile routes: {e}")

try:
    from services.backtest_service import BacktestService, create_backtest_routes
    backtest_service = BacktestService(max_workers=4)
    backtest_router = create_backtest_routes(backtest_service)
    app.include_router(backtest_router)
    logger.info("Loaded backtest routes")
except Exception as e:
    logger.warning(f"Could not load backtest routes: {e}")

try:
    from api.routes.decision_intelligence_routes import router as decision_intel_router
    app.include_router(decision_intel_router)
    logger.info("Loaded decision intelligence routes")
except Exception as e:
    logger.warning(f"Could not load decision intelligence routes: {e}")

# New alpha module routes
try:
    from api.routes.options_flow_routes import router as options_flow_router
    app.include_router(options_flow_router)
    logger.info("Loaded options flow routes")
except Exception as e:
    logger.warning(f"Could not load options flow routes: {e}")

try:
    from api.routes.microstructure_routes import router as microstructure_router
    app.include_router(microstructure_router)
    logger.info("Loaded microstructure routes")
except Exception as e:
    logger.warning(f"Could not load microstructure routes: {e}")

try:
    from api.routes.cross_exchange_routes import router as cross_exchange_router
    app.include_router(cross_exchange_router)
    logger.info("Loaded cross-exchange arbitrage routes")
except Exception as e:
    logger.warning(f"Could not load cross-exchange routes: {e}")

try:
    from api.routes.news_events_routes import router as news_events_router
    app.include_router(news_events_router)
    logger.info("Loaded news events routes")
except Exception as e:
    logger.warning(f"Could not load news events routes: {e}")

# ML Brain routes
try:
    from api.routes.brain_routes import router as brain_router
    app.include_router(brain_router)
    logger.info("Loaded ML Brain routes")
except Exception as e:
    logger.warning(f"Could not load ML Brain routes: {e}")

# API v2 - Consolidated Routes
try:
    from api.v2 import api_v2
    app.include_router(api_v2, prefix="/api/v2")
    logger.info("Loaded API v2 routes")
except Exception as e:
    logger.warning(f"Could not load API v2 routes: {e}")

# V2 API Routes (consolidated)
try:
    from api.v2 import api_v2
    app.include_router(api_v2, prefix="/api/v2")
    logger.info("✅ Loaded V2 API routes")
except Exception as e:
    logger.warning(f"Could not load V2 routes: {e}")

# Deprecation Middleware
try:
    from api.middleware.deprecation import DeprecationMiddleware
    app.add_middleware(DeprecationMiddleware)
    logger.info("✅ Deprecation middleware registered")
except Exception as e:
    logger.warning(f"Could not load deprecation middleware: {e}")


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "QUANT INDUSTRY V1",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "v2": "/api/v2 (recommended)",
            "tax": "/tax",
            "reconciliation": "/reconciliation",
            "backtest": "/backtest",
            "mobile": "/mobile",
            "options_flow": "/api/v1/options-flow",
            "microstructure": "/api/v1/microstructure",
            "arbitrage": "/api/v1/arbitrage",
            "news_events": "/api/v1/news-events"
        },
        "v2_domains": {
            "health": "/api/v2/health",
            "market": "/api/v2/market",
            "trading": "/api/v2/trading",
            "portfolio": "/api/v2/portfolio",
            "risk": "/api/v2/risk",
            "brain": "/api/v2/brain",
            "options": "/api/v2/options",
            "backtest": "/api/v2/backtest",
            "research": "/api/v2/research",
            "settings": "/api/v2/settings"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
