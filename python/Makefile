.PHONY: tests lint format build publish doctest integration_tests integration_tests_fast evals benchmark benchmark-fast test-wheel-imports


OUTPUT ?= out/benchmark.json

benchmark:
	mkdir -p out
	rm -f $(OUTPUT)
	uv run python -m bench -o $(OUTPUT) --rigorous

benchmark-fast:
	mkdir -p out
	rm -f $(OUTPUT)
	uv run python -m bench -o $(OUTPUT) --fast

PROFILE_NAME ?= output

profile-background-thread:
	mkdir -p profiles
	uv run python -m cProfile -o profiles/$(PROFILE_NAME).prof bench/create_run.py

view-profile:
	uv run snakeviz profiles/${PROFILE_NAME}.prof

TEST ?= "tests/unit_tests"
test: tests
tests:
	env \
	 -u LANGCHAIN_PROJECT \
	 -u LANGCHAIN_API_KEY \
	 -u LANGCHAIN_TRACING_V2 \
	 -u LANGSMITH_TRACING \
	 PYTHONDEVMODE=1 \
	 PYTHONASYNCIODEBUG=1 \
	 uv run python -m pytest --disable-socket --allow-unix-socket -n auto --durations=10 ${TEST}

tests_watch:
	uv run ptw --now . -- -vv -x  tests/unit_tests

INT_TEST ?= "tests/integration_tests"
integration_tests:
	uv run python -m pytest -x -v --durations=10 --cov=langsmith --cov-report=term-missing --cov-report=html --cov-config=.coveragerc ${INT_TEST}

integration_tests_fast:
	uv run python -m pytest -x -n auto --durations=10 -v --cov=langsmith --cov-report=term-missing --cov-report=html --cov-config=.coveragerc ${INT_TEST}

integration_tests_watch:
	uv run ptw --now . -- -vv -x  ${INT_TEST}

doctest:
	uv run python -m pytest -n auto -x --durations=10 --doctest-modules langsmith

evals:
	uv run python -m pytest -n auto -x tests/evaluation

lint:
	uv run ruff check .
	# uv run ty check .
	uv run mypy langsmith 

format:
	uv run ruff format .
	uv run ruff check . --fix

build:
	uv build

publish:
	uv publish --dry-run

test-wheel-imports:
	uv build --no-sources
	uv run python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); f.close(); print('\n'.join(d['project']['dependencies']))" > /tmp/langsmith-declared-deps.txt
	uv venv /tmp/langsmith-strict-test
	uv pip install dist/langsmith-*.whl --no-deps --python /tmp/langsmith-strict-test
	uv pip install -r /tmp/langsmith-declared-deps.txt --python /tmp/langsmith-strict-test
	/tmp/langsmith-strict-test/bin/python -c "\
from langsmith._openapi_client import Langsmith; \
from langsmith.client import Client"
	rm -rf /tmp/langsmith-strict-test /tmp/langsmith-declared-deps.txt

api_docs_build:
	uv run python docs/create_api_rst.py
	cd docs && uv run make html
	uv run python docs/scripts/custom_formatter.py docs/_build/html/
	cp docs/_build/html/{reference,index}.html
	open docs/_build/html/index.html

api_docs_clean:
	git clean -fd ./docs/