import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router
from app.config import settings
from app.db import SessionLocal
from app.errors import AppError, error_body
from app.logging_setup import request_id_var, setup_logging
from app.service import mark_stale_imports_failed

setup_logging(settings.log_level)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    mark_stale_imports_failed()
    yield


app = FastAPI(title="Sales Import & Dashboard API", version="1.0.0", lifespan=lifespan)


def _error_response(request: Request, status: int, code: str, message: str, details=None):
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        content=error_body(code, message, request_id, details), status_code=status
    )


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    log.warning("request rejected", extra={"code": exc.code, "path": request.url.path})
    return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()
    ]
    log.warning("request invalid", extra={"code": "VALIDATION_ERROR", "path": request.url.path})
    return _error_response(request, 422, "VALIDATION_ERROR", "Request is not valid", details)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
    code = codes.get(exc.status_code, "HTTP_ERROR")
    return _error_response(request, exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    log.exception("unhandled error", extra={"method": request.method, "path": request.url.path})
    return _error_response(request, 500, "INTERNAL_ERROR", "Something went wrong")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = (request.headers.get("X-Request-ID") or uuid4().hex)[:64]
    request.state.request_id = request_id
    request_id_var.set(request_id)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)

app.include_router(router)


@app.get("/health", tags=["health"])
def health():
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        log.exception("health check failed")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}
