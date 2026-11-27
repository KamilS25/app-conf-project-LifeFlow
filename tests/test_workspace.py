from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.application import create_app
from app.models import Currency
from app.rates import (
    DAILY_RATES_URL,
    MIRROR_RATES_URL,
    RateFeed,
    RatesUnavailable,
    fetch_daily_rates,
    parse_daily_rates,
)
from app.security import SESSION_COOKIE
from settings import load_settings

SAMPLE_RATES = b"""<ValCurs Date="27.11.2026">
  <Valute><CharCode>USD</CharCode><Nominal>1</Nominal><Value>81,12</Value></Valute>
  <Valute><CharCode>EUR</CharCode><Nominal>1</Nominal><Value>92,80</Value></Valute>
  <Valute><CharCode>CNY</CharCode><Nominal>10</Nominal><Value>119,32</Value></Valute>
</ValCurs>"""


def test_account_session_and_csrf(guest: TestClient, database: str) -> None:
    assert guest.get("/tasks").status_code == 401
    assert guest.get("/goals").status_code == 401
    assert guest.get("/finance/summary").status_code == 401
    assert guest.get("/dashboard").status_code == 401
    credentials = {
        "email": "  Reader@Example.com  ",
        "password": "synthetic account password",
    }
    response = guest.post("/auth/register", json=credentials)
    assert response.status_code == 201
    assert response.json() == {"email": "reader@example.com", "demo": False}
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    with psycopg.connect(database) as connection:
        row = connection.execute("SELECT password_hash FROM users").fetchone()
        assert row is not None and row[0] and row[0] != credentials["password"]

    assert guest.post("/auth/register", json=credentials).status_code == 409
    assert (
        guest.post(
            "/tasks",
            json={"title": "No CSRF header"},
            headers={"X-LifeFlow-Request": ""},
        ).status_code
        == 403
    )
    old_cookie = guest.cookies[SESSION_COOKIE]
    assert guest.post("/auth/logout").status_code == 204
    assert (
        guest.get(
            "/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={old_cookie}"}
        ).status_code
        == 401
    )
    assert (
        guest.post("/auth/login", json=credentials | {"password": "wrong"}).status_code
        == 401
    )
    assert guest.post("/auth/login", json=credentials).status_code == 200
    with psycopg.connect(database) as connection:
        connection.execute(
            "UPDATE login_sessions SET expires_at = NOW() - interval '1 minute'"
        )
    assert guest.get("/auth/me").status_code == 401


def test_goal_progress_and_last_task(client: TestClient) -> None:
    task_ids = [
        client.post("/tasks", json={"title": title}).json()["id"]
        for title in ("First", "Second")
    ]
    assert (
        client.post("/goals", json={"title": "Empty", "task_ids": []}).status_code
        == 400
    )
    response = client.post("/goals", json={"title": "My goal", "task_ids": task_ids})
    assert response.status_code == 201, response.text
    goal_path = f"/goals/{response.json()['id']}"
    assert (
        client.post("/goals", json={"title": "Other", "task_ids": task_ids}).status_code
        == 409
    )
    task_path = f"/tasks/{task_ids[0]}"
    assert (
        client.patch(task_path + "/status", json={"status": "done"}).status_code == 200
    )
    result = client.get(goal_path).json()
    assert (result["progress"], result["completed_tasks"]) == (50, 1)
    assert (
        client.put(
            goal_path, json={"title": "Edited", "task_ids": task_ids[:1]}
        ).status_code
        == 200
    )
    assert client.get(goal_path).json()["progress"] == 100
    assert client.delete(task_path).status_code == 409
    assert client.delete(goal_path).status_code == 204
    assert client.get(task_path).json()["goal_id"] is None
    assert client.delete(task_path).status_code == 204


