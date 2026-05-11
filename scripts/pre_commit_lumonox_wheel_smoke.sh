#!/usr/bin/env bash
# Build the ``lumonox`` wheel, install into a throwaway venv under /tmp, and smoke-test
# ``from lumonox import mount_on_app`` + ``GET /lumonox/health`` (matches PyPI consumer layout).
#
# Uses ``uv build --wheel`` only (no sdist). Full ``uv build`` runs ``build_sdist`` first, which
# applies hatch ``sdist.force-include`` for ``../frontend/out``; that path is absent on CI jobs
# that do not build the Next export, so wheel-only keeps this check self-contained.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/lumonox-wheel-smoke.XXXXXX")"
UVICORN_PID=""

on_exit() {
  if [[ -n "${UVICORN_PID}" ]] && kill -0 "${UVICORN_PID}" 2>/dev/null; then
    kill "${UVICORN_PID}" 2>/dev/null || true
    wait "${UVICORN_PID}" 2>/dev/null || true
  fi
  rm -rf "${WORKDIR}"
}
trap on_exit EXIT

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required on PATH" >&2
  exit 1
fi

DIST="${WORKDIR}/dist"
VENV="${WORKDIR}/venv"

uv venv -p 3.12 "${VENV}"
# shellcheck disable=SC1090
source "${VENV}/bin/activate"

uv build "${ROOT}/backend" --wheel -o "${DIST}"
WHL=""
for _cand in "${DIST}"/lumonox-*-py3-none-any.whl; do
  if [[ -f "${_cand}" ]]; then
    WHL="${_cand}"
    break
  fi
done
if [[ -z "${WHL}" ]]; then
  echo "error: no lumonox-*-py3-none-any.whl under ${DIST}" >&2
  exit 1
fi

uv pip install "${WHL}"

export LUMONOX_ENV="${LUMONOX_ENV:-development}"
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///${WORKDIR}/smoke.db}"
export LUMONOX_DATA_DIR="${WORKDIR}/lxdata"
export INGEST_REQUIRE_HTTPS="${INGEST_REQUIRE_HTTPS:-false}"
export DASHBOARD_AUTH_ENABLED="${DASHBOARD_AUTH_ENABLED:-false}"
mkdir -p "${LUMONOX_DATA_DIR}"

APP_PY="${WORKDIR}/host_app.py"
cat >"${APP_PY}" <<'PY'
from fastapi import FastAPI
from lumonox import mount_on_app

app = FastAPI()


@app.get("/host-ping")
def host_ping() -> dict[str, str]:
    return {"from": "host"}


mount_on_app(app, prefix="/lumonox")
PY

(
  cd "${WORKDIR}"
  export PYTHONPATH="${WORKDIR}${PYTHONPATH:+:${PYTHONPATH}}"
  python - <<'PY'
import importlib

import lumonox

for name in ("create_app", "mount_on_app", "__version__"):
    assert hasattr(lumonox, name), f"missing lumonox.{name}"

print("lumonox import ok:", importlib.metadata.version("lumonox"))
PY
)

PORT_FILE="${WORKDIR}/port.txt"
python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); open(r'''${PORT_FILE}''', 'w').write(str(s.getsockname()[1])); s.close()"
PORT="$(cat "${PORT_FILE}")"

cd "${WORKDIR}"
export PYTHONPATH="${WORKDIR}${PYTHONPATH:+:${PYTHONPATH}}"
uvicorn host_app:app --host 127.0.0.1 --port "${PORT}" --log-level warning >/dev/null 2>&1 &
UVICORN_PID=$!
cd "${ROOT}" || true

ok_health=""
for _ in $(seq 1 50); do
  ok_health="$(curl -sf "http://127.0.0.1:${PORT}/lumonox/health" || true)"
  if [[ "${ok_health}" == '{"status":"ok"}' ]]; then
    break
  fi
  sleep 0.15
done
[[ "${ok_health}" == '{"status":"ok"}' ]] || {
  echo "error: /lumonox/health got: ${ok_health}" >&2
  exit 1
}
[[ "$(curl -sf "http://127.0.0.1:${PORT}/host-ping")" == '{"from":"host"}' ]] || {
  echo "error: /host-ping mismatch" >&2
  exit 1
}

echo "lumonox wheel smoke (uvicorn): ok"
