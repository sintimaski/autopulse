# Lumonox PyPI release checklist (dual packages)

The repository ships **two** PyPI distributions:

| PyPI project | Path | Purpose |
| --- | --- | --- |
| `lumonox` | `backend/pyproject.toml` | FastAPI app + ingest + **bundled** static dashboard (`lumonox_backend/dashboard_static/`) |
| `lumonox-sdk` | `sdk/pyproject.toml` | Import package **`lumonox`** for app instrumentation (`pip install lumonox-sdk`); FastAPI middleware + opt-in Django adapter via the `[django]` extra |

Workflows: `.github/workflows/publish-lumonox-pypi.yml` and `.github/workflows/publish-lumonox-sdk-pypi.yml`.

## Before merging a release PR

1. [ ] **CI green** on the PR (`ci.yml` + optional `release-gates.yml`).
2. [ ] **Version bump** in the correct `pyproject.toml` only for what you intend to ship.
3. [ ] **Compatibility note:** `sdk/pyproject.toml` optional extra `[stack]` pins a `lumonox` floor; bump SDK when API wheel requirements change (see `sdk/README.md`).
4. [ ] **Changelog** entry in `sdk/CHANGELOG.md` and/or backend release notes as appropriate.

## `lumonox` (API wheel)

1. [ ] Bump `version` in `backend/pyproject.toml`.
2. [ ] Ensure `frontend/` static export builds (`npm --prefix frontend ci && npm --prefix frontend run build`) — the publish workflow runs this automatically.
3. [ ] Merge to `main`; workflow skips upload if that version already exists on PyPI.
4. [ ] Confirm PyPI shows the new version and wheel contains `lumonox_backend/dashboard_static/index.html` (workflow verifies).

## `lumonox-sdk`

1. [ ] Bump `version` in `sdk/pyproject.toml`.
2. [ ] Merge to `main`; workflow skips upload if that version already exists on PyPI.
3. [ ] Confirm wheel lists `lumonox/__init__.py` (workflow verifies).

## Evidence bundle (maintainer habit)

- Link the successful GitHub Actions run for each published artifact.
- Paste or attach `uv build …` / `unzip -l` smoke output if debugging packaging locally.

## Rollback

- **PyPI:** yank or deprecate the bad release on PyPI; publish a patch version with the fix (files are immutable).
- **Users:** document `pip install lumonox==x.y.z` / `lumonox-sdk==x.y.z` pins in incident notes.
