# Hugging Face Spaces — public Lumonox demo

A self-contained, free, public demo of Lumonox running as a **Docker Space**. Visitors
sign in to a shared demo project that is pre-seeded with synthetic request/error history
and kept moving by a light live traffic trickle.

Everything the Space needs lives in [`deploy/huggingface/`](../../deploy/huggingface/) —
a few files, no monorepo checkout required on the Space side.

## How it works

| File | Role |
|------|------|
| `deploy/huggingface/Dockerfile` | **Two-stage build.** Stage 1 (`node:22-slim`) clones the repo and runs `npm run build` so the demo can ship UI changes ahead of the next wheel release (controlled by `LUMONOX_FRONTEND_REF`). Stage 2 (`python:3.11-slim`) installs the published `lumonox` wheel for the backend and overlays the freshly-built dashboard via `LUMONOX_FRONTEND_STATIC_DIR`. Runs `patch_dashboard.py`, sets demo runtime env, runs as UID 1000 (Spaces requirement). |
| `deploy/huggingface/patch_dashboard.py` | build-time patches to the runtime-served dashboard (honors `LUMONOX_FRONTEND_STATIC_DIR`): inject auto sign-in for the shared demo account, and — as belt-and-suspenders for older wheels — rewrite any baked-in `http://127.0.0.1:8000` API origin to same-origin. See "Why the dashboard is patched" below. |
| `deploy/huggingface/entrypoint.sh` | bootstrap demo tenant + migrations → start the API (`uvicorn`, `--proxy-headers`) → backfill history → run the live trickle. `wait`s on the API so the container lifecycle follows it. |
| `deploy/huggingface/seed_demo.py` | `--bootstrap` (org / project / dashboard user + owner membership / ingest key, idempotent), `--backfill` (POSTs recent synthetic history to `/ingest` — request/error events on a diurnal curve, augmented with W3C trace context including ~40% multi-service traces so the Traces page is populated), `--live` (loops POSTing fresh batches). Depends only on the installed `lumonox` package. |

Key runtime choices (set as `ENV` in the Dockerfile):

- **`LUMONOX_ENV=demo`** — not `production`, so the production invariant checks
  (`validate_deployment_settings`) don't fire and dev-only switches are allowed.
- **`DEV_SCENARIOS_ENABLED=true`** — not strictly required (the seed generates traffic
  in-process and POSTs to `/ingest`), but enabled so the `/dev/scenarios/*` routes are
  available for manual poking.
- **Sign-in:** `DASHBOARD_AUTH_ENABLED=true` + `DASHBOARD_AUTH_ALLOWED_EMAIL=demo@lumonox.dev`
  + `DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true`. Only the demo email can sign in. The
  injected auto sign-in script (see below) completes the magic-link flow for every visitor,
  so they land straight on the shared pre-seeded project — no form to fill in.
- **Alerts (playable):** `ALERT_SENDER_MODE=composite` + `ALERT_EMAIL_PROVIDER=file`. When
  a visitor configures alert delivery in Settings, dispatches are *real* — Slack / Discord /
  generic webhooks go out if a URL is set; email is written to the local outbox file. The
  Alert Dispatches table on the dashboard reflects each attempt. Real email delivery would
  need a Resend / SendGrid API key (`ALERT_EMAIL_API_KEY`), not set in the demo.
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

2. **Push the files to the Space repo root.** The Space is its own git repo, and a
   Docker Space requires `Dockerfile` at the repo root — so push the *contents* of
   `deploy/huggingface/`, not the directory itself. Easiest is the `hf` CLI:

   ```bash
   hf upload <owner>/lumonox-demo deploy/huggingface/ . --type space
   ```

   …or with plain git (`git clone https://huggingface.co/spaces/<owner>/lumonox-demo`,
   copy the four files in, commit, push).

   > HF authentication: `hf auth login` with an access token that has **write** scope
   > (or use the token as the git password). This is a tiny repo — no large files.

3. The Space builds the image and starts the container. First build takes a few minutes
   (pip install + image layers); subsequent restarts are fast.

## Why the dashboard is patched

`patch_dashboard.py` runs at image build time and makes two changes to the wheel's
bundled dashboard. Both exist because the demo serves the wheel's *production* dashboard
build from a public HTTPS origin — a case that build is not configured for:

