"""Hatch hook: build Next static export into ``src/autopulse/ui/`` before wheels."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _find_repo_root_and_bundle_script(sdk_root: Path) -> tuple[Path, Path]:
    """Monorepo (``sdk/`` parent) or sdist tree (``frontend/`` + ``scripts/``)."""
    candidates: list[tuple[Path, Path]] = [
        (sdk_root.parent, sdk_root.parent / "scripts" / "bundle_embedded_dashboard_ui.sh"),
        (sdk_root, sdk_root / "scripts" / "bundle_embedded_dashboard_ui.sh"),
    ]
    for repo_root, script in candidates:
        if script.is_file() and (repo_root / "frontend" / "package.json").is_file():
            return repo_root, script
    raise RuntimeError(
        "Embedded UI build needs frontend/package.json and "
        "scripts/bundle_embedded_dashboard_ui.sh (monorepo root or sdist layout)."
    )


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel":
            return
        sdk_root = Path(self.root).resolve()
        repo_root, bundle_script = _find_repo_root_and_bundle_script(sdk_root)
        env = {**os.environ, "AUTOPULSE_BUNDLE_SKIP_NPM_CI": "1"}
        try:
            subprocess.run(
                ["bash", str(bundle_script)],
                cwd=str(repo_root),
                env=env,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Embedded UI bundle requires `bash` and a successful `npm run build` "
                "(install Node.js and run `npm --prefix frontend ci` if needed)."
            ) from exc
        ui_index = sdk_root / "src" / "autopulse" / "ui" / "index.html"
        if not ui_index.is_file():
            raise RuntimeError(
                f"Embedded UI bundle failed: missing {ui_index} "
                "(check `frontend` build / `basePath` export)."
            )
        artifacts = build_data.setdefault("artifacts", [])
        marker = "src/autopulse/ui/**"
        if marker not in artifacts:
            artifacts.append(marker)
