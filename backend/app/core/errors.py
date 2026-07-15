"""
Centralized exception definitions for the application.

All application-specific exceptions should be defined here.
This ensures consistent error handling and logging.
"""

from typing import Any, Dict


class AppError(Exception):
    """Base class for all application errors"""
    def __init__(self, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


# Authentication Errors
class UnauthorizedError(AppError):
    """Authentication required"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class InvalidTokenError(AppError):
    """Invalid JWT token"""
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message, status_code=403)


class TokenExpiredError(AppError):
    """Token has expired"""
    def __init__(self, message: str = "Token has expired"):
        super().__init__(message, status_code=403)


# Resource Errors
class NotFoundError(AppError):
    """Resource not found"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found",
            status_code=404,
            details={"resource": resource, "identifier": identifier}
        )


class AlreadyExistsError(AppError):
    """Resource already exists"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} already exists",
            status_code=409,
            details={"resource": resource, "identifier": identifier}
        )


# Permission Errors
class ForbiddenError(AppError):
    """Permission denied"""
    def __init__(self, resource: str = "operation", action: str = None):
        message ="Permission denied"
        if action:
            message += f" to {action} on {resource}"
        super().__init__(message, status_code=403, details={"resource": resource, "action": action})


# Validation Errors
class ValidationError(AppError):
    """Data validation error"""
    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Invalid {field}: {message}",
            status_code=422,
            details={"field": field, "message": message}
        )


class MultipleValidationError(AppError):
    """Multiple validation errors"""
    def __init__(self, errors: list):
        super().__init__(
            message="Validation failed",
            status_code=422,
            details={"errors": errors}
        )
