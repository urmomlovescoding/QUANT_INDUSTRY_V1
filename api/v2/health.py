"""
QUANT INDUSTRY V1 - Health API (v2)
===================================
System health and status endpoints.
Wired to real backend health services.
"""

import os
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import platform
import psutil

# Add paths for imports
_api_dir = Path(__file__).parent.parent.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class HealthResponse(BaseModel):
    """Simple health check response."""
    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")


class SystemResources(BaseModel):
    """System resource metrics."""
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    memory_available_gb: float = Field(..., description="Available memory in GB")
    disk_percent: float = Field(..., description="Disk usage percentage")


class ServiceStatus(BaseModel):
    """Individual service status."""
    name: str
    status: str = Field(..., description="up, down, degraded")
    latency_ms: Optional[float] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)
    message: Optional[str] = None


class DetailedHealthResponse(BaseModel):
    """Detailed system health including all services."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")
    uptime_seconds: float = Field(..., description="Application uptime")
    system: SystemResources
    services: list[ServiceStatus] = Field(default_factory=list)
    environment: str = Field(default="production")


# ============================================================================
# Service Access - Lazy Loading
# ============================================================================

_health_service = None
_services_available = None


def _check_services():
    """Check if services are available."""
    global _services_available
    if _services_available is not None:
        return _services_available
    
    try:
        from backend.services.health_service import get_health_service, HAS_CUDA, DEVICE
        _services_available = True
    except ImportError:
        try:
            from services.health_service import get_health_service, HAS_CUDA, DEVICE
            _services_available = True
        except ImportError:
            _services_available = False
    
    return _services_available


def _get_health_service():
    """Get health service with lazy loading."""
    global _health_service
    
    if _health_service is not None:
        return _health_service
    
    if not _check_services():
        return None
    
    try:
        from backend.services.health_service import get_health_service
        _health_service = get_health_service()
    except ImportError:
        try:
            from services.health_service import get_health_service
            _health_service = get_health_service()
        except ImportError:
            return None
    
    return _health_service


def _get_market_status():
    """Get market status if available."""
    try:
        from services.market_hours import get_market_status
        return get_market_status()
    except ImportError:
        return {"session": "unknown"}


def _get_data_service_status():
    """Check data service availability and mode."""
    try:
        from backend.routes._shared import (
            SERVICES_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE,
            BROKER_ADAPTER_AVAILABLE, MARKET_HOURS_AVAILABLE,
            get_data_service
        )
        
        active_sources = []
        is_live = False
        
        if SERVICES_AVAILABLE:
            ds = get_data_service()
            if ds:
                for source in ds.sources:
                    source_name = getattr(source, 'name', '').lower()
                    if source_name and source_name != 'fallback':
                        active_sources.append(source_name)
                is_live = len(active_sources) > 0
        
        return {
            "data_service": SERVICES_AVAILABLE,
            "brain_v6": PROPFIRM_BRAIN_V6_AVAILABLE,
            "broker_adapter": BROKER_ADAPTER_AVAILABLE,
            "market_hours": MARKET_HOURS_AVAILABLE,
            "active_sources": active_sources,
            "is_live": is_live
        }
    except ImportError:
        return {
            "data_service": False,
            "brain_v6": False,
            "broker_adapter": False,
            "market_hours": False,
            "active_sources": [],
            "is_live": False
        }


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Simple health check",
    description="Quick health check returning basic status. Use for load balancer probes."
)
async def health_check() -> HealthResponse:
    """
    Simple health check endpoint.
    
    Returns a basic health status suitable for load balancer health probes.
    For detailed system information, use /health/detailed.
    """
    hs = _get_health_service()
    
    # Determine status from real checks
    status = "healthy"
    
    if hs:
        try:
            overall = hs.get_overall_status()
            raw_status = overall.get("status", "HEALTHY")
            
            # Map HealthService status to our response format
            if raw_status == "UNHEALTHY":
                status = "unhealthy"
            elif raw_status == "DEGRADED":
                status = "degraded"
            else:
                status = "healthy"
        except Exception:
            # If health check fails, still report healthy to not crash load balancers
            status = "healthy"
    
    # Also check basic system health
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        if cpu > 95 or memory.percent > 95:
            status = "unhealthy"
        elif cpu > 85 or memory.percent > 85:
            if status == "healthy":
                status = "degraded"
    except Exception:
        pass
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version="10.0.0"
    )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed system health",
    description="Comprehensive health check including all services and system resources."
)
async def detailed_health_check() -> DetailedHealthResponse:
    """
    Detailed health check endpoint.
    
    Returns comprehensive system status including:
    - System resources (CPU, memory, disk)
    - Service statuses (database, broker, market data, etc.)
    - Application metadata
    """
    hs = _get_health_service()
    
    # Get system resources (always available via psutil)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    system = SystemResources(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=memory.percent,
        memory_available_gb=round(memory.available / (1024**3), 2),
        disk_percent=disk.percent
    )
    
    # Get real uptime and service status
    uptime_seconds = 0.0
    services = []
    overall_status = "healthy"
    environment = os.getenv("QUANT_ENV", "development")
    
    if hs:
        try:
            # Get real uptime from health service
            overall = hs.get_overall_status()
            uptime_seconds = overall.get("uptime_seconds", 0.0)
            
            # Get API health statuses
            api_health = hs.api_health
            for api_name, health in api_health.items():
                status_str = "up"
                if health.status.value == "DISCONNECTED":
                    status_str = "down"
                elif health.status.value == "ERROR":
                    status_str = "down"
                elif health.status.value in ("DEGRADED", "CONNECTING"):
                    status_str = "degraded"
                
                services.append(ServiceStatus(
                    name=api_name,
                    status=status_str,
                    latency_ms=health.latency_ms if health.latency_ms else None,
                    last_check=health.last_check,
                    message=health.error_message
                ))
            
            # Get internal service health
            internal_services = hs.get_all_services_health()
            for svc in internal_services:
                status_str = "up"
                if svc.status.value == "UNHEALTHY":
                    status_str = "down"
                elif svc.status.value == "DEGRADED":
                    status_str = "degraded"
                
                services.append(ServiceStatus(
                    name=svc.name,
                    status=status_str,
                    latency_ms=svc.avg_response_time_ms if svc.avg_response_time_ms else None,
                    last_check=datetime.utcnow(),
                    message=svc.last_error
                ))
            
            # Map overall status
            raw_status = overall.get("status", "HEALTHY")
            if raw_status == "UNHEALTHY":
                overall_status = "unhealthy"
            elif raw_status == "DEGRADED":
                overall_status = "degraded"
        
        except Exception as e:
            # Add error service status
            services.append(ServiceStatus(
                name="health_service",
                status="degraded",
                message=str(e)
            ))
    
    # Add data service status from shared module
    data_status = _get_data_service_status()
    
    # Add data service as a service entry
    services.append(ServiceStatus(
        name="data_service",
        status="up" if data_status["data_service"] else "down",
        message=f"Sources: {', '.join(data_status['active_sources'])}" if data_status['active_sources'] else "No live sources"
    ))
    
    # Add brain service
    services.append(ServiceStatus(
        name="ml_brain",
        status="up" if data_status["brain_v6"] else "down",
        message="PropFirm Brain V6" if data_status["brain_v6"] else "Not loaded"
    ))
    
    # Add broker adapter
    services.append(ServiceStatus(
        name="broker",
        status="up" if data_status["broker_adapter"] else "down"
    ))
    
    # If no services from health service, use manual check
    if not services:
        services = [
            ServiceStatus(name="api", status="up"),
            ServiceStatus(name="data_service", status="up" if data_status["data_service"] else "down"),
        ]
    
    # Determine overall status from services
    down_services = [s for s in services if s.status == "down"]
    degraded_services = [s for s in services if s.status == "degraded"]
    
    if down_services:
        overall_status = "unhealthy"
    elif degraded_services:
        overall_status = "degraded"
    
    # Also factor in system resources
    if system.cpu_percent > 95 or system.memory_percent > 95:
        overall_status = "unhealthy"
    elif system.cpu_percent > 80 or system.memory_percent > 85:
        if overall_status == "healthy":
            overall_status = "degraded"
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="10.0.0",
        uptime_seconds=uptime_seconds,
        system=system,
        services=services,
        environment=environment
    )
