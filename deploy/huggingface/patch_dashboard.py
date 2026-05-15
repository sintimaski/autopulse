#!/usr/bin/env python3
"""Build-time patches to the published ``lumonox`` wheel's bundled dashboard, for the demo.

Both fixes exist because the demo serves the wheel's *production* dashboard build from a
public HTTPS origin — a case the published build is not configured for:

1. **API origin.** ``lumonox`` wheels through 0.3.1 inline
   ``NEXT_PUBLIC_LUMONOX_API_BASE_URL=http://127.0.0.1:8000`` into the static JS (see the
   repo's ``publish-lumonox-pypi.yml``), so the UI calls that absolute origin. Served over
   HTTPS from any non-localhost origin the browser blocks that fetch (mixed content) and
   sign-in fails with "Could not reach the server to verify your session". Rewriting the
   baked-in origin to empty makes ``buildApiUrl()`` emit same-origin ``/dashboard/...`` paths.
   No-op once a wheel built with a same-origin base is pinned.

2. **Auto sign-in.** The demo runs a shared ``demo@lumonox.dev`` account with
   ``DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true``, but a *production*-built UI only
   surfaces the dev magic link when ``NODE_ENV=development`` (correct behaviour — production
   UIs must not leak magic-link tokens). So inject a tiny script into the dashboard HTML
   that completes the documented magic-link flow automatically the first time an
   unauthenticated visitor lands. It uses same-origin API paths only.

Run at image build time (see ``Dockerfile``); both steps are idempotent.
"""

from __future__ import annotations

import os
import pathlib

import lumonox_backend


def _resolve_static_dir() -> pathlib.Path:
    """Where the patcher writes — the runtime-served dashboard.

    Honors ``LUMONOX_FRONTEND_STATIC_DIR`` when set (the demo's multi-stage Dockerfile
    points this at the freshly-built export), otherwise falls back to the wheel's
    bundled ``dashboard_static`` next to ``lumonox_backend``.
    """
    override = (os.getenv("LUMONOX_FRONTEND_STATIC_DIR") or "").strip()
    if override:
        return pathlib.Path(override)
    return pathlib.Path(lumonox_backend.__file__).parent / "dashboard_static"


_STATIC = _resolve_static_dir()

_BAKED_IN_API_ORIGIN = "http://127.0.0.1:8000"

_AUTOLOGIN_MARKER = "lx-demo-autologin"
_AUTOLOGIN_SCRIPT = """<script id="lx-demo-autologin">
(function () {
  // Lumonox demo auto sign-in. Every visitor shares the demo@lumonox.dev account; the
  // published production UI does not surface the dev magic link, so complete the
  // documented magic-link flow here. Same-origin API paths only.
  var EMAIL = "demo@lumonox.dev";
  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }
  (async function () {
    try {
      var session = await fetch("/dashboard/auth/session", { credentials: "include" })
        .then(function (r) { return r.json(); });
      if (session && session.authenticated) return; // already signed in — let the SPA boot
      if (sessionStorage.getItem("lx-demo-signin-tried")) return; // never loop on failure
      sessionStorage.setItem("lx-demo-signin-tried", "1");
      var overlay = document.createElement("div");
      overlay.style.cssText =
        "position:fixed;inset:0;z-index:99999;display:flex;align-items:center;" +
        "justify-content:center;background:#0f172a;color:#e2e8f0;" +
        "font:14px/1.5 system-ui,-apple-system,sans-serif";
      overlay.textContent = "Signing you into the Lumonox demo…";
      (document.body || document.documentElement).appendChild(overlay);
      var requested = await post("/dashboard/auth/magic-link/request", { email: EMAIL })
        .then(function (r) { return r.json(); });
      if (requested && requested.dev_token) {
        var verified = await post("/dashboard/auth/magic-link/verify", {
          token: requested.dev_token,
        });
        if (verified.ok) {
          await verified.text().catch(function () {}); // drain before navigating
          location.reload();
          return;
        }
      }
      overlay.remove(); // fall through to the normal sign-in screen
    } catch (e) {
      /* fall through to the normal sign-in screen */
    }
  })();
})();
</script>"""


def _rewrite_api_origin() -> int:
    """Rewrite the baked-in absolute API origin to empty (same-origin)."""
    patched = 0
    for js in _STATIC.rglob("*.js"):
        text = js.read_text(encoding="utf-8")
        if _BAKED_IN_API_ORIGIN in text:
            js.write_text(text.replace(_BAKED_IN_API_ORIGIN, ""), encoding="utf-8")
            patched += 1
    return patched


def _inject_autologin() -> int:
    """Inject the auto sign-in script before ``</head>`` in every dashboard HTML file."""
    injected = 0
    for html in _STATIC.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        if _AUTOLOGIN_MARKER in text or "</head>" not in text:
            continue
        html.write_text(text.replace("</head>", _AUTOLOGIN_SCRIPT + "</head>", 1), encoding="utf-8")
        injected += 1
    return injected


def main() -> None:
    index_html = _STATIC / "index.html"
    if not index_html.is_file():
        raise SystemExit(f"[patch_dashboard] dashboard_static not found at {_STATIC}")
    rewritten = _rewrite_api_origin()
    injected = _inject_autologin()
    if _AUTOLOGIN_MARKER not in index_html.read_text(encoding="utf-8"):
        raise SystemExit("[patch_dashboard] failed to inject auto sign-in into index.html")
    print(
        f"[patch_dashboard] rewrote API origin in {rewritten} JS file(s); "
        f"injected auto sign-in into {injected} HTML file(s)"
    )


if __name__ == "__main__":
    main()
