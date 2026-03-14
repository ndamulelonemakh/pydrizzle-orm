.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help install lint format check test test-e2e test-v test-cov clean build publish-test publish

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:
	uv sync --all-extras --group dev

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

check: lint
	@echo "All checks passed."

test:
	uv run pytest -q

test-e2e:
	uv run pytest -q -m e2e

test-v:
	uv run pytest -v

test-cov:
	uv run pytest --cov=pydrizzle_orm --cov-report=term-missing

clean:
	rm -rf dist/ build/ .eggs/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

build: clean
	uv build

publish-test: build
	uv publish --index-url https://test.pypi.org/simple/

publish: build
	uv publish

all: format lint test
