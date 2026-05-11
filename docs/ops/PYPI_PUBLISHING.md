# PyPI publishing (Lumonox)

Canonical **install names** on PyPI:

| Distribution | PyPI project | One-line install | What you get |
|----------------|--------------|------------------|----------------|
| **API + bundled dashboard** | [**lumonox-api**](https://pypi.org/project/lumonox-api/) | `pip install lumonox-api` | FastAPI ingest + dashboard APIs + static UI under `/lumonox/ui/` (import **`lumonox_backend`**) |
| **FastAPI SDK only** | [**lumonox-sdk**](https://pypi.org/project/lumonox-sdk/) | `pip install lumonox-sdk` | `from lumonox import lumonox` — send-only instrumentation |
| **API + UI + SDK** | same two projects | `pip install "lumonox-sdk[stack]"` | Installs **`lumonox-api`** as a dependency of the SDK extra |

## Project pages (links)

- **API + UI wheel:** https://pypi.org/project/lumonox-api/
- **SDK wheel:** https://pypi.org/project/lumonox-sdk/

Until the first upload succeeds, those pages may show “project not found” or an empty project—create the projects on PyPI and run the GitHub Actions workflows below.

## PyPI naming

Lumonox ships as **`lumonox-api`** and **`lumonox-sdk`** on PyPI. Shorter generic names are often already claimed by unrelated projects, so these explicit names keep installs unambiguous.

## GitHub Actions (trusted publishing)

1. On **PyPI** → **each** PyPI project (`lumonox-api` and `lumonox-sdk` are separate) → **Publishing** → **Add a pending trusted publisher** → choose **GitHub** as the publisher.
2. Fill fields so they **exactly** match what GitHub puts in the OIDC token (see [PyPI troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/)):
   - **Repository:** `sintimaski/lumonox` (owner + repo name, no `https://`).
   - **Workflow name:** the path **inside the repo**, e.g. `.github/workflows/publish-lumonox-api-pypi.yml` — **not** the SDK workflow unless you are configuring the `lumonox-sdk` project.
   - **Environment name:** `pypi` — required because both publish workflows set `jobs.<id>.environment.name: pypi`. If you leave this blank on PyPI while the workflow uses an environment, you get **`invalid-publisher`**. If you prefer **no** GitHub Environment, remove the `environment:` block from the workflow and register the publisher **without** an environment (then claims will not include `environment:pypi`).
3. On **GitHub** → **Settings → Environments** → create **`pypi`** and allow the default branch (or leave unrestricted) so the workflow can acquire `id-token: write` in that environment.
4. Merge to **`main`** with a **version bump** when you want a release (workflows skip upload if that version already exists on PyPI).

| Workflow file | PyPI project | Publisher must use this workflow path |
|----------------|--------------|----------------------------------------|
| [`.github/workflows/publish-lumonox-api-pypi.yml`](../../.github/workflows/publish-lumonox-api-pypi.yml) | **`lumonox-api`** | `.github/workflows/publish-lumonox-api-pypi.yml` + environment **`pypi`** |
| [`.github/workflows/publish-lumonox-sdk-pypi.yml`](../../.github/workflows/publish-lumonox-sdk-pypi.yml) | **`lumonox-sdk`** | `.github/workflows/publish-lumonox-sdk-pypi.yml` + environment **`pypi`** |

### `invalid-publisher` / “no corresponding publisher”

If the action logs show **`invalid-publisher`** and a claim like:

`workflow_ref`: `sintimaski/lumonox/.github/workflows/publish-lumonox-api-pypi.yml@refs/heads/main`

`environment`: `pypi`

then **PyPI’s pending publisher for `lumonox-api` must list that exact workflow filename** (the API workflow was added/renameed separately from the SDK one). A publisher registered only for `publish-lumonox-sdk-pypi.yml` **does not** satisfy uploads from `publish-lumonox-api-pypi.yml`.

**Fix:** On https://pypi.org/manage/project/lumonox-api/settings/publishing/ add **another** pending trusted publisher (or edit the existing one) with workflow **`.github/workflows/publish-lumonox-api-pypi.yml`** and environment **`pypi`**, save, then re-run the failed GitHub Action.

## Manual dry-run (local)

From repo root after `npm --prefix frontend run build`:

```bash
uv build backend -o dist/manual-pypi-test
ls dist/manual-pypi-test/lumonox_api-*-py3-none-any.whl
```

## Recent `lumonox-api` wheel notes (changelog-lite)

| Version | Highlights |
|---------|------------|
| **0.2.4** | Developer/CI: `uv run pytest` runs backend DB integration tests against an ephemeral session SQLite DB when `BACKEND_TEST_DATABASE_URL` is unset; CI sqlite/postgres env aligned with that harness (see `backend/tests/conftest.py`, `backend/README.md`). |
| **0.2.3** | Dashboard home: overview-derived window snapshot widgets (two-row layout: KPI cards, then donut + bar); infra insights panel open by default in phased UI; widgets slice enabled for filtered dashboard scopes. |
| **0.2.2** | Dashboard default scope: in-memory query snapshot refreshed from ingest deltas (fewer heavy DuckDB reads on poll); optional realtime WebSocket path behind flags; rolling-window chart alignment fixes for overview. |

## Governed docs

If you change supported install surfaces or security expectations, follow **`docs/DOCUMENTATION_GOVERNANCE.md`** for material spec updates.
