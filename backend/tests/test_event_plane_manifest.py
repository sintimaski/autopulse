from __future__ import annotations

from pathlib import Path

import pytest

from autopulse_backend.services.event_plane_manifest import (
    ShardManifestState,
    SqliteShardManifest,
)


def test_register_open_shard_is_persisted_and_recoverable_after_restart(tmp_path: Path) -> None:
    manifest_path = tmp_path / "events-index" / "manifest.sqlite"
    shard_id = "shard-1"
    shard_path = str(tmp_path / "events-log" / "project-a" / "2026/05/05/21" / "shard-1.jsonl")

    first = SqliteShardManifest(manifest_path)
    created = first.register_open_shard(
        shard_id=shard_id,
        project_id="project-a",
        shard_path=shard_path,
    )
    first.close()

    second = SqliteShardManifest(manifest_path)
    recovered = second.get_shard(shard_id)
    second.close()

    assert created.state == ShardManifestState.OPEN
    assert recovered is not None
    assert recovered.shard_id == shard_id
    assert recovered.project_id == "project-a"
    assert recovered.shard_path == shard_path
    assert recovered.state == ShardManifestState.OPEN


def test_state_transition_sequence_open_to_compacted_is_allowed(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "manifest.sqlite")
    try:
        manifest.register_open_shard(
            shard_id="shard-2",
            project_id="project-a",
            shard_path="/tmp/shard-2.jsonl",
        )
        sealed = manifest.transition_state(shard_id="shard-2", to_state=ShardManifestState.SEALED)
        compacting = manifest.transition_state(
            shard_id="shard-2", to_state=ShardManifestState.COMPACTING
        )
        compacted = manifest.transition_state(
            shard_id="shard-2", to_state=ShardManifestState.COMPACTED
        )
        assert sealed.state == ShardManifestState.SEALED
        assert compacting.state == ShardManifestState.COMPACTING
        assert compacted.state == ShardManifestState.COMPACTED
    finally:
        manifest.close()


def test_duplicate_transition_attempt_is_idempotent(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "manifest.sqlite")
    try:
        manifest.register_open_shard(
            shard_id="shard-3",
            project_id="project-a",
            shard_path="/tmp/shard-3.jsonl",
        )
        first = manifest.transition_state(shard_id="shard-3", to_state=ShardManifestState.SEALED)
        second = manifest.transition_state(shard_id="shard-3", to_state=ShardManifestState.SEALED)
        assert first.state == ShardManifestState.SEALED
        assert second.state == ShardManifestState.SEALED
    finally:
        manifest.close()


def test_invalid_transition_raises_value_error(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "manifest.sqlite")
    try:
        manifest.register_open_shard(
            shard_id="shard-4",
            project_id="project-a",
            shard_path="/tmp/shard-4.jsonl",
        )
        with pytest.raises(ValueError, match="Invalid shard manifest transition"):
            manifest.transition_state(shard_id="shard-4", to_state=ShardManifestState.COMPACTING)
    finally:
        manifest.close()


def test_register_open_shard_duplicate_is_idempotent_for_same_fields(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "manifest.sqlite")
    try:
        first = manifest.register_open_shard(
            shard_id="shard-5",
            project_id="project-a",
            shard_path="/tmp/shard-5.jsonl",
        )
        second = manifest.register_open_shard(
            shard_id="shard-5",
            project_id="project-a",
            shard_path="/tmp/shard-5.jsonl",
        )
        assert first.shard_id == second.shard_id
        assert second.state == ShardManifestState.OPEN
    finally:
        manifest.close()


def test_register_open_shard_duplicate_with_mismatched_fields_raises(tmp_path: Path) -> None:
    manifest = SqliteShardManifest(tmp_path / "manifest.sqlite")
    try:
        manifest.register_open_shard(
            shard_id="shard-6",
            project_id="project-a",
            shard_path="/tmp/shard-6.jsonl",
        )
        with pytest.raises(ValueError, match="register_open_shard conflict"):
            manifest.register_open_shard(
                shard_id="shard-6",
                project_id="project-b",
                shard_path="/tmp/shard-6.jsonl",
            )
    finally:
        manifest.close()
