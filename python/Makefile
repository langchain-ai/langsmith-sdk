.PHONY: tests lint format build publish doctest integration_tests integration_tests_fast evals benchmark benchmark-fast


OUTPUT ?= out/benchmark.json

benchmark:
	mkdir -p out
	rm -f $(OUTPUT)
	poetry run python -m bench -o $(OUTPUT) --rigorous

benchmark-fast:
	mkdir -p out
	rm -f $(OUTPUT)
	poetry run python -m bench -o $(OUTPUT) --fast

tests:
	 PYTHONDEVMODE=1 PYTHONASYNCIODEBUG=1 poetry run python -m pytest --disable-socket --allow-unix-socket -n auto --durations=10 tests/unit_tests

tests_watch:
	poetry run ptw --now . -- -vv -x  tests/unit_tests

integration_tests:
	poetry run python -m pytest -v --durations=10 --cov=langsmith --cov-report=term-missing --cov-report=html --cov-config=.coveragerc tests/integration_tests

integration_tests_fast:
	poetry run python -m pytest -n auto --durations=10 -v --cov=langsmith --cov-report=term-missing --cov-report=html --cov-config=.coveragerc tests/integration_tests

doctest:
	poetry run python -m pytest -n auto --durations=10 --doctest-modules langsmith

evals:
	poetry run python -m pytest tests/evaluation

lint:
	poetry run ruff check .
	poetry run mypy langsmith 
	poetry run black . --check

format:
	poetry run ruff format .
	poetry run ruff check . --fix
	poetry run black .

build:
	poetry build

publish:
	poetry publish --dry-run
