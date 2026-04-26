from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    cors_allow_origins: tuple[str, ...]
    default_sdk_version: str = "unknown"


def get_settings() -> Settings:
    raw_cors_origins = getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    cors_allow_origins = tuple(
        origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()
    )
    return Settings(
        database_url=getenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db"),
        cors_allow_origins=cors_allow_origins,
    )
