# Lumonox — Hugging Face Spaces demo image.
#
# Two-stage build so the demo can ship UI changes (and any FE fixes) ahead of the next
# `lumonox` wheel release. Stage 1 clones the repo and builds the Next.js dashboard
# static export from source; stage 2 installs the published wheel for the backend +
# overlays the freshly-built dashboard via ``LUMONOX_FRONTEND_STATIC_DIR``.
#
# Setup + push instructions: docs/ops/HUGGINGFACE_SPACE.md

# ---- Stage 1: build the dashboard static export from source ------------------------
FROM node:22-slim AS frontend
# Bump this to ship newer FE changes to the demo without waiting for a wheel release.
# Use a commit SHA or branch name. ``main`` tracks the latest pushed code.
ARG LUMONOX_FRONTEND_REF=main
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 50 https://github.com/sintimaski/lumonox.git . \
 && git checkout "${LUMONOX_FRONTEND_REF}"
WORKDIR /src/frontend
# Same-origin API base — the dashboard is mounted on its own API host at /lumonox/ui/.
# NEXT_PUBLIC_* is inlined at build time; this matches the upstream publish-workflow fix.
# NEXT_PUBLIC_DEMO_EMAIL enables the "Try Demo" button and auto-verify flow in the login page.
ENV NEXT_PUBLIC_LUMONOX_API_BASE_URL="" \
    NEXT_PUBLIC_DEMO_EMAIL=demo@lumonox.dev
RUN npm ci && npm run build

# ---- Stage 2: runtime ---------------------------------------------------------------
FROM python:3.11-slim

# Pinned Lumonox wheel (the API + Alembic migrations come from here; the dashboard is
# overridden by the stage-1 build via LUMONOX_FRONTEND_STATIC_DIR below).
ARG LUMONOX_VERSION=0.3.1

RUN pip install --no-cache-dir "lumonox==${LUMONOX_VERSION}"

# Copy the freshly-built dashboard from stage 1 to a stable path the backend can mount.
COPY --from=frontend /src/frontend/out /opt/lumonox-dashboard

# Demo-only patches to the bundled UI: inject auto sign-in (the production build hides
# the dev magic link by design). The API-origin rewrite step is harmless on the
# rebuilt frontend (built same-origin) but kept for defense-in-depth.
COPY patch_dashboard.py /tmp/patch_dashboard.py
ENV LUMONOX_FRONTEND_STATIC_DIR=/opt/lumonox-dashboard
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
#
# ALERT_SENDER_MODE=composite + ALERT_EMAIL_PROVIDER=file means: when a visitor
# configures alert delivery in Settings the dispatch attempts are real (slack/webhook
# go out if the URL is set; email is written to the local outbox). Without external
# credentials this keeps the alerts UI fully playable without enabling real email.
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
    ALERT_SENDER_MODE=composite \
    ALERT_EMAIL_PROVIDER=file \
    ALERT_EMAIL_FROM=alerts@lumonox.dev \
    LUMONOX_DEMO_EMAIL=demo@lumonox.dev \
    LUMONOX_DEMO_PORT=8000 \
    LUMONOX_DEMO_BACKFILL_HOURS=24 \
    LUMONOX_DEMO_BACKFILL_CHUNK_PAUSE_SECONDS=0.3 \
    LUMONOX_DEMO_LIVE_INTERVAL_SECONDS=25 \
    LUMONOX_DEMO_TRACE_CHILD_SPAN_CHANCE=0.4

# Must match LUMONOX_DEMO_PORT and the `app_port:` value in the Space README frontmatter.
EXPOSE 8000

CMD ["./entrypoint.sh"]
