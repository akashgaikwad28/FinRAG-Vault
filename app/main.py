from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from collections import defaultdict
import logging

from app.core.config import settings
from app.core.exceptions import setup_exception_handlers
from app.core.database import AsyncSessionLocal
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from app.services.vector_service import VectorService

# Route Routers imports
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.roles import router as roles_router
from app.api.routes.documents import router as documents_router
from app.api.routes.rag import router as rag_router
from app.api.routes.health import router as health_router

logger = logging.getLogger("finragvault.main")


async def seed_database() -> None:
    """Provisions default roles and a default Administrator account if not already in DB."""
    from app.models.role import Role
    from app.models.user import User
    from app.core.security import get_password_hash
    from sqlalchemy import select

    logger.info("Checking database seeds...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Seed standard security Roles
            target_roles = {
                "Admin": "Administrator role with unlimited clearance.",
                "Financial Analyst": "Financial document processor with upload, read, and search clearances.",
                "Auditor": "Auditing role with read-only document access.",
                "Client": "External clients restricted strictly to their company boundaries."
            }
            
            roles_map = {}
            for name, desc in target_roles.items():
                query = select(Role).where(Role.name == name)
                res = await session.execute(query)
                role = res.scalar_one_or_none()
                if not role:
                    logger.info(f"Seeding missing Role: '{name}'")
                    role = Role(name=name, description=desc)
                    session.add(role)
                roles_map[name] = role
                
            await session.flush()  # Allocate UUID primary keys
            
            # 2. Seed Default Administrator account
            admin_username = "admin"
            admin_email = "admin@finragvault.com"
            
            query = select(User).where(User.username == admin_username)
            res = await session.execute(query)
            admin_user = res.scalar_one_or_none()
            
            if not admin_user:
                logger.info(f"Seeding Default Administrator user: '{admin_email}'")
                admin_user = User(
                    username=admin_username,
                    email=admin_email,
                    hashed_password=get_password_hash("AdminPassword123!"),
                    company_name="FinRAG Vault Admin",
                    is_active=True
                )
                admin_user.roles.append(roles_map["Admin"])
                session.add(admin_user)
                
            await session.commit()
            logger.info("Database seeding checks completed successfully.")
            
        except Exception as e:
            logger.error(f"Error seeding database: {str(e)}", exc_info=True)
            await session.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan Context Manager handling system startups and cleanups."""
    logger.info("Initializing system lifespan startup hooks...")
    
    # 1. Ensure Qdrant vector database collection exists
    await VectorService.verify_collection_on_startup()
    
    # 2. Seed default roles and admin account
    await seed_database()
    
    yield
    
    logger.info("De-initializing system lifespan...")


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Financial Document Management System with AI-powered semantic search using RAG.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# -------------------------------------------------------------
# Middlewares registration
# -------------------------------------------------------------

# Simple IP-based Rate Limiter middleware
REQUESTS_RECORD = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Clean up sliding window log
    timestamps = REQUESTS_RECORD[client_ip]
    while timestamps and timestamps[0] < now - settings.RATE_LIMIT_DURATION:
        timestamps.pop(0)
        
    if len(timestamps) >= settings.RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Rate limit triggered for IP '{client_ip}' ({len(timestamps)} requests in sliding window)")
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Too many requests. Please slow down and try again later."
            }
        )
        
    timestamps.append(now)
    return await call_next(request)


# CORS configurations
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Structured Logging Correlation middlewares
app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

# Setup customized exception handlers
setup_exception_handlers(app)

# -------------------------------------------------------------
# Route routers registration
# -------------------------------------------------------------
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(roles_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(rag_router, prefix=settings.API_V1_STR)
app.include_router(health_router, prefix=settings.API_V1_STR)


@app.get(
    "/",
    response_class=JSONResponse,
    tags=["Root"],
    summary="API Root Redirect Entrypoint"
)
async def api_root() -> JSONResponse:
    return JSONResponse(
        content={
            "project": settings.PROJECT_NAME,
            "version": "1.0.0",
            "documentation": "/docs",
            "health_check": f"{settings.API_V1_STR}/health"
        }
    )
