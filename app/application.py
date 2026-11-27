import tomllib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import create_database_engine
from app.task_schemas import TaskValidationIssue, TaskValidationResponse
from app.tasks import router as tasks_router
from settings import Settings

TEAM_NAME = "LifeFlow"


def create_app(settings: Settings) -> FastAPI:
    project_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with project_path.open("rb") as project_file:
        version_number = tomllib.load(project_file)["project"]["version"]

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if settings.app_env == "prod":
            yield
            return

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
    )

    if settings.app_env == "dev":
        app.add_exception_handler(RequestValidationError, handle_validation_error)
        app.include_router(tasks_router)

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "Hello World"}

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
