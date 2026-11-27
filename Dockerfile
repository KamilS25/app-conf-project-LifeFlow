ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:${PYTHON_VERSION}-slim AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN groupadd --system lifeflow \
    && useradd --system --gid lifeflow --no-create-home lifeflow

COPY --from=builder /app/.venv .venv
COPY main.py settings.py pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations

USER lifeflow
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=5s --start-period=10s --retries=5 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=4).close()"]

CMD ["sh", "-ec", "alembic upgrade head && exec python -m uvicorn main:app --host 0.0.0.0 --port 8000"]
