# PyPI publishing (Lumonox)

Canonical **install names** on PyPI:

| Distribution | PyPI project | One-line install | What you get |
|----------------|--------------|------------------|----------------|
| **API + bundled dashboard** | [**lumonox**](https://pypi.org/project/lumonox/) | `pip install lumonox` | FastAPI ingest + dashboard APIs + static UI under `/lumonox/ui/` — use **`from lumonox import mount_on_app`** (or **`lumonox_backend`** for internals) |
| **App SDK (send-only)** | [**lumonox-sdk**](https://pypi.org/project/lumonox-sdk/) | `pip install lumonox-sdk` | `from lumonox import lumonox` — FastAPI middleware; add the **`[django]`** extra (`pip install "lumonox-sdk[django]"`) for the Django ASGI adapter |
| **API + UI + SDK** | same two projects | `pip install "lumonox-sdk[stack]"` | Installs **`lumonox`** as a dependency of the SDK extra |

## Project pages (links)

- **API + UI wheel:** https://pypi.org/project/lumonox/
- **SDK wheel:** https://pypi.org/project/lumonox-sdk/

Until the first upload succeeds, those pages may show “project not found” or an empty project—create the projects on PyPI and run the GitHub Actions workflows below.

## PyPI naming

Lumonox ships as **`lumonox`** (API + bundled dashboard) and **`lumonox-sdk`** (client SDK) on PyPI. The API wheel exposes **`lumonox_backend`** plus a thin top-level **`lumonox`** facade (`create_app`, `mount_on_app`, `__version__`). The SDK wheel exposes **`lumonox`** for instrumentation; with **`lumonox-sdk[stack]`**, the same module also exposes **`mount_on_app`** / **`create_app`** when the API is installed.

## GitHub Actions (trusted publishing)

1. On **PyPI** → **each** PyPI project (`lumonox` and `lumonox-sdk` are separate) → **Publishing** → **Add a pending trusted publisher** → choose **GitHub** as the publisher.
2. Fill fields so they **exactly** match what GitHub puts in the OIDC token (see [PyPI troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/)):
   - **Repository:** `sintimaski/lumonox` (owner + repo name, no `https://`).
   - **Workflow name:** the path **inside the repo**, e.g. `.github/workflows/publish-lumonox-pypi.yml` — **not** the SDK workflow unless you are configuring the `lumonox-sdk` project.
   - **Environment name:** `pypi` — required because both publish workflows set `jobs.<id>.environment.name: pypi`. If you leave this blank on PyPI while the workflow uses an environment, you get **`invalid-publisher`**. If you prefer **no** GitHub Environment, remove the `environment:` block from the workflow and register the publisher **without** an environment (then claims will not include `environment:pypi`).
3. On **GitHub** → **Settings → Environments** → create **`pypi`** and allow the default branch (or leave unrestricted) so the workflow can acquire `id-token: write` in that environment.
4. Merge to **`main`** with a **version bump** when you want a release (workflows skip upload if that version already exists on PyPI).

| Workflow file | PyPI project | Publisher must use this workflow path |
|----------------|--------------|----------------------------------------|
| [`.github/workflows/publish-lumonox-pypi.yml`](../../.github/workflows/publish-lumonox-pypi.yml) | **`lumonox`** | `.github/workflows/publish-lumonox-pypi.yml` + environment **`pypi`** |
| [`.github/workflows/publish-lumonox-sdk-pypi.yml`](../../.github/workflows/publish-lumonox-sdk-pypi.yml) | **`lumonox-sdk`** | `.github/workflows/publish-lumonox-sdk-pypi.yml` + environment **`pypi`** |

### `invalid-publisher` / “no corresponding publisher”

If the action logs show **`invalid-publisher`** and a claim like:

`workflow_ref`: `sintimaski/lumonox/.github/workflows/publish-lumonox-pypi.yml@refs/heads/main`

`environment`: `pypi`

then **PyPI’s pending publisher for `lumonox` must list that exact workflow filename** (the API workflow is separate from the SDK one). A publisher registered only for `publish-lumonox-sdk-pypi.yml` **does not** satisfy uploads from `publish-lumonox-pypi.yml`.

**Fix:** On https://pypi.org/manage/project/lumonox/settings/publishing/ add **another** pending trusted publisher (or edit the existing one) with workflow **`.github/workflows/publish-lumonox-pypi.yml`** and environment **`pypi`**, save, then re-run the failed GitHub Action.

## Manual dry-run (local)

From repo root after `npm --prefix frontend run build`:

```bash
uv build backend -o dist/manual-pypi-test
ls dist/manual-pypi-test/lumonox-*-py3-none-any.whl
```

## Recent `lumonox` wheel notes (changelog-lite)

| Version | Highlights |
|---------|------------|
| **0.3.2** | Dashboard copy + UX trim across overview / diagnosis / logs / settings (north-star: five-second understanding); reusable `DismissibleCard` wrapper. Publish workflow builds the bundled dashboard same-origin so a plain self-host of the wheel serves the UI at any origin without cross-origin sign-in breakage. |
| **0.3.1** | Wheel auto-discovers its bundled dashboard UI: a plain `pip install lumonox` now mounts the dashboard at `/lumonox/ui/` without setting `LUMONOX_FRONTEND_STATIC_DIR`. Regression-tested in `scripts/lumonox_wheel_ui_smoke.sh`. |
| **0.3.0** | Frontend page audit gap closure (FE-page-audit Phases 0–3); OSS launch readiness (LICENSE, portfolio README). Backend-only release; SDK stays at 0.2.8. |
| **0.2.12** | `IngestEvent` validates `trace_id` / `span_id` / `parent_span_id` / `span_name` (paired with **`lumonox-sdk` 0.2.8** per-request trace context). Operator-health refinements: `critical` reserved for real data loss; retention-pressure row keyed off topology, not `JOBS_ENABLE_SCHEDULER`. **`lumonox-sdk[stack]`** floor bumped to **`lumonox>=0.2.12`**. |
| **0.2.11** | Alerts operator-health only flips to `degraded` after per-process thresholds (5 send failures or 10 URL-validation rejections). DB-coordinated outbound webhook pacing via new `alert_webhook_pacing` table (multi-replica safe). SDK unchanged. |
| **0.2.10** | Production-maturity batch (PROD-001 … PROD-012): operator pipeline health surface (`GET /dashboard/operator-health` + UI section); documented HA golden path + `validate_deployment_settings` `LUMONOX_DUCKDB_SINGLE_WRITER_PROFILE` enforcement; server-backed incident worksheet with share/redeem/list/autosave; alert lifecycle (mute / snooze / per-dispatch ack); outbound alert webhook URL validation + `ALERT_WEBHOOK_MIN_INTERVAL_SECONDS` pacing + metrics; release/git markers on Overview + Diagnosis charts; team bookmarks (`visibility` migration, RBAC); bounded request export (`GET /dashboard/requests/export`); Query Explorer curated templates; onboarding completion nudge. |
| **0.2.9** | Dashboard: **`correlation`** query scope end-to-end; **`GET /dashboard/requests?correlation_request_id=…`** includes correlated **`job`** rows; onboarding activation hints, diagnosis pivot bar (Overview / Diagnosis / Requests), SDK noise section in Settings, operator reliability callout + Settings anchor links; internal metric **`dashboard.query.correlation_scope_total`** and **`dashboard.workspace.onboarding_completed_total`**. |
| **0.2.7** | Dashboard log exploration is **HTTP-only** (`POST /dashboard/log-query/validate` and `POST /dashboard/log-query/execute`); the unused **`/dashboard/log-query/stream`** WebSocket placeholder is removed (live updates remain on **`/dashboard/updates`** when realtime is enabled). |
| **0.2.6** | API wheel ships **`lumonox/__init__.py`** (`create_app`, `mount_on_app`, `__version__`) plus **`lumonox_backend`**; **`lumonox-sdk[stack]`** requires **`lumonox>=0.2.6`** and exposes **`mount_on_app`** from the SDK-owned **`lumonox`** module. |
| **0.2.5** | PyPI: API wheel published as **`lumonox`** (distribution formerly documented as `lumonox-api`); `/health` `service` **`lumonox`**; **`lumonox-sdk[stack]`** requires **`lumonox>=0.2.5`**. |

## Governed docs

If you change supported install surfaces or security expectations, follow **`docs/DOCUMENTATION_GOVERNANCE.md`** for material spec updates.
