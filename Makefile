.PHONY: test format format-check lint typecheck check coverage hooks install-hooks bump-patch bump-minor bump-major

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

install-hooks:
	uv run prek install --install-hooks --hook-type pre-commit --hook-type pre-push

bump-patch:
	uv run hatch version patch

bump-minor:
	uv run hatch version minor

bump-major:
	uv run hatch version major
