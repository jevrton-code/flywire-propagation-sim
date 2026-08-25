"""One error shape for the whole API, HTTP and WebSocket alike.

Every failure the client can cause comes back as::

    {"error": {"code": "unknown_cell_type",
               "message": "unknown cell_type(s) ['EPGx']; available: [...]",
               "details": {...}}}

``code`` is a stable machine-readable string the frontend can branch on;
``message`` is meant to be shown to a human; ``details`` is optional structured
context (e.g. which root_ids were missing).

FastAPI's default body is ``{"detail": ...}``, and its validation errors are a
list of pydantic error dicts. Both are re-wrapped by the handlers below so a
client only ever has to parse one shape. The original pydantic errors are kept
verbatim under ``details.errors`` -- nothing is swallowed.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """An error with an HTTP status, a stable code and a human-readable message.

    Raised by the service layer so that route handlers and the WebSocket
    endpoint can share the same failure vocabulary: the HTTP layer turns it into
    a JSON response, the WebSocket layer into an ``{"type": "error"}`` message.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return {"error": body}


def not_found(code: str, message: str, **details: Any) -> ApiError:
    return ApiError(code, message, status_code=status.HTTP_404_NOT_FOUND, details=details)


#: 422 is spelled as a literal because the constant for it was renamed
#: (UNPROCESSABLE_ENTITY -> UNPROCESSABLE_CONTENT) between Starlette versions.
HTTP_422 = 422


def invalid_request(code: str, message: str, **details: Any) -> ApiError:
    return ApiError(code, message, status_code=HTTP_422, details=details)


def server_busy(code: str, message: str, **details: Any) -> ApiError:
    return ApiError(
        code, message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details
    )


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #


async def _api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Re-wrap the framework's own 404/405/... into the same envelope."""
    code = {
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    }.get(exc.status_code, "http_error")
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiError(code, str(exc.detail), status_code=exc.status_code).to_payload(),
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    location = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = first.get("msg", "request payload failed validation")
    if location:
        message = f"{location}: {message}"
    return JSONResponse(
        status_code=HTTP_422,
        content=ApiError(
            "invalid_request",
            message,
            status_code=HTTP_422,
            # jsonable via FastAPI's own encoder: pydantic errors can carry
            # non-JSON values in "ctx", so stringify defensively.
            details={"errors": [_jsonable_error(e) for e in errors]},
        ).to_payload(),
    )


def _jsonable_error(error: dict[str, Any]) -> dict[str, Any]:
    out = {
        "location": [str(p) for p in error.get("loc", ())],
        "message": error.get("msg"),
        "type": error.get("type"),
    }
    if "input" in error:
        out["input"] = repr(error["input"])
    return out


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
