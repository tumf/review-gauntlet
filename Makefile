.PHONY: test format format-check lint typecheck check coverage hooks install install-hooks publish bump-patch bump-minor bump-major

test:
	uv run pytest

coverage:
	uv run pytest --cov=src/review_gauntlet --cov-report=term-missing --cov-report=html

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run pyright

check: format-check lint typecheck test

hooks:
	uv run prek run --all-files

install:
	uv tool install --reinstall .

install-hooks:
	uv run prek install --install-hooks --hook-type pre-commit --hook-type pre-push

publish:
	uv publish

bump-patch:
	uv run bump-my-version bump patch

bump-minor:
	uv run bump-my-version bump minor

bump-major:
	uv run bump-my-version bump major
