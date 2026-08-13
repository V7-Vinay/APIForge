from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class APIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | list | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class ResourceNotFoundError(APIError):
    def __init__(self, message: str = "Resource not found.", details: dict | list | None = None):
        super().__init__(code="NOT_FOUND", message=message, status_code=404, details=details)


class ForbiddenError(APIError):
    def __init__(self, message: str = "You do not have permission to perform this action.", details: dict | list | None = None):
        super().__init__(code="FORBIDDEN", message=message, status_code=403, details=details)


class ConflictError(APIError):
    def __init__(self, message: str = "Resource conflict.", details: dict | list | None = None):
        super().__init__(code="CONFLICT", message=message, status_code=409, details=details)


class ExecutionError(APIError):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | list | None = None):
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class SecurityViolationError(APIError):
    def __init__(self, code: str, message: str, status_code: int = 403, details: dict | list | None = None):
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Authentication required.", details: dict | list | None = None):
        super().__init__(code="UNAUTHORIZED", message=message, status_code=401, details=details)


class ValidationError(APIError):
    def __init__(self, message: str = "Validation failed.", details: dict | list | None = None):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=400, details=details)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            },
            "detail": exc.message
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    status_code = exc.status_code
    if status_code == 401:
        code = "UNAUTHORIZED"
    elif status_code == 403:
        code = "FORBIDDEN"
    elif status_code == 404:
        code = "NOT_FOUND"
    elif status_code == 409:
        code = "CONFLICT"
    elif status_code == 422:
        code = "VALIDATION_ERROR"
    else:
        code = "BAD_REQUEST" if status_code < 500 else "INTERNAL_SERVER_ERROR"

    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail,
                "details": None
            },
            "detail": exc.detail
        },
        headers=headers
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed.",
                "details": exc.errors()
            },
            "detail": exc.errors()
        }
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logger = logging.getLogger("app")
    logger.exception("Unhandled error occurred")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": None
            },
            "detail": "An unexpected error occurred."
        }
    )
