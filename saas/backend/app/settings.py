from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAAS_", extra="ignore")

    database_url: str = "sqlite:///./strix_saas.db"
    dev_mode: bool = True
    session_cookie_name: str = "strix_saas_session"
    session_secret: str = "dev-insecure-secret-change-me"
    frontend_origin: str = "http://localhost:5173"

    enable_real_scan: bool = False

    github_app_id: str | None = None
    github_app_private_key: str | None = None
    github_webhook_secret: str | None = None

    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    @property
    def github_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_private_key)

    @property
    def billing_configured(self) -> bool:
        return bool(self.stripe_secret_key)


settings = Settings()
