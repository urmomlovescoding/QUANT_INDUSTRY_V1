"""
QUANT INDUSTRY - API Router Registry
=====================================
Modular router architecture for the FastAPI backend.
Each router module handles a specific domain of the API.

Usage:
    from routers import register_all_routers
    register_all_routers(app)

This module provides the infrastructure for gradually migrating
routes from the monolithic main.py into domain-specific routers.
"""

import importlib
import logging
from typing import List

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Router modules to register (add new routers here)
ROUTER_MODULES: List[str] = [
    "routers.market",
    "routers.data_integrity",
]


def register_all_routers(app: FastAPI) -> int:
    """
    Register all router modules with the FastAPI application.

    Args:
        app: The FastAPI application instance

    Returns:
        Number of routers successfully registered
    """
    registered = 0

    for module_name in ROUTER_MODULES:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "router"):
                app.include_router(module.router)
                registered += 1
                logger.info(f"Registered router: {module_name}")
            else:
                logger.warning(f"Router module {module_name} has no 'router' attribute")
        except ImportError as e:
            logger.warning(f"Failed to import router {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error registering router {module_name}: {e}")

    logger.info(f"Registered {registered}/{len(ROUTER_MODULES)} routers")
    return registered
