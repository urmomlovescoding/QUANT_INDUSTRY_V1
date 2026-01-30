"""
QUANT INDUSTRY V1 - Health API (v2)
===================================
System health and status endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import platform
import psutil

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
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0"
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
    # Get system resources
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    system = SystemResources(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=memory.percent,
        memory_available_gb=round(memory.available / (1024**3), 2),
        disk_percent=disk.percent
    )
    
    # Mock service statuses (replace with real checks)
    services = [
        ServiceStatus(name="database", status="up", latency_ms=2.5),
        ServiceStatus(name="broker", status="up", latency_ms=45.0),
        ServiceStatus(name="market_data", status="up", latency_ms=12.3),
        ServiceStatus(name="ml_brain", status="up", latency_ms=5.1),
        ServiceStatus(name="redis", status="up", latency_ms=0.8),
    ]
    
    # Determine overall status
    down_services = [s for s in services if s.status == "down"]
    degraded_services = [s for s in services if s.status == "degraded"]
    
    if down_services:
        overall_status = "unhealthy"
    elif degraded_services:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime_seconds=3600.0,  # Mock - replace with actual uptime tracking
        system=system,
        services=services,
        environment="development"
    )
