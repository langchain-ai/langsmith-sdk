"""Run commands: list, get, export."""

from __future__ import annotations


import click

from langsmith.cli.config import get_client
from langsmith.cli.filters import build_query_params, common_filter_options
from langsmith.cli.output import output_json, output_jsonl, print_runs_table
from langsmith.cli.utils import extract_run


@click.group("run")
def run_group():
    """Query and export individual runs (LLM calls, tool calls, chain steps, etc.).

    \b
    A run is a single step within a trace. Unlike `trace` commands (which
    filter on root runs only), `run` commands can query any run at any
    depth in the hierarchy — LLM calls, tool invocations, retriever steps,
    chain nodes, etc.

    \b
    Examples:
      langsmith run list --project my-app --run-type llm --limit 10
      langsmith run list --project my-app --run-type tool --name search
      langsmith run get <run-id> --full
      langsmith run export runs.jsonl --project my-app --run-type llm
    """


@run_group.command("list")
@common_filter_options(include_run_type=True)
@click.option(
    "--include-metadata",
    is_flag=True,
    default=False,
    help="Add status, duration_ms, token_usage, costs, tags to each run.",
)
@click.option(
    "--include-io",
    is_flag=True,
    default=False,
    help="Add inputs, outputs, and error fields to each run.",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Shorthand for --include-metadata --include-io. Returns all fields.",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def run_list(
    ctx,
    trace_ids,
    limit,
    project,
    last_n_minutes,
    since,
    run_type,
    error,
    name,
    min_latency,
    max_latency,
    min_tokens,
    tags,
    raw_filter,
    include_metadata,
    include_io,
    full,
    output_file,
):
    """List runs matching filter criteria (any run type at any depth).

    \b
    Returns an array of runs. Unlike `trace list`, this queries ALL runs
    (not just roots), so you can find specific LLM calls, tool uses, etc.
    Use --run-type to narrow by type.

    \b
    Default limit: 50.

    \b
    Examples:
      # All LLM calls in the last hour
      langsmith run list --project my-app --run-type llm --last-n-minutes 60

    \b
      # Tool calls with errors
      langsmith run list --project my-app --run-type tool --error

    \b
      # Runs by name with full I/O
      langsmith run list --project my-app --name ChatOpenAI --full --limit 5

    \b
      # Expensive LLM calls
      langsmith run list --project my-app --run-type llm --min-tokens 1000 --include-metadata

    \b
    JSON output: [{run_id, trace_id, name, run_type, ...}, ...]
    """
    if full:
        include_metadata = True
        include_io = True

    if limit is None:
        limit = 50

    client = get_client(ctx)
    params = build_query_params(
        project=project,
        trace_ids=trace_ids,
        limit=limit,
        last_n_minutes=last_n_minutes,
        since=since,
        run_type=run_type,
        is_root=False,
        error=error,
        name=name,
        raw_filter=raw_filter,
        min_latency=min_latency,
        max_latency=max_latency,
        min_tokens=min_tokens,
        tags=tags,
    )

    runs = list(client.list_runs(**params))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        print_runs_table(runs, include_metadata=include_metadata, title="Runs")
    else:
        data = [extract_run(r, include_metadata, include_io) for r in runs]
        output_json(data, output_file)


@run_group.command("get")
@click.argument("run_id")
@click.option(
    "--include-metadata",
    is_flag=True,
    default=False,
    help="Add status, duration_ms, token_usage, costs, tags.",
)
@click.option(
    "--include-io",
    is_flag=True,
    default=False,
    help="Add inputs, outputs, and error fields.",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Shorthand for --include-metadata --include-io.",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def run_get(ctx, run_id, include_metadata, include_io, full, output_file):
    """Fetch a single run by its run ID.

    \b
    Returns one run object with the requested detail level.

    \b
    Examples:
      langsmith run get abc123-def456
      langsmith run get abc123-def456 --full
      langsmith run get abc123-def456 --include-io -o run.json

    \b
    JSON output: {run_id, trace_id, name, run_type, ...}
    """
    if full:
        include_metadata = True
        include_io = True

    client = get_client(ctx)
    run = client.read_run(run_id)
    fmt = ctx.obj["output_format"]
    data = extract_run(run, include_metadata, include_io)

    if fmt == "pretty":
        from langsmith.cli.output import print_output

        print_output(data, "pretty", output_file)
    else:
        output_json(data, output_file)


@run_group.command("export")
@click.argument("output_file")
@common_filter_options(include_run_type=True)
@click.option(
    "--include-metadata",
    is_flag=True,
    default=False,
    help="Add status, duration_ms, token_usage, costs, tags to each run.",
)
@click.option(
    "--include-io",
    is_flag=True,
    default=False,
    help="Add inputs, outputs, and error fields to each run.",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Shorthand for --include-metadata --include-io.",
)
@click.pass_context
def run_export(
    ctx,
    output_file,
    trace_ids,
    limit,
    project,
    last_n_minutes,
    since,
    run_type,
    error,
    name,
    min_latency,
    max_latency,
    min_tokens,
    tags,
    raw_filter,
    include_metadata,
    include_io,
    full,
):
    """Export runs to a JSONL file (one JSON object per line).

    \b
    Default limit: 100.

    \b
    Examples:
      langsmith run export llm_calls.jsonl --project my-app --run-type llm
      langsmith run export errors.jsonl --project my-app --error --full

    \b
    JSON output to stderr: {status, path, count}
    """
    if full:
        include_metadata = True
        include_io = True

    if limit is None:
        limit = 100

    client = get_client(ctx)
    params = build_query_params(
        project=project,
        trace_ids=trace_ids,
        limit=limit,
        last_n_minutes=last_n_minutes,
        since=since,
        run_type=run_type,
        is_root=False,
        error=error,
        name=name,
        raw_filter=raw_filter,
        min_latency=min_latency,
        max_latency=max_latency,
        min_tokens=min_tokens,
        tags=tags,
    )

    runs = list(client.list_runs(**params))
    data = [extract_run(r, include_metadata, include_io) for r in runs]
    output_jsonl(data, output_file)
