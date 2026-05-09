from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from lumonox_backend.models import IngestRateLimitWindow
from lumonox_backend.repositories import runtime_controls
from lumonox_backend.repositories.runtime_controls import allow_distributed_ingest_request


class _FakeSession:
    def __init__(
        self, *, rows: list[IngestRateLimitWindow | None], commit_failures: int = 0
    ) -> None:
        self._rows = rows
        self._commit_failures_remaining = commit_failures
        self.commit_calls = 0
        self.rollback_calls = 0
        self.execute_calls = 0
        self.added_rows: list[IngestRateLimitWindow] = []

    async def execute(self, _stmt: object) -> None:
        self.execute_calls += 1

    async def scalar(self, _stmt: object) -> IngestRateLimitWindow | None:
        if self._rows:
            return self._rows.pop(0)
        return None

    def add(self, row: IngestRateLimitWindow) -> None:
        self.added_rows.append(row)

    async def commit(self) -> None:
        self.commit_calls += 1
        if self._commit_failures_remaining > 0:
            self._commit_failures_remaining -= 1
            raise IntegrityError("insert", {}, Exception("duplicate key"))

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.mark.anyio
async def test_distributed_rate_limit_retries_first_hit_integrity_collision() -> None:
    project_id = uuid4()
    now = datetime.now(tz=UTC)
    session = _FakeSession(rows=[None, None], commit_failures=1)

    allowed = await allow_distributed_ingest_request(
        session=session,  # type: ignore[arg-type]
        project_id=project_id,
        max_requests=100,
        window_seconds=60,
        now=now,
    )

    assert allowed is True
    assert session.commit_calls == 2
    assert session.rollback_calls == 1
    assert session.execute_calls == 2
    assert len(session.added_rows) == 2


@pytest.mark.anyio
async def test_allow_distributed_ingest_request_raises_after_retry_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime_controls, "_DISTRIBUTED_INGEST_RL_ATTEMPTS", 3)
    session = _FakeSession(rows=[None, None, None], commit_failures=10)

    with pytest.raises(RuntimeError, match="retry budget"):
        await allow_distributed_ingest_request(
            session=session,  # type: ignore[arg-type]
            project_id=uuid4(),
            max_requests=10,
            window_seconds=30,
        )

    assert session.commit_calls == 3
    assert session.rollback_calls == 3
    assert session.execute_calls == 3
