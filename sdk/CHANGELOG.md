# Changelog

All notable changes to the **`autopulse`** Python SDK are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for public API and packaging.

## [Unreleased]

### Security

- **Breaking / privacy:** `monitor()` now defaults `capture_headers` and `capture_query_params` to **off** unless enabled via kwargs or `AUTOPULSE_CAPTURE_HEADERS` / `AUTOPULSE_CAPTURE_QUERY_PARAMS`. Reduces accidental PII in events.
- **Embedded:** if `.env.autopulse` cannot be written, the SDK no longer falls back to a repo-known API key; it uses the generated key from the failed write attempt for that process and logs remediation steps.

### Fixed

- Middleware tests using a stub dispatcher no longer assume a private `_send_enabled` attribute on arbitrary dispatcher objects (`getattr` fallback).
