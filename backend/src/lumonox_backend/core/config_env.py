from __future__ import annotations

from os import getenv
from pathlib import Path

_RUNTIME_DOTENV_LOADED = False


def candidate_backend_dotenv_files() -> list[Path]:
    """Best-effort dotenv paths so ``backend/.env`` loads for local runs and uvicorn."""
    paths: list[Path] = []
    raw = getenv("LUMONOX_BACKEND_DOTENV")
    if raw and raw.strip():
        paths.append(Path(raw).expanduser())
    cwd = Path.cwd()
    paths.extend([cwd / ".env", cwd / "backend" / ".env"])
    # Monorepo layout: …/backend/src/lumonox_backend/core/config_env.py → backend/.env
    maybe_backend_root = Path(__file__).resolve().parents[3]
    if (maybe_backend_root / "pyproject.toml").is_file():
        paths.append(maybe_backend_root / ".env")
    return paths


def load_runtime_dotenv_once() -> None:
    global _RUNTIME_DOTENV_LOADED
    if _RUNTIME_DOTENV_LOADED:
        return
    _RUNTIME_DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    seen: set[Path] = set()
    for path in candidate_backend_dotenv_files():
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_file():
            load_dotenv(path, override=False)


def env_bool(name: str, default: bool) -> bool:
    raw = getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default
    if minimum is not None:
        return max(value, minimum)
    return value


def env_optional_positive_int(name: str) -> int | None:
    """Parse a positive int from the environment, or None if unset / invalid / <= 0."""
    raw = getenv(name)
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            value = default
    if minimum is not None:
        return max(value, minimum)
    return value
