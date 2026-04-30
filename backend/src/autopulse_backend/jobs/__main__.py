"""Allow ``python -m autopulse_backend.jobs <command>`` (package entrypoint)."""

from __future__ import annotations

from autopulse_backend.jobs import main

if __name__ == "__main__":
    raise SystemExit(main())
