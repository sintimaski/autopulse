# Hugging Face Spaces — public Lumonox demo

A self-contained, free, public demo of Lumonox running as a **Docker Space**. Visitors
sign in to a shared demo project that is pre-seeded with synthetic request/error history
and kept moving by a light live traffic trickle.

Everything the Space needs lives in [`deploy/huggingface/`](../../deploy/huggingface/) —
three files, no monorepo checkout required on the Space side.

## How it works

| File | Role |
|------|------|
| `deploy/huggingface/Dockerfile` | `pip install lumonox==<pinned>` — the wheel bundles the FastAPI ingest + dashboard API, the Next.js dashboard static export, and the Alembic migrations. Sets demo runtime env and runs as UID 1000 (Spaces requirement). |
| `deploy/huggingface/entrypoint.sh` | bootstrap demo tenant + migrations → start the API (`uvicorn`, `--proxy-headers`) → backfill history → run the live trickle. `wait`s on the API so the container lifecycle follows it. |
| `deploy/huggingface/seed_demo.py` | `--bootstrap` (org / project / dashboard user + owner membership / ingest key, idempotent), `--backfill` (POSTs recent synthetic history to `/ingest`), `--live` (loops POSTing fresh batches). Depends only on the installed `lumonox` package. |

Key runtime choices (set as `ENV` in the Dockerfile):

- **`LUMONOX_ENV=demo`** — not `production`, so the production invariant checks
  (`validate_deployment_settings`) don't fire and dev-only switches are allowed.
- **`DEV_SCENARIOS_ENABLED=true`** — not strictly required (the seed generates traffic
  in-process and POSTs to `/ingest`), but enabled so the `/dev/scenarios/*` routes are
  available for manual poking.
- **Sign-in:** `DASHBOARD_AUTH_ENABLED=true` + `DASHBOARD_AUTH_ALLOWED_EMAIL=demo@lumonox.dev`
  + `DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true`. Only the demo email can sign in, and
  the magic link is shown inline in the UI (no email delivery needed). Every visitor logs
  in as the same pre-seeded user and lands on the same seeded project.
- **`INGEST_REQUIRE_HTTPS=false`** — the seed POSTs to `http://127.0.0.1:8000/ingest`
  inside the container; the public origin is still HTTPS via the Spaces TLS proxy.
- **Storage** is SQLite + DuckDB under `LUMONOX_DATA_DIR=/home/user/data`. The Spaces
  free-tier filesystem is **ephemeral**, so each cold start re-seeds from scratch — the
  demo self-cleans.

## One-time setup

1. **Create the Space** at <https://huggingface.co/new-space>:
   - Owner: your HF account/org
   - Space name: e.g. `lumonox-demo`
   - License: `mit`
   - SDK: **Docker** → **Blank**
   - Hardware: **CPU basic** (free) is enough
   - Visibility: **Public**

2. **Push the three files to the Space repo root.** The Space is its own git repo, and a
   Docker Space requires `Dockerfile` at the repo root — so push the *contents* of
   `deploy/huggingface/`, not the directory itself:

   ```bash
   # from a clean checkout location
   git clone https://huggingface.co/spaces/<owner>/lumonox-demo
   cd lumonox-demo
   cp /path/to/lumonox/deploy/huggingface/{Dockerfile,entrypoint.sh,seed_demo.py,README.md} .
   git add Dockerfile entrypoint.sh seed_demo.py README.md
   git commit -m "Lumonox demo Space"
   git push
   ```

   > HF authentication: use an access token with **write** scope as the git password,
   > or `huggingface-cli login` first. Large files aren't involved — this is a tiny repo.

3. The Space builds the image and starts the container. First build takes a few minutes
   (pip install + image layers); subsequent restarts are fast.

## Verifying

Once the Space shows **Running**:

- The app URL redirects `/` → `/lumonox/ui/` (the dashboard sign-in screen).
- Sign in with `demo@lumonox.dev`; the UI shows the magic link inline — click it.
- The **Overview** should already show a few hours of traffic, and new data should
  appear every ~25s from the live trickle.
- Build/runtime logs are under the Space's **Logs** tab — look for the `[entrypoint]`
  and `[seed]` lines.

## Updating

- **New Lumonox release:** bump `ARG LUMONOX_VERSION` in `deploy/huggingface/Dockerfile`,
  re-copy the files to the Space repo, commit, push. **Verify the new wheel still bundles
  `lumonox_backend/dashboard_static/` and `lumonox_backend/alembic/`** before pinning:

  ```bash
  pip download lumonox==<version> --no-deps -d /tmp/lxwheel
  unzip -l /tmp/lxwheel/lumonox-*.whl | grep -E 'dashboard_static/index.html|alembic/env.py'
  ```

- **Demo behavior changes:** edit `entrypoint.sh` / `seed_demo.py` here, re-copy, push.
- **Tuning knobs** (override as Space *Variables*, no rebuild needed for some):
  `LUMONOX_DEMO_BACKFILL_HOURS` (default `4`), `LUMONOX_DEMO_LIVE_INTERVAL_SECONDS`
  (default `25`), `LUMONOX_DEMO_EMAIL`, `LUMONOX_DEMO_API_KEY` (otherwise generated and
  cached at `$LUMONOX_DATA_DIR/.lumonox/demo_api_key`).

## Limitations / notes

- **Shared account.** Everyone signs in as `demo@lumonox.dev`, so dashboard settings
  changes are visible to other visitors until the next restart.
- **Ephemeral data.** No persistent disk on the free tier; restarts wipe and re-seed.
  Spaces also sleep after a period of inactivity and re-seed on the next visit.
- **Public ingest key.** The demo's ingest key authorizes `POST /ingest`; it's a
  throwaway demo project and the backend rate-limits ingestion. Don't reuse it anywhere.
- This is **not** a hosted product. For real self-hosting see `docs/ops/PRODUCTION_DEPLOYMENT.md`
  and `docs/ops/docker-compose.lumonox.yml`.
