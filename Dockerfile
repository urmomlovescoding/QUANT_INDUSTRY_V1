# QUANT_INDUSTRY_V1 - Production Docker Image
# Multi-stage build for optimized size

# ============================================
# Stage 1: Python Dependencies Builder
# ============================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Frontend Builder
# ============================================
FROM node:20-alpine as frontend-builder

WORKDIR /frontend

# Copy frontend source
COPY frontend/package*.json ./
RUN npm ci --only=production

COPY frontend/ .
RUN npm run build

# ============================================
# Stage 3: Production Runtime
# ============================================
FROM python:3.11-slim as runtime

# Labels
LABEL maintainer="QUANT_INDUSTRY_V1 Team"
LABEL version="1.0.0"
LABEL description="Institutional-grade quantitative trading platform"

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    APP_ENV=production \
    LOG_LEVEL=INFO

# Create non-root user for security
RUN groupadd -r quant && useradd -r -g quant quant

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=quant:quant . .

# Copy frontend build
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/models/registry /app/checkpoints && \
    chown -R quant:quant /app

# Switch to non-root user
USER quant

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 8001

# Default command
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================
# Stage 4: Development Image (optional)
# ============================================
FROM runtime as development

USER root

# Install dev dependencies
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov black isort mypy

# Install GPU support (optional)
# RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

USER quant

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
