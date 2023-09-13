.PHONY: tests lint format

tests:
	poetry run pytest tests/unit_tests

integration_tests:
	poetry run pytest tests/integration_tests

lint:
	poetry run ruff .
	poetry run mypy .
	poetry run black . --check

format:
	poetry run ruff --fix .
	poetry run black .

build:
	poetry build

publish:
	poetry publish --dry-run
