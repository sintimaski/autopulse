from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    default_sdk_version: str = "unknown"


def get_settings() -> Settings:
    return Settings(database_url=getenv("DATABASE_URL", "postgresql+asyncpg://localhost/autopulse"))
