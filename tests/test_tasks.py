import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
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
def database(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
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
            config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
            command.upgrade(Config(str(config_path)), "head")
            yield conninfo
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


@pytest.fixture
def client(database: str) -> Iterator[TestClient]:
    with TestClient(create_app(load_settings())) as test_client:
        yield test_client


def test_task_lifecycle(client: TestClient) -> None:
    assert client.get("/tasks").json() == []

    response = client.post(
        "/tasks",
        json={
            "title": "  Plan the demo  ",
            "description": "Draft",
            "due_date": "2026-12-01",
        },
    )
    assert response.status_code == 201
    task = response.json()
    assert task["title"] == "Plan the demo"
    assert task["status"] == "todo"
    assert task["due_date"] == "2026-12-01"
    path = f"/tasks/{task['id']}"
    assert client.get(path).json() == task

    response = client.put(path, json={"title": "Run the demo", "status": "done"})
    assert response.status_code == 200
    assert response.json() == {
        "id": task["id"],
        "title": "Run the demo",
        "description": None,
        "status": "done",
        "due_date": None,
    }
    assert client.get(path).json() == response.json()

    response = client.delete(path)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path).status_code == 404
    assert client.delete(path).status_code == 404
    assert client.get("/tasks").json() == []


def test_default_page_size_and_pagination(client: TestClient) -> None:
    task_ids = []
    for number in range(22):
        response = client.post("/tasks", json={"title": f"Task {number}"})
        assert response.status_code == 201
        task_ids.append(response.json()["id"])

    first_page = client.get("/tasks").json()
    second_page = client.get("/tasks", params={"offset": 20, "limit": 2}).json()
    assert [task["id"] for task in first_page] == task_ids[:20]
    assert [task["id"] for task in second_page] == task_ids[20:]


def test_other_owners_tasks_are_private(client: TestClient, database: str) -> None:
    with psycopg.connect(database) as connection:
        owner = connection.execute(
            "INSERT INTO users (email) VALUES (%s) RETURNING id",
            ("other@example.test",),
        ).fetchone()
        assert owner is not None
        task = connection.execute(
            "INSERT INTO tasks (owner_id, title) VALUES (%s, %s) RETURNING id",
            (owner[0], "Private task"),
        ).fetchone()
        assert task is not None

    response = client.post("/tasks", json={"title": "Demo task"})
    assert response.status_code == 201
    assert client.get("/tasks").json() == [response.json()]
    path = f"/tasks/{task[0]}"
    assert client.get(path).status_code == 404
    assert (
        client.put(path, json={"title": "Changed", "status": "done"}).status_code == 404
    )
    assert client.delete(path).status_code == 404

    with psycopg.connect(database) as connection:
        assert connection.execute(
            "SELECT title, status FROM tasks WHERE id = %s", (task[0],)
        ).fetchone() == ("Private task", "todo")


def test_invalid_requests_return_400(client: TestClient) -> None:
    for payload in (
        {"title": "   "},
        {"title": "a" * 201},
        {"title": "Task", "status": "unknown"},
        {"title": "Task", "due_date": "not-a-date"},
        {"title": "Task", "owner_id": 123},
        {"title": "Task\x00name"},
        {"title": "Task", "description": "Bad\x00description"},
    ):
        response = client.post("/tasks", json=payload)
        assert response.status_code == 400
        assert {"loc", "msg", "type"} == set(response.json()["detail"][0])

    assert client.get("/tasks?limit=101").status_code == 400
    assert client.get("/tasks?offset=-1").status_code == 400
    assert client.get("/tasks/2147483648").status_code == 400
    assert client.put("/tasks/1", json={"title": "Missing status"}).status_code == 400
    assert client.get("/tasks").json() == []


def test_openapi_documents_task_responses(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    creation = schema["paths"]["/tasks"]["post"]["responses"]
    removal = schema["paths"]["/tasks/{task_id}"]["delete"]["responses"]
    assert "201" in creation
    assert "400" in creation
    assert "422" not in creation
    assert "204" in removal
    assert "404" in removal


def test_task_routes_are_only_available_in_development(database: str) -> None:
    settings = load_settings().model_copy(update={"app_env": "prod"})
    with TestClient(create_app(settings)) as client:
        assert client.get("/tasks").status_code == 404
        assert client.post("/tasks", json={"title": "Hidden"}).status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health").status_code == 200


def test_concurrent_creation_reuses_one_demo_owner(
    client: TestClient, database: str
) -> None:
    def create_task(number: int) -> int:
        return client.post(
            "/tasks", json={"title": f"Concurrent task {number}"}
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(create_task, range(4))) == [201, 201, 201, 201]

    with psycopg.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM tasks").fetchone() == (4,)
