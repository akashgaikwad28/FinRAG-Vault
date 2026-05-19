from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response
import time
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger("finragvault.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Telemetry middleware recording execution times, status codes, and request details."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate unique request correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Attach request_id to request state for down-stream logging references
        request.state.request_id = request_id
        
        # Default user_id state to be populated by auth dependencies later
        request.state.user_id = None
        
        start_time = time.time()
        
        try:
            # Process request pipeline
            response = await call_next(request)
            
            # Record execution latency
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Retrieve logged user ID if parsed by auth decorators
            user_id = getattr(request.state, "user_id", None)
            
            # Log successful structured transaction
            logger.info(
                f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                extra={
                    "request_id": request_id,
                    "user_id": str(user_id) if user_id else None,
                    "endpoint": f"{request.method} {request.url.path}",
                    "execution_time": f"{duration_ms}ms",
                    "status_code": response.status_code
                }
            )
            
            # Add correlation header back to response
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as exc:
            # Catch server level execution faults and record traceback telemetry
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"Request crashed: {request.method} {request.url.path} -> 500. Error: {str(exc)}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "user_id": None,
                    "endpoint": f"{request.method} {request.url.path}",
                    "execution_time": f"{duration_ms}ms",
                    "status_code": 500
                }
            )
            raise exc
