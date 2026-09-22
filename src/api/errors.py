"""Stable problem-detail errors for the research API.

Responses expose only stable codes and operational IDs — never exception
text, bodies, credentials, evidence, or raw paths.
"""

from __future__ import annotations

from typing import Final

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

PROBLEM_TYPE_BASE: Final[str] = "urn:palimpsest:problem"
API_ERROR_HEADER: Final[str] = "x-palimpsest-error-code"


class ProblemDetail(BaseModel):
    """RFC 7807-shaped problem document with a stable machine code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(description="URN problem type")
    title: str
    status: int = Field(ge=400, le=599)
    code: str = Field(min_length=1, max_length=128)
    detail: str = Field(min_length=1, max_length=256)
    request_id: str | None = Field(default=None, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)


class ApiError(Exception):
    """API failure carrying a stable problem detail."""

    def __init__(
        self,
        *,
        code: str,
        status: int,
        title: str,
        detail: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.code = code
        self.status = status
        self.title = title
        self.detail = detail if detail is not None else code
        self.run_id = run_id
        super().__init__(code)

    def to_problem(self, *, request_id: str | None = None) -> ProblemDetail:
        return ProblemDetail(
            type=f"{PROBLEM_TYPE_BASE}:{self.code}",
            title=self.title,
            status=self.status,
            code=self.code,
            detail=self.detail,
            request_id=request_id,
            run_id=self.run_id,
        )


def unauthorized(*, code: str = "unauthorized") -> ApiError:
    return ApiError(code=code, status=401, title="Unauthorized")


def forbidden(*, code: str = "forbidden") -> ApiError:
    return ApiError(code=code, status=403, title="Forbidden")


def not_found(*, code: str = "not_found", run_id: str | None = None) -> ApiError:
    return ApiError(code=code, status=404, title="Not Found", run_id=run_id)


def conflict(*, code: str, run_id: str | None = None) -> ApiError:
    return ApiError(code=code, status=409, title="Conflict", run_id=run_id)


def bad_request(*, code: str, run_id: str | None = None) -> ApiError:
    return ApiError(code=code, status=400, title="Bad Request", run_id=run_id)


def gone(*, code: str = "unavailable", run_id: str | None = None) -> ApiError:
    return ApiError(code=code, status=410, title="Gone", run_id=run_id)


def unprocessable(*, code: str, run_id: str | None = None) -> ApiError:
    return ApiError(code=code, status=422, title="Unprocessable Entity", run_id=run_id)


def service_unavailable(*, code: str = "draining") -> ApiError:
    return ApiError(code=code, status=503, title="Service Unavailable")


def internal(*, code: str = "internal_error") -> ApiError:
    return ApiError(code=code, status=500, title="Internal Error")


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, str):
        request_id = None
    problem = exc.to_problem(request_id=request_id)
    return JSONResponse(
        status_code=exc.status,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
        headers={API_ERROR_HEADER: exc.code},
    )
