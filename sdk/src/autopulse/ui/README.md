# Embedded dashboard static export

This directory holds the **Next.js static export** consumed by `autopulse(..., mode="embedded")` (mounted at `/autopulse/ui/`).

It is **not committed** to git (except this file). Populate assets locally with:

```bash
# from repository root
./scripts/bundle_embedded_dashboard_ui.sh
```

The bundle script preserves this `README.md` across rebuilds. Building the **`autopulse` wheel** (e.g. `uv build --package autopulse --wheel`) runs the same bundle automatically via the Hatch build hook in [`hatch_build.py`](../../../hatch_build.py).
