# ==========================================
# Stage 1: Build dependencies in virtual env
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

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt


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

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy codebase contents
COPY . .

# Setup non-root execution user for security compliance
RUN groupadd -g 999 appgroup && \
    useradd -r -u 999 -g appgroup -d /app appuser

# Initialize local chunked upload folders, set execute permissions, and assign ownership
RUN mkdir -p /app/data/uploads && \
    chmod +x /app/start.sh && \
    chown -R appuser:appgroup /app && \
    chown -R appuser:appgroup /opt/venv

USER appuser

# Expose FastAPI default production port
EXPOSE 8000

# Set environment controls
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Run the database migration and start server using the startup script
CMD ["/app/start.sh"]
