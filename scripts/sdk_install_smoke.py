"""Install-matrix smoke test for ``lumonox-sdk``.

Each cell of ``.github/workflows/sdk-install-matrix.yml`` runs this script after
``pip install lumonox_sdk-*.whl`` inside a target image. The checks below mirror
the acceptance criteria in ``docs/plans/sdk-install-ease.md``:

* the public import surface works,
* the FastAPI middleware can be attached to a real ``FastAPI`` instance,
* the psutil-backed infrastructure sampler still emits its full counter set
  (the load-bearing "no functional regression" gate — install-ease wins must
  not silently drop a default capture path),
* ``python -c "import lumonox"`` finishes under the 100 ms cold-import budget.

Exits non-zero with a human-readable explanation on any failure.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from typing import Final

COLD_IMPORT_BUDGET_MS: Final[float] = 100.0
REQUIRED_INFRA_KEYS: Final[frozenset[str]] = frozenset(
    {
        "host_cpu_percent",
        "host_memory_used_percent",
        "process_cpu_percent",
        "process_memory_rss_bytes",
        "disk_used_percent",
        "network_bytes_recv",
        "network_bytes_sent",
    }
)


def _ok(label: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  [ok] {label}{suffix}")


def _fail(label: str, detail: str) -> None:
    print(f"  [FAIL] {label} — {detail}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    print(
        f"lumonox-sdk install smoke: python={platform.python_version()} "
        f"impl={platform.python_implementation()} machine={platform.machine()} "
        f"libc={platform.libc_ver()}"
    )

    # 1. Import surface --------------------------------------------------------------
    try:
        import lumonox
        from lumonox import (
            BarChartWidget,  # noqa: F401
            BaseDashboardWidget,  # noqa: F401
            CardWidget,  # noqa: F401
            DonutChartWidget,  # noqa: F401
            HistogramWidget,  # noqa: F401
            LineChartWidget,  # noqa: F401
            ScatterPlotWidget,  # noqa: F401
            StackedAreaWidget,  # noqa: F401
            capture_background_job,  # noqa: F401
            monitor,  # noqa: F401
        )
        from lumonox import lumonox as lumonox_setup
    except Exception as exc:  # noqa: BLE001
        _fail("import lumonox", f"{type(exc).__name__}: {exc}")
        return
    _ok("import lumonox", f"version path attrs={len(lumonox.__all__)}")

    # 2. Middleware attaches to a real FastAPI app -----------------------------------
    try:
        from fastapi import FastAPI

        app = FastAPI()
        lumonox_setup(app, api_key="smoke", ingest_url="https://example.invalid/ingest")
    except Exception as exc:  # noqa: BLE001
        _fail("attach middleware", f"{type(exc).__name__}: {exc}")
        return
    if not getattr(app.state, "_lumonox_configured", False):
        _fail("attach middleware", "app.state._lumonox_configured is not True")
    _ok("attach middleware", "app.state._lumonox_configured=True")

    # 3. psutil-backed infrastructure sampler still works (no regression) ----------
    try:
        from lumonox._infrastructure import InfrastructureSampler

        sample = InfrastructureSampler().sample()
    except Exception as exc:  # noqa: BLE001
        _fail("infrastructure sampler", f"{type(exc).__name__}: {exc}")
        return
    if not sample:
        _fail(
            "infrastructure sampler",
            "InfrastructureSampler().sample() returned empty — psutil likely missing",
        )
    missing = REQUIRED_INFRA_KEYS - set(sample.keys())
    if missing:
        _fail("infrastructure sampler", f"missing required keys: {sorted(missing)}")
    _ok("infrastructure sampler", f"keys={len(sample)}")

    # 4. Cold-import regression guard ------------------------------------------------
    timings_ms: list[float] = []
    for _ in range(3):
        started = time.perf_counter()
        subprocess.check_call([sys.executable, "-c", "import lumonox"])
        timings_ms.append((time.perf_counter() - started) * 1000.0)
    best = min(timings_ms)
    if best > COLD_IMPORT_BUDGET_MS:
        fail_fmt = [f"{t:.1f}" for t in timings_ms]
        _fail(
            "cold import",
            f"best of 3 was {best:.1f} ms (budget {COLD_IMPORT_BUDGET_MS:.0f} ms); all={fail_fmt}",
        )
    all_fmt = [f"{t:.1f}" for t in timings_ms]
    _ok("cold import", f"best={best:.1f} ms (budget {COLD_IMPORT_BUDGET_MS:.0f} ms); all={all_fmt}")

    print("OK — lumonox-sdk install smoke passed.")


if __name__ == "__main__":
    main()
