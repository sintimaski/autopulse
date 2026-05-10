.PHONY: help setup sync frontend-install lint typecheck test check check-python check-python-ci check-frontend build release-gates

help:
	@echo "Lumonox root commands"
	@echo "  make setup           # install backend + frontend dependencies"
	@echo "  make check-python    # ruff/mypy/bandit/python tests"
	@echo "  make check-python-ci # CI-equivalent backend gate (requires Postgres BACKEND_TEST_DATABASE_URL)"
	@echo "  make check-frontend  # frontend lint/typecheck/test/build"
	@echo "  make check           # python + frontend checks"
	@echo "  make release-gates   # full release gate script"
	@echo "  make test            # alias for check"

sync:
	uv sync --group dev

frontend-install:
	npm --prefix frontend ci

setup: sync frontend-install

lint:
	uv run ruff check .
	uv run ruff format --check .
	npm --prefix frontend run lint

typecheck:
	uv run mypy
	npm --prefix frontend run typecheck

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

build:
	npm --prefix frontend run build

release-gates:
	bash ./scripts/release_gates.sh
