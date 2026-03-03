"""Trace commands: list, get, export."""

from __future__ import annotations

import json
import os

import click

from langsmith.cli.config import get_client
from langsmith.cli.filters import build_query_params, common_filter_options
from langsmith.cli.output import output_json, output_tree, print_runs_table
from langsmith.cli.utils import extract_run


@click.group("trace")
def trace_group():
    """Query and export traces (top-level agent runs and their full hierarchy).

    \b
    A trace is a tree of runs representing one end-to-end invocation of your
    application. The root run is the top-level entry point; child runs are
    LLM calls, tool calls, retriever steps, etc.

    \b
    Examples:
      langsmith trace list --project my-app --limit 5
      langsmith trace list --project my-app --last-n-minutes 60 --error
      langsmith trace get <trace-id> --project my-app --full
      langsmith trace export ./traces --project my-app --limit 20 --full
    """


@trace_group.command("list")
@common_filter_options(include_run_type=False)
@click.option("--include-metadata", is_flag=True, default=False,
              help="Add status, duration_ms, token_usage, costs, tags to each run.")
@click.option("--include-io", is_flag=True, default=False,
              help="Add inputs, outputs, and error fields to each run.")
@click.option("--full", is_flag=True, default=False,
              help="Shorthand for --include-metadata --include-io. Returns all fields.")
@click.option("--show-hierarchy", is_flag=True, default=False,
              help="Fetch the full run tree for each trace (slower, more API calls).")
@click.option("-o", "--output", "output_file", default=None,
              help="Write JSON output to a file instead of stdout.")
@click.pass_context
def trace_list(ctx, trace_ids, limit, project, last_n_minutes, since, error,
               name, min_latency, max_latency, min_tokens, tags, raw_filter,
               include_metadata, include_io, full, show_hierarchy, output_file):
    """List traces (root runs) matching filter criteria.

    \b
    Returns an array of root-level runs. By default only base fields are
    included (run_id, trace_id, name, run_type, start_time, end_time).
    Use --include-metadata, --include-io, or --full for more detail.

    \b
    Default limit: 20. Traces are always filtered to root runs only.

    \b
    Examples:
      # Recent traces in a project
      langsmith trace list --project my-app --limit 10

    \b
      # Traces with errors from the last hour
      langsmith trace list --project my-app --last-n-minutes 60 --error

    \b
      # Slow traces with full detail
      langsmith trace list --project my-app --min-latency 5.0 --full

    \b
      # Traces with specific tags
      langsmith trace list --project my-app --tags production,v2

    \b
    JSON output: [{run_id, trace_id, name, run_type, ...}, ...]
    """
    if full:
        include_metadata = True
        include_io = True

    if limit is None:
        limit = 20

    client = get_client(ctx)
    params = build_query_params(
        project=project, trace_ids=trace_ids, limit=limit,
        last_n_minutes=last_n_minutes, since=since, run_type=None,
        is_root=True, error=error, name=name, raw_filter=raw_filter,
        min_latency=min_latency, max_latency=max_latency, min_tokens=min_tokens,
        tags=tags,
    )

    runs = list(client.list_runs(**params))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        if show_hierarchy:
            for run in runs:
                all_runs = list(client.list_runs(
                    trace_id=str(run.trace_id) if hasattr(run, "trace_id") else str(run.id),
                    project_name=params.get("project_name"),
                ))
                output_tree(all_runs)
        else:
            print_runs_table(runs, include_metadata=include_metadata, title="Traces")
    else:
        if show_hierarchy:
            result = []
            for run in runs:
                tid = str(run.trace_id) if hasattr(run, "trace_id") else str(run.id)
                all_runs = list(client.list_runs(
                    trace_id=tid,
                    project_name=params.get("project_name"),
                ))
                result.append({
                    "trace_id": tid,
                    "run_count": len(all_runs),
                    "runs": [extract_run(r, include_metadata, include_io) for r in all_runs],
                })
            output_json(result, output_file)
        else:
            data = [extract_run(r, include_metadata, include_io) for r in runs]
            output_json(data, output_file)


