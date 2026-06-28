from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    verity_api_url: str = "https://v-rify-ia.fly.dev"
    verity_timeout: int = 10
    agent_id: str = "sios"
    max_iterations: int = 6

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
