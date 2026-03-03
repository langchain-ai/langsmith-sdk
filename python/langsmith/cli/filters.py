"""Shared filter builder and common filter options for Click commands."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import click


def common_filter_options(include_run_type: bool = True):
    """Decorator factory that adds shared filter flags to a Click command."""

    def decorator(func):
        options = [
            click.option(
                "--trace-ids",
                default=None,
                help="Comma-separated trace IDs to filter by. Example: 'abc123,def456'.",
            ),
            click.option(
                "--limit", "-n",
                type=int,
                default=None,
                help="Maximum number of results to return (command sets its own default).",
            ),
            click.option(
                "--project",
                default=None,
                help="Project name to query. [env: LANGSMITH_PROJECT]",
            ),
            click.option(
                "--last-n-minutes",
                type=int,
                default=None,
                help="Only include runs from the last N minutes. Example: --last-n-minutes 60.",
            ),
            click.option(
                "--since",
                default=None,
                help="Only include runs after this ISO timestamp. Example: '2024-01-15T00:00:00Z'.",
            ),
            click.option(
                "--error/--no-error",
                default=None,
                help="Filter by error status. --error for failed runs, --no-error for successful.",
            ),
            click.option(
                "--name",
                default=None,
                help="Filter by run name (case-insensitive substring search).",
            ),
            click.option(
                "--min-latency",
                type=float,
                default=None,
                help="Minimum latency in seconds. Example: --min-latency 2.5.",
            ),
            click.option(
                "--max-latency",
                type=float,
                default=None,
                help="Maximum latency in seconds. Example: --max-latency 10.0.",
            ),
            click.option(
                "--min-tokens",
                type=int,
                default=None,
                help="Minimum total tokens (prompt + completion). Example: --min-tokens 1000.",
            ),
            click.option(
                "--tags",
                default=None,
                help="Comma-separated tags (OR logic). Example: 'production,v2'.",
            ),
            click.option(
                "--filter", "raw_filter",
                default=None,
                help="Raw LangSmith filter DSL string. Example: 'and(eq(status, \"error\"), gte(latency, 5))'.",
            ),
        ]
        if include_run_type:
            options.append(
                click.option(
                    "--run-type",
                    type=click.Choice(
                        ["llm", "chain", "tool", "retriever", "prompt", "parser"],
                        case_sensitive=False,
                    ),
                    default=None,
                    help="Filter by run type (llm, chain, tool, retriever, prompt, parser).",
                ),
            )

        # Apply decorators in reverse order (outermost first)
        for option in reversed(options):
            func = option(func)
        return func

    return decorator


def build_query_params(
    project: str | None = None,
    trace_ids: str | None = None,
    limit: int | None = None,
    last_n_minutes: int | None = None,
    since: str | None = None,
    run_type: str | None = None,
    is_root: bool | None = None,
    error: bool | None = None,
    name: str | None = None,
    raw_filter: str | None = None,
    min_latency: float | None = None,
    max_latency: float | None = None,
    min_tokens: int | None = None,
    tags: str | None = None,
) -> dict:
    """Build unified query params dict for client.list_runs().

    Assembles the filter DSL string from individual flags.
    All conditions AND together.
    """
    params: dict = {}

    # Project
    resolved_project = project or os.getenv("LANGSMITH_PROJECT")
    if resolved_project:
        params["project_name"] = resolved_project

    # Trace IDs
    if trace_ids:
        ids = [t.strip() for t in trace_ids.split(",") if t.strip()]
        if len(ids) == 1:
            params["trace_id"] = ids[0]
        # Multiple trace IDs handled via filter DSL below

    # Limit
    if limit is not None:
        params["limit"] = limit

    # Time filters
    if last_n_minutes is not None:
        params["start_time"] = datetime.now(timezone.utc) - timedelta(minutes=last_n_minutes)
    elif since:
        params["start_time"] = datetime.fromisoformat(since.replace("Z", "+00:00"))

    # Run type
    if run_type:
        params["run_type"] = run_type

    # Is root
    if is_root is True:
        params["is_root"] = True

    # Error
    if error is not None:
        params["error"] = error

    # Build filter DSL parts
    filter_parts: list[str] = []

    # Multiple trace IDs
    if trace_ids:
        ids = [t.strip() for t in trace_ids.split(",") if t.strip()]
        if len(ids) > 1:
            id_list = ", ".join(f'"{tid}"' for tid in ids)
            filter_parts.append(f"in(trace_id, [{id_list}])")

    # Name search
    if name:
        filter_parts.append(f'search(name, "{name}")')

    # Latency filters
    if min_latency is not None:
        filter_parts.append(f"gte(latency, {min_latency})")
    if max_latency is not None:
        filter_parts.append(f"lte(latency, {max_latency})")

    # Token filter
    if min_tokens is not None:
        filter_parts.append(f"gte(total_tokens, {min_tokens})")

    # Tags
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if len(tag_list) == 1:
            filter_parts.append(f'has(tags, "{tag_list[0]}")')
        elif len(tag_list) > 1:
            tag_clauses = ", ".join(f'has(tags, "{t}")' for t in tag_list)
            filter_parts.append(f"or({tag_clauses})")

    # Raw filter passthrough
    if raw_filter:
        filter_parts.append(raw_filter)

    # Combine filter parts
    if len(filter_parts) == 1:
        params["filter"] = filter_parts[0]
    elif len(filter_parts) > 1:
        params["filter"] = f"and({', '.join(filter_parts)})"

    return params
