.DEFAULT_GOAL := help
.PHONY: help sync test lint format format-check check clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

sync:  ## Create/refresh .venv and uv.lock from pyproject.toml
	uv sync

test:  ## Run the test suite (live tests stay skipped)
	uv run pytest

lint:  ## Ruff lint + import order over the repo
	uv run ruff check .

format:  ## Rewrite files with the Ruff formatter
	uv run ruff format .

format-check:  ## Verify the Ruff formatter would change nothing
	uv run ruff format --check .

check: lint test  ## Everything CI should run: lint + tests

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
