from __future__ import annotations

import pytest
from fastapi import HTTPException

from autopulse_backend.dashboard.routes.query_explorer import _validate_query


def test_validate_accepts_select_followed_by_newline() -> None:
    sql = (
        "SELECT\n"
        "  service_name,\n"
        "  environment\n"
        "FROM scoped_events\n"
        "GROUP BY service_name, environment"
    )
    assert _validate_query(sql) == sql


def test_validate_accepts_with_cte() -> None:
    sql = "WITH t AS (SELECT id FROM scoped_events LIMIT 1)\n" "SELECT * FROM t"
    assert _validate_query(sql) == sql


def test_validate_rejects_non_select() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_query("DELETE FROM scoped_events")
    assert exc.value.status_code == 422
    assert "SELECT/CTE" in str(exc.value.detail)


def test_validate_requires_scoped_events() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_query("SELECT 1")
    assert "scoped_events" in str(exc.value.detail).lower()
