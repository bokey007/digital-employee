"""Application settings loaded from environment variables."""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    AZURE = "azure"


class AppEnv(str, Enum):
    """Application environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Central application settings — validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.OPENAI

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment: str = "gpt-4o"

    # ── Email ────────────────────────────────────────────────────────────────
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_address: str = ""
    email_password: str = ""
    email_use_tls: bool = True

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://digital_employee:secret@localhost:5432/digital_employee"
    database_url_sync: str = "postgresql+psycopg2://digital_employee:secret@localhost:5432/digital_employee"

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Recipients ───────────────────────────────────────────────────────────
    anuj_email: str = ""
    anuj_name: str = "Anuj"
    ashwin_email: str = ""
    ashwin_name: str = "Ashwin"
    distribution_list_raw: str = Field(default="", alias="DISTRIBUTION_LIST")

    @property
    def distribution_list(self) -> list[str]:
        """Split comma-separated emails into a list."""
        if not self.distribution_list_raw:
            return []
        return [e.strip() for e in self.distribution_list_raw.split(",") if e.strip()]

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Digital Employee"
    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: str = "INFO"
    secret_key: str = "change-me-to-a-random-string"

    # ── Newsletter ───────────────────────────────────────────────────────────
    newsletter_subject_prefix: str = "[Monthly Newsletter]"
    reminder_after_days: int = 3
    max_reminders: int = 2

    # ── Derived properties ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION


def get_settings() -> Settings:
    """Factory — returns a cached Settings instance."""
    return Settings()
