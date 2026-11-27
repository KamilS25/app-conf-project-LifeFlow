import logging
import tomllib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router
from app.dashboard import router as dashboard_router
from app.database import create_database_engine
from app.demo import router as demo_router
from app.finance import router as finance_router
from app.goals import router as goals_router
from app.rates import RateFeed
from app.security import AuthAttemptLimit
from app.task_schemas import TaskValidationIssue, TaskValidationResponse
from app.tasks import router as tasks_router
from settings import Settings

TEAM_NAME = "LifeFlow"
logger = logging.getLogger(__name__)


def create_app(settings: Settings) -> FastAPI:
    project_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with project_path.open("rb") as project_file:
        version_number = tomllib.load(project_file)["project"]["version"]

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(settings)
        application.state.database_engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="LifeFlow",
        description="LifeFlow application",
        version=version_number,
        openapi_url=None if settings.app_env == "prod" else "/openapi.json",
        lifespan=lifespan,
        responses={
            400: {"model": TaskValidationResponse, "description": "Invalid request"}
        },
    )
    app.state.secure_cookies = settings.app_env == "prod"
    app.state.rate_feed = RateFeed()
    app.state.auth_attempts = AuthAttemptLimit()
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
    app.include_router(auth_router)
    app.include_router(tasks_router)
    app.include_router(goals_router)
    app.include_router(finance_router)
    app.include_router(dashboard_router)
    if settings.app_env == "dev":
        app.include_router(demo_router)

    static_path = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/app", include_in_schema=False)
    def workspace() -> FileResponse:
        return FileResponse(
            static_path / "index.html",
            headers={
                "Content-Security-Policy": "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            },
        )

    @app.get("/app/config", include_in_schema=False)
    def workspace_config() -> dict[str, bool]:
        return {"demo_available": settings.app_env == "dev"}

    @app.middleware("http")
    async def response_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith(
            ("/auth", "/tasks", "/goals", "/finance", "/dashboard")
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    async def root(request: Request):
        """Root endpoint."""
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse("/app", headers={"Vary": "Accept"})
        return JSONResponse({"message": "Hello World"}, headers={"Vary": "Accept"})

    @app.get("/health", responses={503: {"description": "PostgreSQL check failed"}})
    def health_check():
        """Check application and PostgreSQL availability."""
        try:
            with psycopg.connect(
                settings.database_conninfo(),
                connect_timeout=settings.db_connect_timeout,
            ) as connection:
                connection.execute("SELECT 1")
        except psycopg.Error:
            raise HTTPException(status_code=503, detail="Service unavailable") from None

        return {"status": "healthy", "database": "ok"}

    @app.get("/version")
    async def version():
        """Версия приложения и команда-владелец."""
        return {"version": app.version, "team": TEAM_NAME}

    return app


async def handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = TaskValidationResponse(
        detail=[
            TaskValidationIssue(
                loc=list(error["loc"]), msg=error["msg"], type=error["type"]
            )
            for error in exc.errors()
        ]
    )
    return JSONResponse(status_code=400, content=errors.model_dump(mode="json"))


async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled request error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "Не удалось обработать запрос"},
        headers={"Cache-Control": "no-store"},
    )
