
from typing import Optional


class BaseServiceException(Exception):
    
    def __init__(
        self, 
        message: str, 
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(BaseServiceException):
    
    def __init__(
        self, 
        message: str = "Resource not found",
        error_code: Optional[str] = "NOT_FOUND",
        details: Optional[dict] = None
    ):
        super().__init__(message, status_code=404, error_code=error_code, details=details)


class ValidationError(BaseServiceException):
    
    def __init__(
        self, 
        message: str = "Validation error",
        error_code: Optional[str] = "VALIDATION_ERROR",
        details: Optional[dict] = None
    ):
        super().__init__(message, status_code=400, error_code=error_code, details=details)


class ConflictError(BaseServiceException):
    
    def __init__(
        self, 
        message: str = "Resource conflict",
        error_code: Optional[str] = "CONFLICT",
        details: Optional[dict] = None
    ):
        super().__init__(message, status_code=409, error_code=error_code, details=details)


class UnauthorizedError(BaseServiceException):
    
    def __init__(
        self, 
        message: str = "Unauthorized",
        error_code: Optional[str] = "UNAUTHORIZED",
        details: Optional[dict] = None
    ):
        super().__init__(message, status_code=401, error_code=error_code, details=details)


class ForbiddenError(BaseServiceException):
    
    def __init__(
        self, 
        message: str = "Forbidden",
        error_code: Optional[str] = "FORBIDDEN",
        details: Optional[dict] = None
    ):
        super().__init__(message, status_code=403, error_code=error_code, details=details)


class InternalServerError(BaseServiceException):
    
    def __init__(
        self, 
        message: str = "Internal server error",
        error_code: Optional[str] = "INTERNAL_ERROR",
        details: Optional[dict] = None
    ):
        super().__init__(message, status_code=500, error_code=error_code, details=details)

