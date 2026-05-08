# PyPI publishing (AutoPulse)

Canonical **install names** on PyPI:

| Distribution | PyPI project | One-line install | What you get |
|----------------|--------------|------------------|----------------|
| **API + bundled dashboard** | [**autopulse-api**](https://pypi.org/project/autopulse-api/) | `pip install autopulse-api` | FastAPI ingest + dashboard APIs + static UI under `/autopulse/ui/` (import **`autopulse_backend`**) |
| **FastAPI SDK only** | [**autopulse-sdk**](https://pypi.org/project/autopulse-sdk/) | `pip install autopulse-sdk` | `from autopulse import autopulse` — send-only instrumentation |
| **API + UI + SDK** | same two projects | `pip install "autopulse-sdk[stack]"` | Installs **`autopulse-api`** as a dependency of the SDK extra |

## Project pages (links)

- **API + UI wheel:** https://pypi.org/project/autopulse-api/
- **SDK wheel:** https://pypi.org/project/autopulse-sdk/

Until the first upload succeeds, those pages may show “project not found” or an empty project—create the projects on PyPI and run the GitHub Actions workflows below.

## Name note: `autopulse` on PyPI

The name **`autopulse`** on PyPI is **already taken** by an unrelated package (see https://pypi.org/project/autopulse/). This product therefore publishes the server stack as **`autopulse-api`**.

## GitHub Actions (trusted publishing)

1. On **PyPI** → **each** PyPI project (`autopulse-api` and `autopulse-sdk` are separate) → **Publishing** → **Add a pending trusted publisher** → choose **GitHub** as the publisher.
2. Fill fields so they **exactly** match what GitHub puts in the OIDC token (see [PyPI troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/)):
   - **Repository:** `sintimaski/autopulse` (owner + repo name, no `https://`).
   - **Workflow name:** the path **inside the repo**, e.g. `.github/workflows/publish-autopulse-api-pypi.yml` — **not** the SDK workflow unless you are configuring the `autopulse-sdk` project.
   - **Environment name:** `pypi` — required because both publish workflows set `jobs.<id>.environment.name: pypi`. If you leave this blank on PyPI while the workflow uses an environment, you get **`invalid-publisher`**. If you prefer **no** GitHub Environment, remove the `environment:` block from the workflow and register the publisher **without** an environment (then claims will not include `environment:pypi`).
3. On **GitHub** → **Settings → Environments** → create **`pypi`** and allow the default branch (or leave unrestricted) so the workflow can acquire `id-token: write` in that environment.
4. Merge to **`main`** with a **version bump** when you want a release (workflows skip upload if that version already exists on PyPI).

| Workflow file | PyPI project | Publisher must use this workflow path |
|----------------|--------------|----------------------------------------|
| [`.github/workflows/publish-autopulse-api-pypi.yml`](../../.github/workflows/publish-autopulse-api-pypi.yml) | **`autopulse-api`** | `.github/workflows/publish-autopulse-api-pypi.yml` + environment **`pypi`** |
| [`.github/workflows/publish-autopulse-sdk-pypi.yml`](../../.github/workflows/publish-autopulse-sdk-pypi.yml) | **`autopulse-sdk`** | `.github/workflows/publish-autopulse-sdk-pypi.yml` + environment **`pypi`** |

### `invalid-publisher` / “no corresponding publisher”

If the action logs show **`invalid-publisher`** and a claim like:

`workflow_ref`: `sintimaski/autopulse/.github/workflows/publish-autopulse-api-pypi.yml@refs/heads/main`

`environment`: `pypi`

then **PyPI’s pending publisher for `autopulse-api` must list that exact workflow filename** (the API workflow was added/renameed separately from the SDK one). A publisher registered only for `publish-autopulse-sdk-pypi.yml` **does not** satisfy uploads from `publish-autopulse-api-pypi.yml`.

**Fix:** On https://pypi.org/manage/project/autopulse-api/settings/publishing/ add **another** pending trusted publisher (or edit the existing one) with workflow **`.github/workflows/publish-autopulse-api-pypi.yml`** and environment **`pypi`**, save, then re-run the failed GitHub Action.

## Manual dry-run (local)

From repo root after `npm --prefix frontend run build`:

```bash
uv build backend -o dist/manual-pypi-test
ls dist/manual-pypi-test/autopulse_api-*-py3-none-any.whl
```

## Governed docs

If you change supported install surfaces or security expectations, follow **`docs/DOCUMENTATION_GOVERNANCE.md`** for material spec updates.
