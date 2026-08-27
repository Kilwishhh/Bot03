# MK TRADER — common commands
#
# The Python toolchain is expected to be in the active venv (`source .venv/bin/activate`).
# On Windows with git-bash, use `make` from the project root.

.PHONY: help install test test-quiet lint smoke release-check audit-deps docker-build docker-run docker-down ci-local clean

help:
	@echo "MK TRADER Makefile"
	@echo ""
	@echo "  install           Install the package + dev/test/api extras into the active venv"
	@echo "  test              Run the full pytest suite"
	@echo "  test-quiet        Run pytest with minimal output"
	@echo "  lint              Run ruff on app/, tests/, scripts/"
	@echo "  smoke             Run the offline smoke (no network)"
	@echo "  release-check     Run all release-readiness checks (lint + tests + smoke + audits)"
	@echo "  audit-deps        Check installed deps are within pyproject.toml upper bounds"
	@echo "  docker-build      Build the Docker image"
	@echo "  docker-run        Run the API in paper mode (port 8000)"
	@echo "  docker-down       Stop the running container"
	@echo "  ci-local          Mimic what CI does, locally (lint + tests + smoke + release-check)"
	@echo "  clean             Remove __pycache__, .pyc, .pytest_cache"

install:
	pip install -e ".[test,api,dev]"

test:
	pytest

test-quiet:
	pytest -q

lint:
	ruff check app tests scripts

smoke:
	python scripts/check_app.py

release-check:
	python scripts/release_check.py

audit-deps:
	python scripts/audit_dependencies.py

docker-build:
	docker build -t mktrader:dev -f Dockerfile .

docker-run: docker-build
	docker run -d --name mktrader-dev -p 8000:8000 \
		-e TRADING_MODE=paper \
		-e DATABASE_PATH=/app/data/trading.db \
		mktrader:dev

docker-down:
	docker rm -f mktrader-dev 2>/dev/null || true

ci-local: lint test smoke release-check

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
