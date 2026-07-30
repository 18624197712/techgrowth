from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TG_", extra="ignore")

    app_name: str = "TechGrowth"
    environment: str = "development"
    database_url: str = "sqlite:///./data/techgrowth.db"
    secret_key: str = "change-this-development-secret"
    encryption_key: str = "change-this-development-encryption-key"
    secure_cookies: bool = False
    session_hours: int = 12
    temp_upload_dir: Path = Path("./data/uploads")
    app_domain: str = "localhost"
    icp_number: str = ""
    openai_base_url: str = ""
    openai_api_key: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    chat_model: str = ""
    embedding_model: str = ""
    max_agent_tokens: int = 30_000
    max_daily_tokens: int = 100_000
    github_token: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender: str = ""
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:admin@localhost"
    timezone: str = "Asia/Shanghai"
    allowed_origins: list[str] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    return Settings()
