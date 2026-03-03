"""Thread commands: list, get."""

from __future__ import annotations


import click

from langsmith.cli.config import get_client
from langsmith.cli.output import output_json, output_table, print_runs_table
from langsmith.cli.utils import extract_run


@click.group("thread")
def thread_group():
    """Query multi-turn conversation threads.

    \b
    A thread groups multiple root runs that share a thread_id, representing
    a multi-turn conversation. Each turn in the conversation is a separate
    trace (root run) linked by the same thread_id in its metadata.

    \b
    Examples:
      langsmith thread list --project my-chatbot --limit 10
      langsmith thread get <thread-id> --project my-chatbot --full
    """


@thread_group.command("list")
@click.option("--project", required=True,
              help="Project name (required). The project containing the threads.")
@click.option("--limit", "-n", type=int, default=20,
              help="Maximum number of threads to return. Default: 20.")
@click.option("--offset", type=int, default=0,
              help="Number of threads to skip (for pagination).")
@click.option("--filter", "raw_filter", default=None,
              help="Raw LangSmith filter DSL string applied to thread queries.")
@click.option("--last-n-minutes", type=int, default=None,
              help="Only include threads with activity in the last N minutes.")
@click.option("-o", "--output", "output_file", default=None,
              help="Write JSON output to a file instead of stdout.")
@click.pass_context
def thread_list(ctx, project, limit, offset, raw_filter, last_n_minutes, output_file):
    """List conversation threads in a project.

    \b
    Returns an array of thread summaries with thread_id, run_count,
    and time range.

    \b
    Examples:
      langsmith thread list --project my-chatbot
      langsmith thread list --project my-chatbot --last-n-minutes 120 --limit 5

    \b
    JSON output: [{thread_id, run_count, min_start_time, max_start_time}, ...]
    """
    from datetime import datetime, timedelta, timezone

    client = get_client(ctx)
    kwargs = {
        "project_name": project,
        "limit": limit,
        "offset": offset,
    }
    if raw_filter:
        kwargs["filter"] = raw_filter
    if last_n_minutes:
        kwargs["start_time"] = datetime.now(timezone.utc) - timedelta(minutes=last_n_minutes)

    threads = client.list_threads(**kwargs)
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        columns = ["Thread ID", "Run Count", "Min Start", "Max Start"]
        rows = []
        for t in threads:
            rows.append([
                t["thread_id"],
                str(t.get("count", len(t.get("runs", [])))),
                t.get("min_start_time", "N/A"),
                t.get("max_start_time", "N/A"),
            ])
        output_table(columns, rows, title=f"Threads in {project}")
    else:
        data = []
        for t in threads:
            entry = {
                "thread_id": t["thread_id"],
                "run_count": t.get("count", len(t.get("runs", []))),
                "min_start_time": t.get("min_start_time"),
                "max_start_time": t.get("max_start_time"),
            }
            data.append(entry)
        output_json(data, output_file)


@thread_group.command("get")
@click.argument("thread_id")
@click.option("--project", required=True,
              help="Project name (required). The project containing the thread.")
@click.option("--include-metadata", is_flag=True, default=False,
              help="Add status, duration_ms, token_usage, costs, tags to each run.")
@click.option("--include-io", is_flag=True, default=False,
              help="Add inputs, outputs, and error fields to each run.")
@click.option("--full", is_flag=True, default=False,
              help="Shorthand for --include-metadata --include-io.")
@click.option("--limit", "-n", type=int, default=None,
              help="Maximum number of runs (turns) to return.")
@click.option("-o", "--output", "output_file", default=None,
              help="Write JSON output to a file instead of stdout.")
@click.pass_context
def thread_get(ctx, thread_id, project, include_metadata, include_io, full, limit, output_file):
    """Fetch all runs (turns) in a single conversation thread.

    \b
    Returns the root runs belonging to this thread, ordered chronologically
    (oldest first). Each run represents one turn in the conversation.

    \b
    Examples:
      langsmith thread get <thread-id> --project my-chatbot
      langsmith thread get <thread-id> --project my-chatbot --full

    \b
    JSON output: {thread_id, run_count, runs: [...]}
    """
    if full:
        include_metadata = True
        include_io = True

    client = get_client(ctx)
    runs = list(client.read_thread(
        thread_id=thread_id,
        project_name=project,
        limit=limit,
    ))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        print_runs_table(runs, include_metadata=include_metadata, title=f"Thread {thread_id}")
    else:
        data = {
            "thread_id": thread_id,
            "run_count": len(runs),
            "runs": [extract_run(r, include_metadata, include_io) for r in runs],
        }
        output_json(data, output_file)
