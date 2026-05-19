from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict, List
import logging
import traceback

logger = logging.getLogger("finragvault.exceptions")


# Custom Exception Hierarchy
class FinRAGException(Exception):
    """Base exception class for all custom exceptions in FinRAG Vault."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class EntityNotFound(FinRAGException):
    """Exception raised when a requested database entry is missing."""
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class AuthenticationError(FinRAGException):
    """Exception raised when credentials or JWT signatures fail validation."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class PermissionDenied(FinRAGException):
    """Exception raised when an authenticated user lacks RBAC permission clearance."""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class FileValidationError(FinRAGException):
    """Exception raised when an upload fails size, extension, or MIME bounds."""
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


class DatabaseException(FinRAGException):
    """Exception raised for unexpected relational database operational issues."""
    def __init__(self, message: str = "Database transaction error"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VectorDatabaseException(FinRAGException):
    """Exception raised for Qdrant network or read/write failures."""
    def __init__(self, message: str = "Vector database failure"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# FastAPI Global Exception Registration Helpers
def setup_exception_handlers(app: Any) -> None:
    """Attaches standard response wrappers to the FastAPI application instance.
    
    Args:
        app (FastAPI): The main FastAPI application.
    """
    
    @app.exception_handler(FinRAGException)
    async def finrag_exception_handler(request: Request, exc: FinRAGException):
        """Catch-all for our explicit domain exceptions."""
        logger.warning(f"Domain exception on {request.method} {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "data": None
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Catches and handles Pydantic schema validation failures."""
        errors: List[Dict[str, Any]] = []
        for error in exc.errors():
            # Standardize pydantic field paths
            field_path = " -> ".join(str(p) for p in error.get("loc", []))
            errors.append({
                "field": field_path,
                "message": error.get("msg", "Invalid parameter specification")
            })
            
        logger.warning(f"Validation failure on {request.method} {request.url.path}: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": "Schema validation failed",
                "errors": errors
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Failsafe for unhandled server exceptions (HTTP 500)."""
        tb = traceback.format_exc()
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}\nTraceback:\n{tb}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "An unexpected internal server error occurred",
                "data": None if not app.debug else {"detail": str(exc), "trace": tb.split("\n")}
            }
        )