1. **API origin → same-origin.** `lumonox` wheels through 0.3.1 inline
   `NEXT_PUBLIC_LUMONOX_API_BASE_URL=http://127.0.0.1:8000` into the static JS (the
   publish workflow set it; that's since been fixed to build same-origin). Served over
   HTTPS from any non-localhost origin, the browser blocks the cross-origin/mixed-content
   `fetch` and sign-in fails with *"Could not reach the server to verify your session"*.
   The patch rewrites the baked-in origin to empty → same-origin `/dashboard/...` paths.
2. **Auto sign-in.** The demo uses `DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true`, but
   a production-built UI only surfaces the dev magic link when `NODE_ENV=development`
   (correct behaviour — production UIs must not leak tokens). The patch injects a small
   script into the dashboard HTML that completes the documented magic-link flow
   automatically, so visitors land straight on the dashboard.

Once a wheel built same-origin is pinned, step 1 becomes a no-op; step 1 is only fully
retired when the demo no longer needs the auto sign-in shim.

## Verifying

Once the Space shows **Running**:

- The app URL redirects `/` → `/lumonox/ui/`; a brief *"Signing you into the Lumonox
  demo…"* overlay shows while auto sign-in runs, then the dashboard loads.
- The **Overview** should already show a few hours of traffic, and new data should
  appear every ~25s from the live trickle.
- Build/runtime logs are under the Space's **Logs** tab — look for the `[patch_dashboard]`,
  `[entrypoint]`, and `[seed]` lines.

## Updating

- **New Lumonox release:** bump `ARG LUMONOX_VERSION` in `deploy/huggingface/Dockerfile`,
  re-upload (`hf upload …`). **Verify the new wheel still bundles
  `lumonox_backend/dashboard_static/` and `lumonox_backend/alembic/`** before pinning:

  ```bash
  pip download lumonox==<version> --no-deps -d /tmp/lxwheel
  unzip -l /tmp/lxwheel/lumonox-*.whl | grep -E 'dashboard_static/index.html|alembic/env.py'
  ```

  Also check whether the wheel still inlines `http://127.0.0.1:8000` in its JS
  (`unzip -p … | grep -c '127.0.0.1:8000'`) — `patch_dashboard.py` handles it either way,
  but it tells you whether the same-origin publish fix has shipped yet.

- **Demo behavior changes:** edit `entrypoint.sh` / `seed_demo.py` / `patch_dashboard.py`
  here, re-upload.
- **Frontend ref:** `LUMONOX_FRONTEND_REF` (Docker build arg, default `main`). Use a
  commit SHA or tag to pin the dashboard build; bump it to ship newer FE changes to the
  demo without waiting for a `lumonox` wheel release.
- **Tuning knobs** (override as Space *Variables*, no rebuild needed for some):
  `LUMONOX_DEMO_BACKFILL_HOURS` (default `24` — one full diurnal cycle so the day/night
  curve and the morning/evening rush-hour peaks are visible on a 1d/2d Overview window),
  `LUMONOX_DEMO_TRACE_CHILD_SPAN_CHANCE` (default `0.4` — share of seeded events that
  emit a correlated downstream span on a different service so the Traces page shows
  multi-service traces, not just trivial single-span ones),
  `LUMONOX_DEMO_BACKFILL_CHUNK_PAUSE_SECONDS`
  (default `0.3` — pause between backfill `POST /ingest` chunks so the seed burst never
  starves API reads on the free-tier instance; raise it if first-load feels slow),
  `LUMONOX_DEMO_LIVE_INTERVAL_SECONDS` (default `25`), `LUMONOX_DEMO_EMAIL`,
  `LUMONOX_DEMO_API_KEY` (otherwise generated and cached at
  `$LUMONOX_DATA_DIR/.lumonox/demo_api_key`).

## Limitations / notes

- **Shared account.** Everyone signs in as `demo@lumonox.dev`, so dashboard settings
  changes are visible to other visitors until the next restart.
- **Ephemeral data.** No persistent disk on the free tier; restarts wipe and re-seed.
  Spaces also sleep after a period of inactivity and re-seed on the next visit.
- **Public ingest key.** The demo's ingest key authorizes `POST /ingest`; it's a
  throwaway demo project and the backend rate-limits ingestion. Don't reuse it anywhere.
- This is **not** a hosted product. For real self-hosting see `docs/ops/PRODUCTION_DEPLOYMENT.md`
  and `docs/ops/docker-compose.lumonox.yml`.
