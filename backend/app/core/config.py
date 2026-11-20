from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "ClearWait API"
    ENVIRONMENT: str = "production"
    SECRET_KEY: str = "super-secret-key-clearwait-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str = "sqlite:///./clearwait.db"
    CORS_ORIGINS: Union[str, List[str]] = "https://vikasm777.github.io,http://localhost:3000,http://localhost:8000,http://127.0.0.1:5500"

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
