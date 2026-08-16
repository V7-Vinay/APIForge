from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "APIForge"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.12.0"
    BUILD_SHA: str = "dev"
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
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver,test,backend"
    TRUST_PROXY_HEADERS: bool = False
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_GENERAL: int = 300
    RATE_LIMIT_LOGIN: int = 10
    RATE_LIMIT_REGISTER: int = 5
    RATE_LIMIT_REFRESH: int = 20
    RATE_LIMIT_EXECUTION: int = 30
    RATE_LIMIT_FAIL_OPEN: bool = True
    METRICS_ENABLED: bool = True
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT_SECONDS: int = 30
    DATABASE_POOL_RECYCLE_SECONDS: int = 1800
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
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
