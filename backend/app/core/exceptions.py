"""
Custom application exceptions.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base application exception."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        detail: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class DatabaseException(AppException):
    """Database operation failed."""
    pass


class ValidationException(AppException):
    """Validation error."""
    pass


class NotFoundError(AppException):
    """Resource not found."""
    
    def __init__(self, resource: str, resource_id: Any):
        message = f"{resource} not found: {resource_id}"
        super().__init__(message, status_code=404)


class UnauthorizedException(AppException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenException(AppException):
    """Authorization failed."""
    
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)
