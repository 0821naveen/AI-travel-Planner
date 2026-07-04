from __future__ import annotations

import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from src.api.main import router as api_router
from src.bootstrap import create_container
from src.core.config import Settings, get_settings
from src.core.logging import configure_logging, get_logger
from src.core.request_context import RequestContext, reset_request_context, set_request_context
from src.core.security import build_rate_limiter, extract_actor, resolve_client_key, validate_api_key


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    logger = get_logger("travel_planner.api")
    rate_limiter = build_rate_limiter(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = create_container(resolved_settings)
        container.assert_startup_ready()
        app.state.container = container
        yield
        container.shutdown()

    app = FastAPI(title=resolved_settings.app.name, version=resolved_settings.app.version, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.rate_limiter = rate_limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=resolved_settings.api.cors_allow_methods,
        allow_headers=resolved_settings.api.cors_allow_headers,
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        actor = extract_actor(request, resolved_settings)
        started = time.perf_counter()
        request.state.request_id = request_id
        request.state.actor_id = actor.actor_id
        request.state.actor_role = actor.role.value
        token = set_request_context(
            RequestContext(
                request_id=request_id,
                actor_id=actor.actor_id,
                actor_role=actor.role.value,
            )
        )
        logger.info(
            "request.started",
            extra={
                "request_id": request_id,
                "actor_id": actor.actor_id,
                "actor_role": actor.role.value,
                "method": request.method,
                "path": request.url.path,
            },
        )
        try:
            validate_api_key(request, resolved_settings)
            rate_limiter.check(resolve_client_key(request, resolved_settings))
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "same-origin"
        except HTTPException as exc:
            logger.warning(
                "request.rejected",
                extra={
                    "request_id": request_id,
                    "actor_id": actor.actor_id,
                    "actor_role": actor.role.value,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": exc.status_code,
                },
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={"X-Request-ID": request_id},
            )
        except Exception:
            logger.exception(
                "request.failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        finally:
            reset_request_context(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "actor_id": actor.actor_id,
                "actor_role": actor.role.value,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    app.include_router(api_router)
    return app


app = create_app()
