from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATES_SCRIPT = REPO_ROOT / "scripts" / "release_gates.sh"


def test_release_gates_script_keeps_critical_manifest_in_order() -> None:
    """Guard against accidental release-gate drift across local/CI docs."""
    content = RELEASE_GATES_SCRIPT.read_text(encoding="utf-8")
    executable_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    required_steps = [
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy",
        "uv run bandit -c pyproject.toml -r sdk/src/autopulse backend/src/autopulse_backend",
        "uv run pytest",
        "npm --prefix frontend audit --audit-level=high",
        "npm --prefix frontend run lint",
        "npm --prefix frontend run typecheck",
        "npm --prefix frontend run test",
        "npm --prefix frontend run build",
        "npm --prefix frontend run check:bundle-budget",
        "uv run python -m autopulse_backend.jobs alerts-once >/dev/null",
        "uv run python -m autopulse_backend.jobs retention-once >/dev/null",
    ]

    cursor = -1
    for step in required_steps:
        try:
            next_index = executable_lines.index(step)
        except ValueError as exc:
            raise AssertionError(f"release gate step missing: {step}") from exc
        assert next_index > cursor, f"release gate order regression near: {step}"
        cursor = next_index


def test_release_gates_script_keeps_optional_paths_explicit() -> None:
    content = RELEASE_GATES_SCRIPT.read_text(encoding="utf-8")
    assert "AUTOPULSE_RELEASE_GATES_POSTGRES" in content
    assert "AUTOPULSE_RELEASE_GATES_E2E" in content
