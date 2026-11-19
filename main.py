
import os

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="LifeFlow",
    description="LifeFlow application",
    version="0.1.0",
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hello World"}


@app.get("/health")
async def health_check():
    """Check application and PostgreSQL availability."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable",
        )

    try:
        with psycopg.connect(database_url, connect_timeout=3) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable",
        ) from None

    return {"status": "healthy", "database": "ok"}
