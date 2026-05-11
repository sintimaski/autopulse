from __future__ import annotations

from lumonox_backend.dashboard.error_grouping import (
    DASHBOARD_GROUP_HASH_PATH_SEP,
    derived_error_group_key,
    normalize_exception_message_for_synthetic_grouping,
    synthetic_error_key,
)


def test_normalize_exception_message_collapses_uuids_and_long_ids() -> None:
    a = "order 550e8400-e29b-41d4-a716-446655440000 failed"
    b = "order 6ba7b810-9dad-11d1-80b4-00c04fd430c8 failed"
    na = normalize_exception_message_for_synthetic_grouping(a)
    nb = normalize_exception_message_for_synthetic_grouping(b)
    assert na == nb
    assert "<uuid>" in normalize_exception_message_for_synthetic_grouping(a)
    norm = normalize_exception_message_for_synthetic_grouping("ref 12345678901234567890")
    assert norm == "ref <id>"


def test_synthetic_error_key_stable_across_uuid_only_message_change() -> None:
    k1 = synthetic_error_key(
        "ValueError",
        "bad id 11111111-1111-1111-1111-111111111111",
        "/items/{id}",
    )
    k2 = synthetic_error_key(
        "ValueError",
        "bad id 22222222-2222-2222-2222-222222222222",
        "/items/{id}",
    )
    assert k1 == k2


def test_derived_error_group_key_prefers_error_hash_over_message_normalization() -> None:
    payload = {"error_hash": "abc", "exception_message": "x"}
    assert derived_error_group_key(payload, "/p") == f"abc{DASHBOARD_GROUP_HASH_PATH_SEP}/p"
