from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
RELEASE_GATES_SCRIPT_PATH = REPO_ROOT / "scripts" / "release_gates.sh"


def test_readme_keeps_release_gates_entrypoints_and_ci_parity_notes() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    required_snippets = [
        "bash ./scripts/release_gates.sh",
        "LUMONOX_RELEASE_GATES_POSTGRES=1",
        "LUMONOX_RELEASE_GATES_E2E=1",
        "#### Supported matrix and CI parity",
        "| Python | **3.11+**",
        "| Node.js | **22.x**",
    ]
    for snippet in required_snippets:
        assert snippet in readme, f"README missing DX parity snippet: {snippet}"


def test_readme_keeps_cold_clone_first_ingest_smoke_sequence() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    for command in (
        "make setup",
        "./scripts/run_synthetic_stack.sh",
        "./scripts/examples/synthetic_load_demo.sh",
        "curl -s http://127.0.0.1:8000/health",
        "curl -s http://127.0.0.1:8000/ready",
    ):
        assert command in readme, f"README cold-clone smoke command missing: {command}"


def test_release_gates_script_keeps_optional_ci_parity_switches() -> None:
    script = RELEASE_GATES_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "LUMONOX_RELEASE_GATES_POSTGRES" in script
    assert "LUMONOX_RELEASE_GATES_E2E" in script
