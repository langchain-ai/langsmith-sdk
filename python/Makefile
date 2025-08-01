.PHONY: tests lint format build publish doctest integration_tests integration_tests_fast evals benchmark benchmark-fast


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
	uv run mypy langsmith 

format:
	uv run ruff format .
	uv run ruff check . --fix

build:
	uv build

publish:
	uv publish --dry-run

api_docs_build:
	uv run python docs/create_api_rst.py
	cd docs && uv run make html
	uv run python docs/scripts/custom_formatter.py docs/_build/html/
	cp docs/_build/html/{reference,index}.html
	open docs/_build/html/index.html

api_docs_clean:
	git clean -fd ./docs/

sync-version:
	# Update version in __init__.py to match pyproject.toml
	$(eval VERSION := $(shell grep '^version =' pyproject.toml | sed 's/version = "\(.*\)"/\1/'))
	sed -i '' 's/__version__ = "[^"]*"/__version__ = "$(VERSION)"/' langsmith/__init__.py
	echo "Synced version: $(VERSION)"

check-version:
	# Get version from pyproject.toml
	$(eval VERSION := $(shell grep '^version =' pyproject.toml | sed 's/version = "\(.*\)"/\1/'))
	# Get version from __init__.py
	$(eval INIT_VERSION := $(shell grep '__version__ =' langsmith/__init__.py | sed 's/__version__ = "\(.*\)"/\1/'))
	@echo "Checking version alignment..."
	@echo "pyproject.toml version: $(VERSION)"
	@echo "__init__.py version: $(INIT_VERSION)"
	@if [ "$(VERSION)" = "$(INIT_VERSION)" ]; then \
		echo "✅ Versions are aligned"; \
	else \
		echo "❌ Version mismatch! Please run 'make sync-version' to sync versions"; \
		exit 1; \
	fi