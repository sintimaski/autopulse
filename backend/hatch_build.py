"""Hatch build hook: ship ``lumonox/__init__.py`` only in non-editable wheels.

Editable installs used with ``lumonox-sdk`` in the same environment must not
place a minimal ``lumonox`` package on ``sys.path`` (see hatch force-include +
editable behavior).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class LumonoxShimHook(BuildHookInterface):
    PLUGIN_NAME = "lumonox-shim"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if version == "editable":
            return
        root = Path(self.root)
        shim = root / "packaging" / "lumonox_shim" / "__init__.py"
        if not shim.is_file():
            msg = f"missing shim file: {shim}"
            raise FileNotFoundError(msg)
        rel = shim.relative_to(root).as_posix()
        build_data.setdefault("force_include", {})[rel] = "lumonox/__init__.py"
