"""
QUANT INDUSTRY V1 - Main API Application
========================================
FastAPI application bringing together all routes.
"""

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


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "QUANT INDUSTRY V1",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "tax": "/tax",
            "reconciliation": "/reconciliation",
            "backtest": "/backtest",
            "mobile": "/mobile"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
