from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "APIForge"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173"

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://apiforge:apiforge_dev_password@localhost:5432/apiforge"
    )
    REDIS_URL: str = "redis://localhost:6379/0"
    ENVIRONMENT_ENCRYPTION_KEY: str = ""
    REFRESH_COOKIE_NAME: str = "refresh_token"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    JWT_SECRET_KEY: str = "dev-secret-change-this"
    JWT_ALGORITHM: str = "HS256"
    INVITATION_EXPIRE_DAYS: int = 7

    EXECUTION_TIMEOUT_SECONDS: int = 30
    EXECUTION_CONNECT_TIMEOUT_SECONDS: int = 10
    EXECUTION_MAX_RESPONSE_SIZE_BYTES: int = 5000000
    EXECUTION_MAX_REDIRECTS: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
