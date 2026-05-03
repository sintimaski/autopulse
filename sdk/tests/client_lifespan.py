"""TestClient helpers: Starlette's sync client can raise CancelledError on shutdown."""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import CancelledError
from contextlib import contextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient


@contextmanager
def lifespan_test_client(app: FastAPI, **kwargs: Any) -> Generator[TestClient, None, None]:
    client = TestClient(app, **kwargs)
    client.__enter__()
    try:
        yield client
    finally:
        with suppress(CancelledError, RuntimeError):
            client.__exit__(None, None, None)
