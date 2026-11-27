import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.application import create_app
from settings import load_settings


@pytest.fixture
def isolated_schema(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    test_url = os.environ.get("LIFEFLOW_TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("Set LIFEFLOW_TEST_DATABASE_URL to a PostgreSQL test database")

    schema = f"lifeflow_test_{uuid4().hex}"
    conninfo = make_conninfo(test_url, options=f"-c search_path={schema}")
    with psycopg.connect(test_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            monkeypatch.setenv("DATABASE_URL", conninfo)
            monkeypatch.setenv("APP_ENV", "dev")
            yield conninfo
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


@pytest.fixture
def migrations() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture
def database(isolated_schema: str, migrations: Config) -> str:
    command.upgrade(migrations, "head")
    return isolated_schema


@pytest.fixture
def guest(database: str) -> Iterator[TestClient]:
    with TestClient(
        create_app(load_settings()), headers={"X-LifeFlow-Request": "1"}
    ) as client:
        yield client


@pytest.fixture
def client(guest: TestClient) -> TestClient:
    response = guest.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "password": "synthetic account password",
        },
    )
    assert response.status_code == 201, response.text
    return guest
