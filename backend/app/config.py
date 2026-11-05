"""Application settings loaded from environment / .env file.

All secrets come from env vars or the encrypted store — never hardcoded.
All times are UTC internally.
"""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bandit B105 heuristic flags the literal because of the variable name; this
# is the dev-only default and `Settings` refuses it in prod (model_validator).
_DEV_SESSION_SECRET = "dev-only-secret-change-in-prod"  # noqa: S105  # nosec B105


class Settings(BaseSettings):
    """Central backend configuration (P1-01)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCM_", extra="ignore")

    app_name: str = "SCM Agent"
    app_version: str = "0.1.0"
    environment: str = "dev"  # dev | test | prod

    # Database: SQLite for dev/test only; PostgreSQL 15+ in production.
    database_url: str = "sqlite:///./scm_dev.db"

    # Session / auth (dev default only; prod overrides via SCM_SESSION_SECRET env)
    session_secret: str = _DEV_SESSION_SECRET  # noqa: S105
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

    # Credential encryption (P4-04): base64 32-byte AES-256-GCM key via
    # SCM_CREDENTIAL_KEY, or a 0600 key file at this path.
    credential_key_file: str = ""

    # Autonomy (Part I): level 3 needs this many days in L1/L2 first.
    autonomy_min_days: int = 30

    # Optional connectors (P4-07): Zoho is off unless the owner enables it.
    zoho_enabled: bool = False
    zoho_api_base: str = "https://www.zohoapis.com"

    # Direct ERP write (P4-06): off by default even when a connector opts in.
    erp_write_enabled: bool = False

    # SAP B1 host allowlist (P4-03 hardening): empty = any configured host.
    sap_allowed_hosts: str = ""

    currency: str = "INR"

    @model_validator(mode="after")
    def _fail_fast_on_insecure_prod(self) -> Settings:
        """Refuse to start prod with the development session secret."""
        if self.environment == "prod" and self.session_secret == _DEV_SESSION_SECRET:
            raise ValueError(
                "SCM_SESSION_SECRET must be set when SCM_ENVIRONMENT=prod; "
                "refusing to sign sessions with the built-in dev secret"
            )
        return self


settings = Settings()
