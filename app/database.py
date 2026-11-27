from collections.abc import Iterator

from fastapi import Request
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from settings import Settings


def create_database_engine(settings: Settings) -> Engine:
    options = conninfo_to_dict(settings.database_conninfo())
    options["connect_timeout"] = settings.db_connect_timeout
    return create_engine(
        "postgresql+psycopg://",
        connect_args=options,
        pool_pre_ping=True,
        hide_parameters=True,
    )


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.database_engine) as session:
        yield session
