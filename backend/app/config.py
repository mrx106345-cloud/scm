"""Application settings loaded from environment / .env file.

All secrets come from env vars or the encrypted store — never hardcoded.
All times are UTC internally.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central backend configuration (P1-01)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCM_", extra="ignore")

    app_name: str = "SCM Agent"
    app_version: str = "0.1.0"
    environment: str = "dev"  # dev | test | prod

    # Database: SQLite for dev/test only; PostgreSQL 15+ in production.
    database_url: str = "sqlite:///./scm_dev.db"

    # Session / auth (dev default only; prod overrides via SCM_SESSION_SECRET env)
    session_secret: str = "dev-only-secret-change-in-prod"  # noqa: S105
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    password_min_length: int = 12
    login_lockout_failures: int = 5
    login_lockout_minutes: int = 15

    # Pipeline
    pipeline_cron: str = "0 6 * * *"
    agent_timeout_seconds: int = 1200
    agent_max_retries: int = 2

    # Inventory defaults (estimates, editable in Admin > Settings)
    target_cover_days: int = 30
    default_stockout_cost_factor: float = 2.0
    carrying_rate: float = 0.20
    excess_days: int = 120
    dead_days: int = 180
    stale_days: int = 3

    # Service levels by criticality
    service_level_A: float = 0.98
    service_level_B: float = 0.95
    service_level_C: float = 0.90

    # LLM
    llm_model_path: str = "/data/models/model.gguf"
    llm_max_tokens: int = 512
    llm_timeout_seconds: int = 120

    # Filesystem roots (inside /data on customer installs)
    data_dir: str = "./data"
    inbox_dir: str = "./data/inbox"
    outbox_dir: str = "./data/outbox"

    currency: str = "INR"


settings = Settings()
