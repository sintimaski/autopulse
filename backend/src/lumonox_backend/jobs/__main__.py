"""Allow ``python -m lumonox_backend.jobs <command>`` (package entrypoint)."""

from __future__ import annotations

from lumonox_backend.jobs import main

if __name__ == "__main__":
    raise SystemExit(main())
