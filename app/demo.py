from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response, status

from app.auth import Account
from app.models import (
    Currency,
    FinanceTransaction,
    Goal,
    Task,
    TaskStatus,
    TransactionKind,
    User,
)
from app.security import (
    DatabaseSession,
    SessionToken,
    limit_auth_attempts,
    require_request_header,
    start_session,
)

router = APIRouter(
    prefix="/auth", tags=["Accounts"], dependencies=[Depends(require_request_header)]
)


@router.post(
    "/demo",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_auth_attempts)],
)
def start_demo(
    request: Request, response: Response, db: DatabaseSession, token: SessionToken
) -> Account:
    """Give this browser a separate workspace with synthetic example records."""
    today = date.today()
    user = User(email=f"demo+{uuid4().hex}@lifeflow.invalid")
    db.add(user)
    db.flush()
    travel = Goal(
        owner_id=user.id,
        title="Спланировать поездку",
        due_date=today + timedelta(days=16),
        description="Подготовить маршрут, бюджет и всё необходимое для поездки.",
    )
    routine = Goal(
        owner_id=user.id,
        title="Наладить утреннюю рутину",
        due_date=today + timedelta(days=9),
        description="Проверить, что помогает начинать день без спешки.",
    )
    db.add_all([travel, routine])
    db.flush()

    sample_tasks = (
        ("Составить маршрут на выходные", TaskStatus.IN_PROGRESS, 2, travel.id),
        ("Сравнить варианты жилья", TaskStatus.DONE, -1, travel.id),
        ("Собрать список вещей", TaskStatus.TODO, 7, travel.id),
        ("Выбрать маршрут для прогулки", TaskStatus.DONE, -3, routine.id),
        (
            "Запланировать три короткие тренировки",
            TaskStatus.IN_PROGRESS,
            3,
            routine.id,
        ),
        ("Записать время подъёма всю неделю", TaskStatus.DONE, -2, routine.id),
        ("Разобрать документы", TaskStatus.TODO, 4, None),
        ("Записаться к стоматологу", TaskStatus.TODO, 5, None),
        ("Пропылесосить квартиру", TaskStatus.TODO, 1, None),
        ("Обновить домашний бюджет", TaskStatus.IN_PROGRESS, 2, None),
    )
    db.add_all(
        [
            Task(
                owner_id=user.id,
                title=title,
                status=task_status.value,
                due_date=today + timedelta(days=days),
                goal_id=goal_id,
            )
            for title, task_status, days, goal_id in sample_tasks
        ]
    )

    sample_transactions = (
        (TransactionKind.INCOME, Currency.RUB, "125000.00", "Зарплата", 3, None),
        (
            TransactionKind.EXPENSE,
            Currency.RUB,
            "28500.00",
            "Жильё",
            6,
            "Аренда квартиры",
        ),
        (TransactionKind.EXPENSE, Currency.RUB, "4680.40", "Продукты", 12, None),
        (
            TransactionKind.EXPENSE,
            Currency.RUB,
            "34500.00",
            "Обмен валюты",
            17,
            "Покупка долларов",
        ),
        (
            TransactionKind.INCOME,
            Currency.USD,
            "400.00",
            "Обмен валюты",
            17,
            "Отложено на поездку",
        ),
        (
            TransactionKind.EXPENSE,
            Currency.RUB,
            "11000.00",
            "Обмен валюты",
            21,
            "Покупка юаней",
        ),
        (
            TransactionKind.INCOME,
            Currency.CNY,
            "950.00",
            "Обмен валюты",
            21,
            "Валютный резерв",
        ),
        (TransactionKind.INCOME, Currency.EUR, "250.00", "Подработка", 24, None),
        (
            TransactionKind.EXPENSE,
            Currency.EUR,
            "35.00",
            "Путешествия",
            25,
            "Билет на поезд",
        ),
    )
    db.add_all(
        [
            FinanceTransaction(
                owner_id=user.id,
                kind=kind.value,
                currency=currency.value,
                amount=Decimal(amount),
                category=category,
                occurred_on=today.replace(day=min(today.day, day)),
                comment=comment,
            )
            for kind, currency, amount, category, day, comment in sample_transactions
        ]
    )
    start_session(db, user.id, token, response, secure=request.app.state.secure_cookies)
    return Account(email=None, demo=True)
