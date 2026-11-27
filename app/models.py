from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    CNY = "CNY"


class TransactionKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(128))


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_goals_id_owner"),
        Index("ix_goals_owner_id_id", "owner_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None]


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status"
        ),
        Index("ix_tasks_owner_id_id", "owner_id", "id"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goals.id", "goals.owner_id"],
            name="fk_tasks_goal_owner",
        ),
        Index("ix_tasks_goal_id", "goal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    goal_id: Mapped[int | None]
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(11), server_default=TaskStatus.TODO.value
    )
    due_date: Mapped[date | None]


class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"
    __table_args__ = (
        CheckConstraint("kind IN ('income', 'expense')", name="ck_finance_kind"),
        CheckConstraint(
            "currency IN ('RUB', 'USD', 'EUR', 'CNY')", name="ck_finance_currency"
        ),
        CheckConstraint("amount > 0", name="ck_finance_amount_positive"),
        Index("ix_finance_owner_date_id", "owner_id", "occurred_on", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(7))
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    category: Mapped[str] = mapped_column(String(80))
    occurred_on: Mapped[date]
    comment: Mapped[str | None] = mapped_column(Text)
