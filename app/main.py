from typing import Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize minimal SQLite database configuration on startup
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Merchant-as-a-Tool Agent Gateway API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=Dict[str, str])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
