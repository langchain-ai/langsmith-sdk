"""Tests for filters.py - build_query_params and filter DSL generation."""

from langsmith.cli.filters import build_query_params


class TestBuildQueryParams:
    def test_basic_project(self):
        params = build_query_params(project="my-project")
        assert params["project_name"] == "my-project"

    def test_single_trace_id(self):
        params = build_query_params(trace_ids="abc-123")
        assert params["trace_id"] == "abc-123"

    def test_multiple_trace_ids(self):
        params = build_query_params(trace_ids="abc-123, def-456")
        assert "filter" in params
        assert 'in(trace_id, ["abc-123", "def-456"])' in params["filter"]

    def test_limit(self):
        params = build_query_params(limit=10)
        assert params["limit"] == 10

    def test_last_n_minutes(self):
        params = build_query_params(last_n_minutes=30)
        assert "start_time" in params

    def test_since_iso(self):
        params = build_query_params(since="2024-01-01T00:00:00Z")
        assert "start_time" in params

    def test_run_type(self):
        params = build_query_params(run_type="llm")
        assert params["run_type"] == "llm"

    def test_is_root(self):
        params = build_query_params(is_root=True)
        assert params["is_root"] is True

    def test_error_filter(self):
        params = build_query_params(error=True)
        assert params["error"] is True

    def test_error_false(self):
        params = build_query_params(error=False)
        assert params["error"] is False

    def test_name_search(self):
        params = build_query_params(name="chat")
        assert params["filter"] == 'search(name, "chat")'

    def test_min_latency(self):
        params = build_query_params(min_latency=2.5)
        assert params["filter"] == "gte(latency, 2.5)"

    def test_max_latency(self):
        params = build_query_params(max_latency=10.0)
        assert params["filter"] == "lte(latency, 10.0)"

    def test_latency_range(self):
        params = build_query_params(min_latency=1.0, max_latency=5.0)
        assert "and(" in params["filter"]
        assert "gte(latency, 1.0)" in params["filter"]
        assert "lte(latency, 5.0)" in params["filter"]

    def test_min_tokens(self):
        params = build_query_params(min_tokens=100)
        assert params["filter"] == "gte(total_tokens, 100)"

    def test_single_tag(self):
        params = build_query_params(tags="prod")
        assert params["filter"] == 'has(tags, "prod")'

    def test_multiple_tags(self):
        params = build_query_params(tags="prod, beta")
        assert 'or(has(tags, "prod"), has(tags, "beta"))' in params["filter"]

    def test_raw_filter(self):
        params = build_query_params(raw_filter='eq(status, "error")')
        assert params["filter"] == 'eq(status, "error")'

    def test_combined_filters(self):
        params = build_query_params(name="chat", min_latency=1.0, tags="prod")
        assert "and(" in params["filter"]
        assert 'search(name, "chat")' in params["filter"]
        assert "gte(latency, 1.0)" in params["filter"]
        assert 'has(tags, "prod")' in params["filter"]

    def test_project_env_fallback(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_PROJECT", "env-project")
        params = build_query_params()
        assert params["project_name"] == "env-project"

    def test_project_flag_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_PROJECT", "env-project")
        params = build_query_params(project="flag-project")
        assert params["project_name"] == "flag-project"

    def test_empty_params(self):
        params = build_query_params()
        # Should have no project_name if no env var set
        assert "filter" not in params
