.PHONY: tests lint format


tests:
	poetry run pytest tests/unit_tests

integration_tests:
	poetry run pytest tests/integration_tests

lint:
	poetry run mypy .
	poetry run black . --check
	poetry run ruff .

format:
	poetry run black .
	poetry run ruff --select I --fix .

build:
	poetry build

publish:
	poetry publish --dry-run

update_data_model:
	poetry run python scripts/update_data_models.py
	$(MAKE) format
