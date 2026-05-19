from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi import Request, Response
from jose import jwt, JWTError
from app.core.config import settings
import logging

logger = logging.getLogger("finragvault.middleware.auth")


class AuthMiddleware(BaseHTTPMiddleware):
    """Correlation middleware parsing security context to supply user ID telemetry to system logs."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        authorization: str = request.headers.get("Authorization", "")
        
        # Initialize default user state
        request.state.user_id = None
        
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            try:
                # Attempt to extract subject claims without blocking route execution
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
                if user_id:
                    request.state.user_id = user_id
            except JWTError:
                # Ignore JWT decodes here (route level guards will reject credentials explicitly)
                pass
                
        return await call_next(request)
