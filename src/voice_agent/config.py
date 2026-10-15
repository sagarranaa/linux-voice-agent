from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr
    groq_chat_model: str = "llama-3.3-70b-versatile"
    groq_stt_model: str = "whisper-large-v3-turbo"
    groq_stt_language: str = "en"

    agent_workspace: Path = Path("./data/workspace")
    agent_max_steps: int = Field(default=8, ge=1, le=30)
    tool_timeout_seconds: int = Field(default=15, ge=1, le=120)
    log_level: str = "INFO"

    @field_validator("groq_api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()

        if not key or key == "your_actual_key_here":
            raise ValueError("Set a real GROQ_API_KEY in your environment or .env")

        return SecretStr(key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process and reuse them."""
    return Settings()
