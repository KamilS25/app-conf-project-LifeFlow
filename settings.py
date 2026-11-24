from typing import Literal

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    app_env: Literal["dev", "prod"] = Field(default="dev", validation_alias="APP_ENV")
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    db_connect_timeout: int = Field(
        default=3, ge=2, validation_alias="DB_CONNECT_TIMEOUT"
    )
    pg_database: str | None = Field(default=None, validation_alias="PGDATABASE")
    pg_user: str | None = Field(default=None, validation_alias="PGUSER")
    pg_password: SecretStr | None = Field(default=None, validation_alias="PGPASSWORD")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        conninfo = value.get_secret_value()
        if not conninfo.strip():
            raise ValueError("Database connection string is empty")
        try:
            conninfo_to_dict(conninfo)
        except ProgrammingError:
            raise ValueError("Invalid PostgreSQL connection string") from None
        return value

    def database_conninfo(self) -> str:
        defaults = {
            "dbname": self.pg_database,
            "user": self.pg_user,
            "password": self.pg_password.get_secret_value()
            if self.pg_password
            else None,
        }
        options = conninfo_to_dict(self.database_url.get_secret_value())
        return make_conninfo("", **(defaults | options))


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        fields = error.errors(
            include_input=False, include_context=False, include_url=False
        )
        variables = ", ".join(str(field["loc"][0]) for field in fields)
        raise SystemExit(
            f"Missing or invalid environment variables: {variables}"
        ) from None
