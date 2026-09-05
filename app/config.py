import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings(BaseModel):
    app_name: str = Field(
        default=os.getenv("APP_NAME", "Merchant-as-a-Tool Agent Gateway")
    )
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "sqlite:///./data/gateway.db")
    )
    llm_provider: str = Field(
        default=os.getenv("LLM_PROVIDER", "gemini")
    )
    gemini_api_key: Optional[str] = Field(
        default=os.getenv("GEMINI_API_KEY")
    )
    gemini_model: str = Field(
        default=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    )
    ollama_base_url: str = Field(
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = Field(
        default=os.getenv("OLLAMA_MODEL", "qwen3:8b")
    )
    razorpay_key_id: Optional[str] = Field(
        default=os.getenv("RAZORPAY_KEY_ID")
    )
    razorpay_key_secret: Optional[str] = Field(
        default=os.getenv("RAZORPAY_KEY_SECRET")
    )


settings = Settings()
