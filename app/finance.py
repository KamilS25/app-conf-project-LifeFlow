from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import ColumnElement, case, delete, func, select, update
from sqlalchemy.orm import Session

from app.models import Currency, FinanceTransaction, TransactionKind
from app.rates import RateSnapshot, RatesUnavailable
from app.security import (
    CurrentUser,
    DatabaseSession,
    current_user,
    require_request_header,
)

router = APIRouter(
    prefix="/finance",
    tags=["Finance"],
    dependencies=[Depends(current_user), Depends(require_request_header)],
)
TransactionID = Annotated[int, Path(ge=1, le=2_147_483_647)]
ZERO = Decimal("0.00")


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TransactionKind
    currency: Currency
    amount: Annotated[
        Decimal, Field(gt=0, max_digits=14, decimal_places=2, examples=["125.50"])
    ]
    category: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\x00]*$"
        ),
    ]
    occurred_on: date
    comment: (
        Annotated[str, StringConstraints(max_length=2000, pattern=r"^[^\x00]*$")] | None
    ) = None


class TransactionResponse(TransactionInput):
    model_config = ConfigDict(from_attributes=True)

    id: int


class Period(BaseModel):
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def check_order(self) -> "Period":
        if self.start and self.end and self.start > self.end:
            raise ValueError("Начало периода должно предшествовать его окончанию")
        return self


class TransactionQuery(Period):
    currency: Currency | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0, le=2_147_483_647)] = 0


class CurrencyTotals(BaseModel):
    currency: Currency
    income: Decimal = ZERO
    expense: Decimal = ZERO
    net: Decimal = ZERO
    balance: Decimal = ZERO


def month_to_date() -> Period:
    today = datetime.now().date()
    return Period(start=today.replace(day=1), end=today)


def finance_totals(db: Session, owner_id: int, period: Period) -> list[CurrencyTotals]:
    transaction = FinanceTransaction
    income = transaction.kind == TransactionKind.INCOME
    expense = transaction.kind == TransactionKind.EXPENSE
    date_filters = []
    if period.start is not None:
        date_filters.append(transaction.occurred_on >= period.start)
    if period.end is not None:
        date_filters.append(transaction.occurred_on <= period.end)

    results = db.execute(
        select(
            transaction.currency,
            func.sum(transaction.amount).filter(income, *date_filters),
            func.sum(transaction.amount).filter(expense, *date_filters),
            func.sum(case((income, transaction.amount), else_=-transaction.amount)),
        )
        .where(transaction.owner_id == owner_id)
        .group_by(transaction.currency)
    )
    totals = {currency: CurrencyTotals(currency=currency) for currency in Currency}
    for code, total_income, total_expense, balance in results:
        currency = Currency(code)
        earned, spent = total_income or ZERO, total_expense or ZERO
        totals[currency] = CurrencyTotals(
            currency=currency,
            income=earned,
            expense=spent,
            net=earned - spent,
            balance=balance or ZERO,
        )
    return list(totals.values())


def owned_transaction(owner_id: int, transaction_id: int) -> ColumnElement[bool]:
    return (FinanceTransaction.owner_id == owner_id) & (
        FinanceTransaction.id == transaction_id
    )


@router.get("/summary")
def summarize_finances(
    period: Annotated[Period, Query()], db: DatabaseSession, user: CurrentUser
) -> list[CurrencyTotals]:
    """Report the period totals and the ledger balance independently for each currency."""
    if period.start is None and period.end is None:
        period = month_to_date()
    return finance_totals(db, user.id, period)


@router.get("/rates")
def read_rates(request: Request) -> RateSnapshot:
    """Read official exchange rates without changing any ledger amount."""
    try:
        return request.app.state.rate_feed.read()
    except RatesUnavailable:
        raise HTTPException(
            status_code=503, detail="Курсы Банка России сейчас недоступны"
        ) from None


@router.get("/transactions")
def list_transactions(
    filters: Annotated[TransactionQuery, Query()],
    db: DatabaseSession,
    user: CurrentUser,
) -> list[TransactionResponse]:
    record = FinanceTransaction
    query = select(record).where(record.owner_id == user.id)
    if filters.start is not None:
        query = query.where(record.occurred_on >= filters.start)
    if filters.end is not None:
        query = query.where(record.occurred_on <= filters.end)
    if filters.currency is not None:
        query = query.where(record.currency == filters.currency.value)
    rows = db.scalars(
        query.order_by(record.occurred_on.desc(), record.id.desc())
        .offset(filters.offset)
        .limit(filters.limit)
    )
    return [TransactionResponse.model_validate(row) for row in rows]


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionInput, db: DatabaseSession, user: CurrentUser
) -> TransactionResponse:
    record = FinanceTransaction(owner_id=user.id, **data.model_dump())
    db.add(record)
    db.flush()
    result = TransactionResponse.model_validate(record)
    db.commit()
    return result


@router.get("/transactions/{transaction_id}")
def read_transaction(
    transaction_id: TransactionID, db: DatabaseSession, user: CurrentUser
) -> TransactionResponse:
    record = db.scalar(
        select(FinanceTransaction).where(owned_transaction(user.id, transaction_id))
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    return TransactionResponse.model_validate(record)


@router.put("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: TransactionID,
    data: TransactionInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> TransactionResponse:
    record = db.scalar(
        update(FinanceTransaction)
        .where(owned_transaction(user.id, transaction_id))
        .values(**data.model_dump())
        .returning(FinanceTransaction)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    result = TransactionResponse.model_validate(record)
    db.commit()
    return result


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: TransactionID, db: DatabaseSession, user: CurrentUser
) -> Response:
    deleted = db.scalar(
        delete(FinanceTransaction)
        .where(owned_transaction(user.id, transaction_id))
        .returning(FinanceTransaction.id)
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
