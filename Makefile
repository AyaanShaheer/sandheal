.PHONY: help install install-dev run test lint format check coverage migrate revision up down clean

PYTHON ?= python
UVICORN_APP ?= app.main:app
HOST ?= 127.0.0.1
PORT ?= 8000

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the runtime dependencies
	$(PYTHON) -m pip install -e .

install-dev:  ## Install the project with the development extras
	$(PYTHON) -m pip install -e ".[dev]"

run:  ## Start the development server
	uvicorn $(UVICORN_APP) --reload --host $(HOST) --port $(PORT)

test:  ## Run the test suite
	pytest -v

coverage:  ## Run the test suite with a coverage report
	pytest --cov=app --cov-report=term-missing

lint:  ## Run the linter
	ruff check .

format:  ## Format the code
	ruff format .

check: lint  ## Run every static check
	ruff format --check .

migrate:  ## Apply the database migrations
	alembic upgrade head

revision:  ## Create a new migration: make revision m="message"
	alembic revision --autogenerate -m "$(m)"

up: migrate  ## Apply the database migrations
	@true

down:  ## Roll the database back one revision
	alembic downgrade -1

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
