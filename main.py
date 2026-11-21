import tomllib
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException

from settings import load_settings

settings = load_settings()
with Path(__file__).with_name("pyproject.toml").open("rb") as project_file:
    version_number = tomllib.load(project_file)["project"]["version"]

app = FastAPI(
    title="LifeFlow",
    description="LifeFlow application",
    version=version_number,
    openapi_url=None if settings.app_env == "prod" else "/openapi.json",
)
TEAM_NAME = "LifeFlow"


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hello World"}


@app.get("/health", responses={503: {"description": "PostgreSQL check failed"}})
def health_check():
    """Check application and PostgreSQL availability."""
    try:
        with psycopg.connect(
            settings.database_conninfo(), connect_timeout=settings.db_connect_timeout
        ) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Service unavailable") from None

    return {"status": "healthy", "database": "ok"}


@app.get("/version")
async def version():
    """Версия приложения и команда-владелец."""
    return {"version": app.version, "team": TEAM_NAME}
