#!/usr/bin/env bash
# Rebuild the Next static export and copy it into the Python package tree so `autopulse(app)`
# serves the real dashboard without AUTOPULSE_FRONTEND_STATIC_DIR or a separate frontend install.
# Destination: ``sdk/src/autopulse/ui`` in the monorepo, or ``src/autopulse/ui`` in an sdist tree.
#
# Pre-commit / incremental dev: set AUTOPULSE_BUNDLE_SKIP_NPM_CI=1 to skip ``npm ci`` when
# ``frontend/node_modules`` already exists (still runs ``npm run build``).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Monorepo checkout uses ``sdk/src/autopulse/``; sdist / flat trees use ``src/autopulse/``.
if [[ -d "$ROOT/sdk/src/autopulse" ]]; then
  UI_DEST="$ROOT/sdk/src/autopulse/ui"
elif [[ -d "$ROOT/src/autopulse" ]]; then
  UI_DEST="$ROOT/src/autopulse/ui"
else
  echo "bundle_embedded_dashboard_ui: cannot find autopulse package under $ROOT (expected sdk/src/autopulse or src/autopulse)" >&2
  exit 1
fi
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm ci
elif [[ "${AUTOPULSE_BUNDLE_SKIP_NPM_CI:-}" == "1" ]]; then
  :
else
  npm ci
fi
npm run build
readme_backup=""
if [[ -f "$UI_DEST/README.md" ]]; then
  readme_backup="$(mktemp)"
  cp "$UI_DEST/README.md" "$readme_backup"
fi
rm -rf "$UI_DEST"
mkdir -p "$UI_DEST"
rsync -a "$ROOT/frontend/out/" "$UI_DEST/"
if [[ -n "${readme_backup}" ]] && [[ -f "${readme_backup}" ]]; then
  mv "${readme_backup}" "$UI_DEST/README.md"
fi
# Drop Next export `*.txt` metadata (RSC route manifests); not needed for static HTML+assets.
find "$UI_DEST" -type f -name '*.txt' -delete
echo "Bundled UI -> $UI_DEST ($(du -sh "$UI_DEST" | cut -f1))"
