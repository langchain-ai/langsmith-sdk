.PHONY: tests lint format

tests:
	poetry run pytest tests/unit_tests

tests_watch:
	poetry run ptw --now . -- -vv -x  tests/unit_tests

integration_tests:
	poetry run pytest tests/integration_tests

integration_tests_fast:
	poetry run pytest -n auto tests/integration_tests

lint:
	poetry run ruff .
	poetry run mypy .
	poetry run black . --check

format:
	poetry run ruff format .
	poetry run ruff --fix .
	poetry run black .

build:
	poetry build

publish:
	poetry publish --dry-run
