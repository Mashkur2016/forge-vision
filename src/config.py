"""
Application configuration loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://forgevision:forgevision_dev_pass@localhost:5432/forgevision"

    # Security
    SETTINGS_ENCRYPTION_KEY: str = ""  # Must be set in .env for production
    JWT_SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_ACCESS_EXPIRE_MINUTES: int = 120
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # Application
    ENVIRONMENT: str = "development"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    API_BASE_URL: str = "http://localhost:8000"

    # Default LLM fallback (used if no DB settings saved yet)
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3.1:8b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"


settings = Settings()
