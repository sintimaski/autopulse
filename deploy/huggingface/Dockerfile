# Lumonox — Hugging Face Spaces demo image.
#
# Self-contained: installs the published `lumonox` wheel (FastAPI ingest API, dashboard
# API, and the Next.js dashboard static export are all baked into the wheel) and runs a
# seeded, self-refreshing demo. No monorepo checkout required.
#
# Setup + push instructions: docs/ops/HUGGINGFACE_SPACE.md
FROM python:3.11-slim

# Pinned Lumonox release. The wheel bundles `lumonox_backend/dashboard_static/` (the
# dashboard UI) and `lumonox_backend/alembic/` (DB migrations) — verified before pinning.
ARG LUMONOX_VERSION=0.3.1

RUN pip install --no-cache-dir "lumonox==${LUMONOX_VERSION}"

# Patch the wheel's bundled dashboard for the demo: rewrite the baked-in API origin to
# same-origin, and inject auto sign-in for the shared demo account. See patch_dashboard.py
# for the full rationale; both steps are idempotent no-ops once unnecessary.
COPY patch_dashboard.py /tmp/patch_dashboard.py
RUN python /tmp/patch_dashboard.py && rm /tmp/patch_dashboard.py

# Hugging Face Spaces run the container as UID 1000. Create that user and keep every
# writable path under its home. The Spaces free-tier filesystem is ephemeral, which
# suits this demo: each cold start re-seeds from scratch (the demo self-cleans).
RUN useradd --create-home --uid 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app
COPY --chown=user:user entrypoint.sh seed_demo.py ./
RUN chmod +x entrypoint.sh

# --- Demo runtime configuration ------------------------------------------------------
# LUMONOX_ENV=demo keeps the deployment out of the production invariant checks (see
# backend core/config.py validate_deployment_settings) while still avoiding any
# production-only lockdown. Relative DB / event-store paths anchor to LUMONOX_DATA_DIR.
ENV LUMONOX_DATA_DIR=/home/user/data \
    LUMONOX_ENV=demo \
    DATABASE_URL=sqlite+aiosqlite:///./.lumonox/lumonox.db \
    DATABASE_RUN_MIGRATIONS_ON_STARTUP=true \
    LUMONOX_EVENT_STORE=duckdb \
    JOBS_ENABLE_SCHEDULER=true \
    INGEST_REQUIRE_HTTPS=false \
    DEV_SCENARIOS_ENABLED=true \
    LUMONOX_STUDIO_SHOWCASE_DEMO=true \
    DASHBOARD_AUTH_ENABLED=true \
    DASHBOARD_AUTH_ALLOWED_EMAIL=demo@lumonox.dev \
    DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true \
    ALERT_EMAIL_PROVIDER=file \
    ALERT_EMAIL_FROM=demo@lumonox.dev \
    LUMONOX_DEMO_EMAIL=demo@lumonox.dev \
    LUMONOX_DEMO_PORT=8000 \
    LUMONOX_DEMO_BACKFILL_HOURS=24 \
    LUMONOX_DEMO_BACKFILL_CHUNK_PAUSE_SECONDS=0.3 \
    LUMONOX_DEMO_LIVE_INTERVAL_SECONDS=25

# Must match LUMONOX_DEMO_PORT and the `app_port:` value in the Space README frontmatter.
EXPOSE 8000

CMD ["./entrypoint.sh"]
