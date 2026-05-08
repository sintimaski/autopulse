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

1. On **PyPI** → each project → **Publishing** → **Add a pending publisher** (GitHub → this repository → workflow file → optional `pypi` environment).
2. On **GitHub** → **Settings → Environments** → create **`pypi`** if the workflow uses it for protection rules.
3. Merge to **`main`** with a **version bump** when you want a release (workflows skip upload if that version already exists on PyPI).

| Workflow file | Publishes |
|---------------|-----------|
| [`.github/workflows/publish-autopulse-api-pypi.yml`](../../.github/workflows/publish-autopulse-api-pypi.yml) | **`autopulse-api`** — builds `frontend/out`, then `uv build backend` |
| [`.github/workflows/publish-autopulse-sdk-pypi.yml`](../../.github/workflows/publish-autopulse-sdk-pypi.yml) | **`autopulse-sdk`** |

## Manual dry-run (local)

From repo root after `npm --prefix frontend run build`:

```bash
uv build backend -o dist/manual-pypi-test
ls dist/manual-pypi-test/autopulse_api-*-py3-none-any.whl
```

## Governed docs

If you change supported install surfaces or security expectations, follow **`docs/DOCUMENTATION_GOVERNANCE.md`** for material spec updates.
