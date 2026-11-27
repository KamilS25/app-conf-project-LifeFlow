from concurrent.futures import ThreadPoolExecutor

import psycopg
from fastapi.testclient import TestClient

from app.application import create_app
from settings import load_settings


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
        "goal_id": None,
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


def test_production_requires_authentication_and_hides_debug_routes(
    database: str,
) -> None:
    settings = load_settings().model_copy(update={"app_env": "prod"})
    with TestClient(
        create_app(settings),
        base_url="https://testserver",
        headers={"X-LifeFlow-Request": "1"},
    ) as client:
        assert client.get("/tasks").status_code == 401
        assert client.post("/auth/demo").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health").status_code == 200
        response = client.post(
            "/auth/register",
            json={
                "email": "production@example.com",
                "password": "synthetic account password",
            },
        )
        assert response.status_code == 201
        assert "Secure" in response.headers["set-cookie"]
        assert client.post("/tasks", json={"title": "Private task"}).status_code == 201


def test_concurrent_creation_stays_with_signed_in_owner(
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
