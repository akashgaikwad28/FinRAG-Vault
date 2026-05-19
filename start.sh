#!/bin/sh
# ==============================================================================
# Production Startup Script for FinRAG Vault
# ==============================================================================

# 1. Run Alembic Database Migrations
echo "Running database migrations..."
alembic upgrade head

if [ $? -ne 0 ]; then
    echo "Database migrations failed! Exiting."
    exit 1
fi
echo "Database migrations completed successfully."

# 2. Start Uvicorn Web Server
echo "Starting FastAPI application via Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
