"""
QUANT INDUSTRY - Backend Main (Thin Wrapper)
=============================================
This module now acts as a thin wrapper that imports from the unified main.py
for backwards compatibility.

For the full application, run from the project root:
    uvicorn main:app --host 0.0.0.0 --port 8000

The original monolithic implementation is preserved in main.py.bak
"""

import sys
from pathlib import Path

# Add project root to path so we can import from main.py
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the unified app from the project root
try:
    from main import app
    print("✅ Imported unified app from main.py")
except ImportError as e:
    print(f"⚠️ Could not import unified app: {e}")
    print("Falling back to standalone mode...")
    
    # Fallback: create a minimal standalone app
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(
        title="QUANT INDUSTRY API",
        description="Backend fallback mode",
        version="10.0"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        return {"message": "QUANT INDUSTRY API v10.0 (fallback mode)", "status": "operational"}
    
    @app.get("/api/health")
    async def health():
        return {"status": "healthy", "mode": "fallback"}

    # Try to import routes from the extracted route modules
    try:
        from backend.routes.market_routes import router as market_router
        from backend.routes.system_routes import router as system_router
        from backend.routes.trading_routes import router as trading_router
        from backend.routes.brain_routes import router as brain_router
        from backend.routes.risk_routes import router as risk_router
        from backend.routes.options_routes import router as options_router
        from backend.routes.websocket_routes import router as ws_router
        from backend.routes.research_routes import router as research_router
        from backend.routes.quant_routes import router as quant_router
        from backend.routes.portfolio_routes import router as portfolio_router
        from backend.routes.broker_routes import router as broker_router
        from backend.routes.parity_routes import router as parity_router
        from backend.routes.algobot_routes import router as algobot_router
        
        app.include_router(market_router)
        app.include_router(system_router)
        app.include_router(trading_router)
        app.include_router(brain_router)
        app.include_router(risk_router)
        app.include_router(options_router)
        app.include_router(ws_router)
        app.include_router(research_router)
        app.include_router(quant_router)
        app.include_router(portfolio_router)
        app.include_router(broker_router)
        app.include_router(parity_router)
        app.include_router(algobot_router)
        
        print("✅ Loaded extracted route modules")
    except Exception as e:
        print(f"⚠️ Could not load extracted routes: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
