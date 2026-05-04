#!/usr/bin/env bash
# Rebuild the Next static export and copy it into the SDK wheel tree so `autopulse(app)`
# serves the real dashboard without AUTOPULSE_FRONTEND_STATIC_DIR or a separate frontend install.
#
# Pre-commit / incremental dev: set AUTOPULSE_BUNDLE_SKIP_NPM_CI=1 to skip ``npm ci`` when
# ``frontend/node_modules`` already exists (still runs ``npm run build``).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm ci
elif [[ "${AUTOPULSE_BUNDLE_SKIP_NPM_CI:-}" == "1" ]]; then
  :
else
  npm ci
fi
npm run build
rm -rf "$ROOT/sdk/src/autopulse/ui"
mkdir -p "$ROOT/sdk/src/autopulse/ui"
rsync -a "$ROOT/frontend/out/" "$ROOT/sdk/src/autopulse/ui/"
# Drop Next export `*.txt` metadata (RSC route manifests); not needed for static HTML+assets.
find "$ROOT/sdk/src/autopulse/ui" -type f -name '*.txt' -delete
echo "Bundled UI -> sdk/src/autopulse/ui ($(du -sh "$ROOT/sdk/src/autopulse/ui" | cut -f1))"
