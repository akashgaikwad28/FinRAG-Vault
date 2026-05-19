# ==========================================
# Stage 1: Build dependencies & cache wheels
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system utilities needed to build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements file to leverage Docker layer cache
COPY requirements.txt .

# Pre-compile wheels into a local cache directory
RUN pip install --no-cache-dir --user -r requirements.txt


# ==========================================
# Stage 2: Final minimal execution image
# ==========================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime dependencies (libpq for PostgreSQL connection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python package binaries from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy codebase contents
COPY . .

# Setup non-root execution user for security compliance
RUN groupadd -g 999 appgroup && \
    useradd -r -u 999 -g appgroup -d /app appuser

# Initialize local chunked upload folders and assign ownership to appuser
RUN mkdir -p /app/data/uploads && \
    chown -R appuser:appgroup /app

USER appuser

# Expose FastAPI default production port
EXPOSE 8000

# Set environment controls
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Run server with standard uvicorn production flags
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
