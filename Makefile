.PHONY: help setup sync frontend-install install \
	lint typecheck format \
	test test-py test-fe test-all \
	check check-python check-python-ci check-frontend \
	ci \
	build \
	synthetic-stack synthetic-load stack load \
	release-gates

# Default: quick orientation (grouped for DX).
help:
	@echo "Lumonox — common targets"
	@echo ""
	@echo "Setup"
	@echo "  make setup | make install   # uv sync + npm ci (frontend)"
	@echo ""
	@echo "Synthetic local stack (DuckDB + backend :8000 + sample app :8001; FE build is always first)"
	@echo "  make synthetic-stack | make stack   # ./scripts/run_synthetic_stack.sh"
	@echo "  make synthetic-load  | make load   # traffic generator (run with stack already up)"
	@echo ""
	@echo "Tests (no linters)"
	@echo "  make test-all    # pytest + frontend unit tests"
	@echo "  make test-py     # uv run pytest"
	@echo "  make test-fe     # npm --prefix frontend run test"
	@echo ""
	@echo "Lint + tests (fast local feedback)"
	@echo "  make check           # Python + frontend gates (see targets below)"
	@echo "  make check-python    # ruff, mypy, bandit, pytest"
	@echo "  make check-frontend  # lint, typecheck, vitest, next build"
	@echo "  make format          # apply Ruff formatting (not CI-enforced autofix for JS)"
	@echo ""
	@echo "CI parity (mirrors .github/workflows/ci.yml; see scripts/ci_local.sh)"
	@echo "  make ci              # SQLite job + frontend job (+ backend wheel static check)"
	@echo "    Optional: LUMONOX_CI_POSTGRES=1 with BACKEND_TEST_DATABASE_URL=postgresql+asyncpg://..."
	@echo "    Optional: LUMONOX_CI_E2E=1  (Playwright; install browsers once: cd frontend && npx playwright install --with-deps chromium)"
	@echo ""
	@echo "Other"
	@echo "  make test            # alias for make check (historical)"
	@echo "  make check-python-ci # stricter backend gate; requires Postgres BACKEND_TEST_DATABASE_URL"
	@echo "  make release-gates   # scripts/release_gates.sh (release-oriented; not identical to make ci)"
	@echo "  make build           # npm --prefix frontend run build only"

sync:
	uv sync --group dev

frontend-install:
	npm --prefix frontend ci

setup: sync frontend-install

install: setup

lint:
	uv run ruff check .
	uv run ruff format --check .
	npm --prefix frontend run lint

typecheck:
	uv run mypy
	npm --prefix frontend run typecheck

format:
	uv run ruff format .

check-python:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run bandit -c pyproject.toml -r sdk/src/lumonox backend/src/lumonox_backend
	uv run pytest

check-python-ci:
	@if [ -z "$(BACKEND_TEST_DATABASE_URL)" ]; then \
		echo "BACKEND_TEST_DATABASE_URL is required for check-python-ci."; \
		echo "Use a Postgres URL (for example: postgresql+asyncpg://lumonox:lumonox@127.0.0.1:5432/lumonox_ci)."; \
		exit 1; \
	fi
	@case "$(BACKEND_TEST_DATABASE_URL)" in \
		postgresql*) ;; \
		*) \
			echo "check-python-ci requires BACKEND_TEST_DATABASE_URL to use postgresql+asyncpg://..."; \
			exit 1; \
			;; \
	esac
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run bandit -c pyproject.toml -r sdk/src/lumonox backend/src/lumonox_backend
	uv run pip-audit
	uv run pytest --cov=lumonox --cov=lumonox_backend --cov-report=term-missing
	uv build --package lumonox-sdk --wheel -o packaging-dist && rm -rf packaging-dist
	uv run python -m lumonox_backend.jobs alerts-once >/dev/null
	uv run python -m lumonox_backend.jobs retention-once >/dev/null
	uv run pytest backend/tests/test_ingest.py::test_ingest_idempotency_key_replays_accepted_without_duplicate_events -q
	uv run pytest backend/tests -q

check-frontend:
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck
	npm --prefix frontend run test
	npm --prefix frontend run build

check: check-python check-frontend

test: check

test-py:
	uv run pytest

test-fe:
	npm --prefix frontend run test

test-all: test-py test-fe

ci:
	bash ./scripts/ci_local.sh

synthetic-stack:
	bash ./scripts/run_synthetic_stack.sh

synthetic-load:
	bash ./scripts/examples/synthetic_load_demo.sh

stack: synthetic-stack

load: synthetic-load

build:
	npm --prefix frontend run build

release-gates:
	bash ./scripts/release_gates.sh
