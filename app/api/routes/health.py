from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.api.deps.deps import get_db
from app.services.vector_service import VectorService
from app.schemas.auth import StandardResponse

router = APIRouter(prefix="/health", tags=["System Health"])
logger = logging.getLogger("finragvault.routes.health")


@router.get(
    "",
    response_model=StandardResponse,
    summary="Perform liveness and readiness health checks",
    description="Actively verifies DB connection states (PostgreSQL + Qdrant) and alerts orchestrators if any systems are degraded."
)
async def check_health(
    response: Response,
    session: AsyncSession = Depends(get_db)
) -> StandardResponse:
    postgres_healthy = False
    qdrant_healthy = False
    details = {}

    # 1. Verify PostgreSQL Database connectivity
    try:
        await session.execute(text("SELECT 1"))
        postgres_healthy = True
        details["postgres"] = "healthy"
    except Exception as e:
        logger.error(f"Health check failed for PostgreSQL: {str(e)}")
        details["postgres"] = f"unhealthy: {str(e)}"

    # 2. Verify Qdrant Vector Database connectivity
    try:
        client = VectorService.get_client()
        # Ping Qdrant clusters using readyz endpoint check
        await client.get_collections()
        qdrant_healthy = True
        details["qdrant"] = "healthy"
    except Exception as e:
        logger.error(f"Health check failed for Qdrant: {str(e)}")
        details["qdrant"] = f"unhealthy: {str(e)}"

    # Determine status and response code
    if postgres_healthy and qdrant_healthy:
        response.status_code = status.HTTP_200_OK
        return StandardResponse(
            success=True,
            message="All services are online and healthy",
            data=details
        )
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return StandardResponse(
            success=False,
            message="One or more critical services are degraded",
            data=details
        )
