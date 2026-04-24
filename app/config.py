"""
Configuration module for the Finance App.
Loads settings from environment variables.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Plaid Configuration
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "development"  # sandbox, development, or production

    # AI Configuration
    ai_api_key: str = ""
    force_gemini: bool = False
    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"

    # Database (optional - if you want to override the hardcoded sqlite path)
    database_url: str = "sqlite:///./data/finance.db"

    # App Configuration
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()