@trace_group.command("get")
@click.argument("trace_id")
@click.option("--project", default=None,
              help="Project name. Falls back to LANGSMITH_PROJECT env var.")
@click.option("--include-metadata", is_flag=True, default=False,
              help="Add status, duration_ms, token_usage, costs, tags to each run.")
@click.option("--include-io", is_flag=True, default=False,
              help="Add inputs, outputs, and error fields to each run.")
@click.option("--full", is_flag=True, default=False,
              help="Shorthand for --include-metadata --include-io.")
@click.option("-o", "--output", "output_file", default=None,
              help="Write JSON output to a file instead of stdout.")
@click.pass_context
def trace_get(ctx, trace_id, project, include_metadata, include_io, full, output_file):
    """Fetch every run in a single trace, given its trace ID.

    \b
    Returns the full run hierarchy for the trace. In pretty mode, renders
    as a tree. In JSON mode, returns {trace_id, run_count, runs: [...]}.

    \b
    Examples:
      langsmith trace get abc123-def456 --project my-app
      langsmith trace get abc123-def456 --project my-app --full
      langsmith trace get abc123-def456 --project my-app -o trace.json
    """
    if full:
        include_metadata = True
        include_io = True

    client = get_client(ctx)
    params = {"trace_id": trace_id}
    resolved_project = project or os.getenv("LANGSMITH_PROJECT")
    if resolved_project:
        params["project_name"] = resolved_project

    runs = list(client.list_runs(**params))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        output_tree(runs)
    else:
        data = {
            "trace_id": trace_id,
            "run_count": len(runs),
            "runs": [extract_run(r, include_metadata, include_io) for r in runs],
        }
        output_json(data, output_file)


@trace_group.command("export")
@click.argument("output_dir")
@common_filter_options(include_run_type=False)
@click.option("--include-metadata", is_flag=True, default=False,
              help="Add status, duration_ms, token_usage, costs, tags to each run.")
@click.option("--include-io", is_flag=True, default=False,
              help="Add inputs, outputs, and error fields to each run.")
@click.option("--full", is_flag=True, default=False,
              help="Shorthand for --include-metadata --include-io.")
@click.option("--filename-pattern", default="{trace_id}.jsonl",
              help="Filename pattern. Supports {trace_id} and {name} placeholders.")
@click.pass_context
def trace_export(ctx, output_dir, trace_ids, limit, project, last_n_minutes, since,
                 error, name, min_latency, max_latency, min_tokens, tags, raw_filter,
                 include_metadata, include_io, full, filename_pattern):
    """Export traces to a directory as JSONL files (one file per trace).

    \b
    Each trace is written as a JSONL file where each line is one run.
    This format is compatible with `dataset generate --input` for building
    evaluation datasets from production traces.

    \b
    Default limit: 10.

    \b
    Examples:
      langsmith trace export ./traces --project my-app --limit 20 --full
      langsmith trace export ./data --project my-app --last-n-minutes 60

    \b
    JSON output: {status, count, output_dir}
    """
    if full:
        include_metadata = True
        include_io = True

    if limit is None:
        limit = 10

    os.makedirs(output_dir, exist_ok=True)
    client = get_client(ctx)
    params = build_query_params(
        project=project, trace_ids=trace_ids, limit=limit,
        last_n_minutes=last_n_minutes, since=since, run_type=None,
        is_root=True, error=error, name=name, raw_filter=raw_filter,
        min_latency=min_latency, max_latency=max_latency, min_tokens=min_tokens,
        tags=tags,
    )

    root_runs = list(client.list_runs(**params))
    exported = 0

    for root in root_runs:
        tid = str(root.trace_id) if hasattr(root, "trace_id") else str(root.id)
        all_runs = list(client.list_runs(
            trace_id=tid,
            project_name=params.get("project_name"),
        ))

        filename = os.path.basename(
            filename_pattern.format(trace_id=tid, name=root.name or "unknown")
        )
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w") as f:
            for run in all_runs:
                f.write(json.dumps(extract_run(run, include_metadata, include_io), default=str) + "\n")
        exported += 1

    output_json({"status": "exported", "count": exported, "output_dir": output_dir})
