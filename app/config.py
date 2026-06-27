from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERITY_", case_sensitive=False)

    # Ledger
    db_path: str = "/tmp/verity_ledger.db"
    signing_key: str = "verity-dev-key-change-in-production"

    # Sandbox defaults
    default_timeout: int = 5
    default_memory: str = "128m"
    # WARNING: never set True in production — subprocess executes code on the host.
    allow_subprocess_fallback: bool = False

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "text"

    # API
    api_title: str = "VERITY CORE"
    api_version: str = "0.4.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
