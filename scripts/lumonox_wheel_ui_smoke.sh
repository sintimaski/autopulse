#!/usr/bin/env bash
# Regression smoke for the bug where the published ``lumonox`` wheel could not
# auto-discover its own bundled dashboard UI: the Next export ships at
# ``lumonox_backend/dashboard_static/`` but the runtime looked one directory too
# deep (under ``dashboard/``), so ``pip install lumonox`` + run served no UI
# unless ``LUMONOX_FRONTEND_STATIC_DIR`` was set by hand.
#
# Builds the full ``lumonox`` wheel (the sdist ``force-include`` bundles
# ``frontend/out``), installs it into a throwaway venv, runs the API from a
# directory OUTSIDE the repo -- so the monorepo ``frontend/out`` fallback cannot
# mask the bundled-path lookup -- and asserts the dashboard UI actually mounts.
#
# Requires ``frontend/out`` to exist (run ``npm run build`` in ``frontend/`` first).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/lumonox-wheel-ui-smoke.XXXXXX")"
UVICORN_PID=""

on_exit() {
  if [[ -n "${UVICORN_PID}" ]] && kill -0 "${UVICORN_PID}" 2>/dev/null; then
    kill "${UVICORN_PID}" 2>/dev/null || true
    wait "${UVICORN_PID}" 2>/dev/null || true
  fi
  rm -rf "${WORKDIR}"
}
trap on_exit EXIT

command -v uv >/dev/null 2>&1 || { echo "error: uv is required on PATH" >&2; exit 1; }

if [[ ! -f "${ROOT}/frontend/out/index.html" ]]; then
  echo "error: ${ROOT}/frontend/out/index.html missing -- run 'npm run build' in frontend/ first" >&2
  exit 1
fi

DIST="${WORKDIR}/dist"
VENV="${WORKDIR}/venv"
RUNDIR="${WORKDIR}/run"  # deliberately outside the repo: defeats the frontend/out fallback
mkdir -p "${RUNDIR}"

uv build "${ROOT}/backend" --out-dir "${DIST}"
WHL=""
for _cand in "${DIST}"/lumonox-*-py3-none-any.whl; do
  if [[ -f "${_cand}" ]]; then
    WHL="${_cand}"
    break
  fi
done
[[ -n "${WHL}" ]] || { echo "error: no lumonox wheel built under ${DIST}" >&2; exit 1; }

# The export must be bundled at the package root -- where the runtime looks.
# Capture the listing first: piping ``unzip -l`` straight into ``grep -q`` makes
# ``grep`` close the pipe on the first match, so ``unzip`` takes SIGPIPE and
# ``set -o pipefail`` reports a false failure.
wheel_listing="$(unzip -l "${WHL}")"
grep -Fq "lumonox_backend/dashboard_static/index.html" <<<"${wheel_listing}" || {
  echo "error: wheel is missing lumonox_backend/dashboard_static/index.html" >&2
  exit 1
}

uv venv -p 3.12 "${VENV}"
uv pip install --python "${VENV}" "${WHL}"

PORT="$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")"

cd "${RUNDIR}"
DATABASE_URL="sqlite+aiosqlite:///${WORKDIR}/smoke.db" \
LUMONOX_DATA_DIR="${WORKDIR}/lxdata" \
DASHBOARD_AUTH_ENABLED=false \
INGEST_REQUIRE_HTTPS=false \
  "${VENV}/bin/uvicorn" lumonox_backend.main:app \
    --host 127.0.0.1 --port "${PORT}" --log-level warning >"${WORKDIR}/uvicorn.log" 2>&1 &
UVICORN_PID=$!

ready=""
for _ in $(seq 1 80); do
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.25
done
[[ -n "${ready}" ]] || {
  echo "error: backend did not become ready" >&2
  cat "${WORKDIR}/uvicorn.log" >&2
  exit 1
}

ui_code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/lumonox/ui/")"
root_code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/")"

if [[ "${ui_code}" != "200" ]]; then
  echo "error: bundled dashboard UI did not mount -- GET /lumonox/ui/ -> ${ui_code} (expected 200)." >&2
  echo "       the wheel bundles the export but the runtime could not discover it." >&2
  cat "${WORKDIR}/uvicorn.log" >&2
  exit 1
fi
if [[ "${root_code}" != "307" && "${root_code}" != "200" ]]; then
  echo "error: GET / -> ${root_code} (expected 307 redirect to /lumonox/ui/)" >&2
  exit 1
fi

echo "lumonox wheel UI smoke: ok (/lumonox/ui/ -> ${ui_code}, / -> ${root_code})"