def test_separate_currency_totals_and_private_workspaces(
    client: TestClient, database: str
) -> None:
    day = date.today()
    first = {
        "kind": "income",
        "amount": "10.10",
        "category": " Side job ",
        "occurred_on": day.isoformat(),
    }
    liability = first | {"currency": "USD", "amount": "2.01", "kind": "expense"}
    assert (
        client.post(
            "/finance/transactions", json=first | {"currency": "GBP"}
        ).status_code
        == 400
    )
    response = client.post("/finance/transactions", json=first | {"currency": "USD"})
    assert response.status_code == 201
    assert response.json()["category"] == "Side job"
    assert client.post("/finance/transactions", json=liability).status_code == 201
    assert (
        client.post(
            "/finance/transactions", json=first | {"currency": "CNY"}
        ).status_code
        == 201
    )
    previous = first | {
        "currency": "USD",
        "occurred_on": (day - timedelta(days=1)).isoformat(),
    }
    assert client.post("/finance/transactions", json=previous).status_code == 201
    totals = client.get(
        "/finance/summary", params={"start": day.isoformat(), "end": day.isoformat()}
    )
    assert totals.status_code == 200
    by_currency = {row["currency"]: row for row in totals.json()}
    assert by_currency["USD"] == {
        "currency": "USD",
        "income": "10.10",
        "expense": "2.01",
        "net": "8.09",
        "balance": "18.19",
    }
    assert by_currency["CNY"]["balance"] == "10.10"
    assert by_currency["RUB"]["balance"] == "0.00"
    transaction_path = f"/finance/transactions/{response.json()['id']}"
    task_id = client.post("/tasks", json={"title": "Private"}).json()["id"]
    goal_id = client.post(
        "/goals", json={"title": "Private", "task_ids": [task_id]}
    ).json()["id"]

    with TestClient(
        create_app(load_settings()), headers={"X-LifeFlow-Request": "1"}
    ) as other:
        assert (
            other.post(
                "/auth/register",
                json={
                    "email": "other@example.com",
                    "password": "another synthetic password",
                },
            ).status_code
            == 201
        )
        assert other.get("/goals").json() == []
        assert other.get(f"/goals/{goal_id}").status_code == 404
        assert (
            other.post(
                "/goals", json={"title": "Private", "task_ids": [task_id]}
            ).status_code
            == 404
        )
        assert other.get("/finance/transactions").json() == []
        assert other.get(transaction_path).status_code == 404
        assert other.put(transaction_path, json=liability).status_code == 404
        assert other.delete(transaction_path).status_code == 404
        assert other.get("/dashboard").json()["goal_count"] == 0

    assert client.put(transaction_path, json=liability).status_code == 200
    assert client.delete(transaction_path).status_code == 204


def test_demo_isolated(client: TestClient, database: str) -> None:
    assert client.get("/dashboard").json()["goal_count"] == 0
    with TestClient(
        create_app(load_settings()), headers={"X-LifeFlow-Request": "1"}
    ) as demo:
        assert demo.post("/auth/demo").status_code == 201
        assert demo.get("/auth/me").json() == {"email": None, "demo": True}
        assert demo.get("/dashboard").json()["goal_count"] == 2
        assert len(demo.get("/tasks").json()) == 10
        assert len(demo.get("/finance/transactions").json()) == 9
    assert client.get("/tasks").json() == []


def test_existing_demo_data_survives_upgrade(
    isolated_schema: str, migrations: Config
) -> None:
    command.upgrade(migrations, "0001")
    with psycopg.connect(isolated_schema) as connection:
        connection.execute(
            "INSERT INTO users (id, email) VALUES (100, 'demo@lifeflow.invalid')"
        )
        connection.execute(
            "INSERT INTO tasks (owner_id, title) VALUES (100, 'Existing task')"
        )
    command.upgrade(migrations, "head")
    with psycopg.connect(isolated_schema) as connection:
        assert connection.execute("SELECT title, goal_id FROM tasks").fetchone() == (
            "Existing task",
            None,
        )


def test_rates_nominal_cache_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = parse_daily_rates(SAMPLE_RATES)
    assert snapshot.rub_per_unit[Currency.CNY] == Decimal("11.932")

    def unavailable():
        raise RatesUnavailable

    feed = RateFeed(lambda: snapshot)
    assert feed.read() == snapshot
    feed.load = unavailable
    assert feed.read() == snapshot
    monkeypatch.setattr("app.rates.monotonic", lambda: feed.retry_at + 1)
    assert feed.read().stale
    with pytest.raises(RatesUnavailable):
        RateFeed(unavailable).read()


def test_rates_fall_back_to_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    requested = []

    class Opener:
        def open(self, url: str, timeout: int) -> BytesIO:
            requested.append(url)
            if url == DAILY_RATES_URL:
                raise OSError("Primary feed unavailable")
            return BytesIO(SAMPLE_RATES)

    monkeypatch.setattr("app.rates.build_opener", lambda *_handlers: Opener())
    snapshot = fetch_daily_rates()
    assert snapshot.provider == "mirror"
    assert snapshot.rub_per_unit[Currency.CNY] == Decimal("11.932")
    assert requested == [DAILY_RATES_URL, MIRROR_RATES_URL]
