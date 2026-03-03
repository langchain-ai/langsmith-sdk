"""Tracing project commands: list."""

from __future__ import annotations

import click

from langsmith.cli.config import get_client
from langsmith.cli.output import output_json, output_table


@click.group("project")
def project_group():
    """List and inspect tracing projects (sessions).

    \b
    Tracing projects collect runs from your application. Each project
    is a namespace that groups related traces together (e.g. by app,
    environment, or feature).

    \b
    Note: This lists tracing projects only (not experiments). Experiments
    are projects with an associated reference dataset — use
    'langsmith experiment list' for those.

    \b
    Examples:
      langsmith project list
      langsmith project list --limit 10
      langsmith project list --name-contains chatbot
    """


@project_group.command("list")
@click.option(
    "--limit",
    "-n",
    type=int,
    default=20,
    help="Maximum number of projects to return. Default: 20.",
)
@click.option(
    "--name-contains",
    default=None,
    help="Filter projects whose name contains this substring (case-insensitive).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def project_list(ctx, limit, name_contains, output_file):
    """List tracing projects in the workspace.

    \b
    Returns an array of tracing project summaries, sorted by most
    recently active. Only lists tracing projects (not experiments).

    \b
    Examples:
      langsmith project list
      langsmith project list --limit 50
      langsmith project list --name-contains my-app
      langsmith project list --format pretty

    \b
    JSON output: [{id, name, description, run_count, latency_p50,
                   latency_p99, total_tokens, total_cost, error_rate,
                   last_run_start_time, start_time}, ...]
    """
    client = get_client(ctx)
    fmt = ctx.obj["output_format"]

    kwargs = {"limit": limit, "reference_free": True}
    if name_contains:
        kwargs["name_contains"] = name_contains

    projects = list(client.list_projects(**kwargs))

    if fmt == "pretty":
        columns = ["Name", "ID", "Runs", "Latency p50", "Error Rate", "Last Active"]
        rows = []
        for p in projects:
            latency = _format_timedelta(p.latency_p50) if p.latency_p50 else "N/A"
            error_rate = f"{p.error_rate:.1%}" if p.error_rate is not None else "N/A"
            last_active = (
                p.last_run_start_time.strftime("%Y-%m-%d %H:%M")
                if p.last_run_start_time
                else "N/A"
            )
            rows.append(
                [
                    p.name or "N/A",
                    str(p.id)[:16] + "...",
                    str(p.run_count) if p.run_count is not None else "N/A",
                    latency,
                    error_rate,
                    last_active,
                ]
            )
        output_table(columns, rows, title="Tracing Projects")
    else:
        data = []
        for p in projects:
            entry = {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "run_count": p.run_count,
                "latency_p50": p.latency_p50.total_seconds() if p.latency_p50 else None,
                "latency_p99": p.latency_p99.total_seconds() if p.latency_p99 else None,
                "total_tokens": p.total_tokens,
                "total_cost": float(p.total_cost) if p.total_cost is not None else None,
                "error_rate": p.error_rate,
                "last_run_start_time": str(p.last_run_start_time)
                if p.last_run_start_time
                else None,
                "start_time": str(p.start_time) if p.start_time else None,
            }
            data.append(entry)
        output_json(data, output_file)


def _format_timedelta(td) -> str:
    """Format a timedelta as a human-readable string."""
    total_seconds = td.total_seconds()
    if total_seconds < 1:
        return f"{total_seconds * 1000:.0f}ms"
    elif total_seconds < 60:
        return f"{total_seconds:.1f}s"
    else:
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes}m {seconds:.0f}s"
