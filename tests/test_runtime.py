import os
import runpy
import tomllib
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.application import create_app
from settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNREACHABLE_DATABASE = "postgresql://127.0.0.1:1/lifeflow"


@pytest.fixture
def test_db_url() -> str:
    url = os.environ.get("LIFEFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LIFEFLOW_TEST_DATABASE_URL to a PostgreSQL test database")
    return url


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DATABASE)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "2")
    return monkeypatch


def test_root_serves_json(settings_env: pytest.MonkeyPatch) -> None:
    with TestClient(create_app(load_settings())) as client:
        response = client.get("/", headers={"Accept": "application/json"})

    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_version_matches_project_metadata(settings_env: pytest.MonkeyPatch) -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        version = tomllib.load(project_file)["project"]["version"]

    with TestClient(create_app(load_settings())) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": version, "team": "LifeFlow"}


def test_health_checks_running_postgres(
    settings_env: pytest.MonkeyPatch, test_db_url: str
) -> None:
    settings_env.setenv("DATABASE_URL", test_db_url)
    with TestClient(create_app(load_settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


def test_health_returns_503_when_postgres_is_unreachable(
    settings_env: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app(load_settings())) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}


@pytest.mark.parametrize(("environment", "status"), [("dev", 200), ("prod", 404)])
def test_docs_availability_depends_on_environment(
    settings_env: pytest.MonkeyPatch, environment: str, status: int
) -> None:
    settings_env.setenv("APP_ENV", environment)
    with TestClient(create_app(load_settings())) as client:
        assert client.get("/docs").status_code == status


def test_application_refuses_to_start_without_database_url(
    settings_env: pytest.MonkeyPatch,
) -> None:
    settings_env.delenv("DATABASE_URL")
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        runpy.run_module("main")


def test_application_refuses_to_start_with_invalid_environment(
    settings_env: pytest.MonkeyPatch,
) -> None:
    settings_env.setenv("APP_ENV", "invalid")
    with pytest.raises(SystemExit, match="APP_ENV"):
        runpy.run_module("main")


def test_alembic_upgrades_a_clean_schema_and_can_repeat(
    settings_env: pytest.MonkeyPatch, test_db_url: str
) -> None:
    schema = sql.Identifier(f"lifeflow_test_{uuid4().hex}")
    conninfo = make_conninfo(
        test_db_url, options=f"-c search_path={schema.as_string()}"
    )
    settings_env.setenv("DATABASE_URL", conninfo)
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None

    with psycopg.connect(test_db_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        try:
            command.upgrade(config, "head")
            command.upgrade(config, "head")

            with psycopg.connect(conninfo) as connection:
                assert connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone() == (head,)
                assert connection.execute("SELECT count(*) FROM tasks").fetchone() == (
                    0,
                )
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))
