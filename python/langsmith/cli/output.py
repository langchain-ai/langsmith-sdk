"""Shared output formatting: JSON, JSONL, table, tree."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from langsmith.cli.utils import calc_duration, format_duration

console = Console()


def output_json(data, file_path: str | None = None) -> None:
    """Output data as formatted JSON to stdout or file."""
    json_str = json.dumps(data, indent=2, default=str)
    if file_path:
        with open(file_path, "w") as f:
            f.write(json_str)
        click.echo(json.dumps({"status": "written", "path": file_path}), err=True)
    else:
        click.echo(json_str)


def output_jsonl(items: list, file_path: str | None = None) -> None:
    """Output items as JSONL (one JSON object per line)."""
    if file_path:
        with open(file_path, "w") as f:
            for item in items:
                f.write(json.dumps(item, default=str) + "\n")
        click.echo(json.dumps({"status": "written", "path": file_path, "count": len(items)}), err=True)
    else:
        for item in items:
            click.echo(json.dumps(item, default=str))


def output_table(columns: list[str], rows: list[list], title: str | None = None) -> None:
    """Output a Rich table (pretty mode)."""
    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(v) if v is not None else "" for v in row])
    console.print(table)


def output_tree(runs: list, root_id: str | None = None) -> None:
    """Output a trace hierarchy tree (pretty mode).

    Ported from query_traces.py print_tree.
    """
    if not runs:
        console.print("[dim]No runs found[/dim]")
        return

    # Build parent -> children mapping
    children_map: dict[str | None, list] = {}
    run_map: dict[str, object] = {}
    for run in runs:
        rid = str(run.id)
        pid = str(run.parent_run_id) if run.parent_run_id else None
        run_map[rid] = run
        children_map.setdefault(pid, []).append(run)

    # Sort children by start_time
    for pid in children_map:
        children_map[pid].sort(key=lambda r: r.start_time or "")

    # Find root
    if root_id is None:
        roots = children_map.get(None, [])
        if not roots:
            # Fallback: use first run
            roots = [runs[0]]
    else:
        roots = [run_map[root_id]] if root_id in run_map else children_map.get(None, runs[:1])

    for root in roots:
        duration = format_duration(calc_duration(root))
        tree = Tree(f"[bold]{root.name}[/bold] ({root.run_type}) [{duration}]")
        _add_children(tree, str(root.id), children_map)
        console.print(tree)


def _add_children(tree_node: Tree, parent_id: str, children_map: dict) -> None:
    """Recursively add children to a Rich tree node."""
    children = children_map.get(parent_id, [])
    for child in children:
        duration = format_duration(calc_duration(child))
        label = f"{child.name} ({child.run_type}) [{duration}]"
        if hasattr(child, "error") and child.error:
            label = f"[red]{label}[/red]"
        child_node = tree_node.add(label)
        _add_children(child_node, str(child.id), children_map)


def print_runs_table(runs: list, include_metadata: bool = False, title: str | None = None) -> None:
    """Print runs as a Rich table (pretty mode)."""
    columns = ["Time", "Name", "Type", "Trace ID", "Run ID"]
    if include_metadata:
        columns.extend(["Duration", "Status", "Tokens"])

    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col)

    # Sort newest first
    sorted_runs = sorted(runs, key=lambda r: r.start_time or "", reverse=True)

    for run in sorted_runs:
        time_str = run.start_time.strftime("%H:%M:%S") if run.start_time else "N/A"
        name = run.name[:40] if run.name else "N/A"
        trace_id = str(run.trace_id)[:16] + "..." if hasattr(run, "trace_id") and run.trace_id else "N/A"
        run_id = str(run.id)[:16] + "..."

        row = [time_str, name, run.run_type or "N/A", trace_id, run_id]

        if include_metadata:
            duration = format_duration(calc_duration(run))
            status = getattr(run, "status", "N/A") or "N/A"
            tokens = str(run.total_tokens) if hasattr(run, "total_tokens") and run.total_tokens else "N/A"
            row.extend([duration, status, tokens])

        table.add_row(*row)

    console.print(table)


def print_output(data, fmt: str, file_path: str | None = None) -> None:
    """Dispatch to json or pretty based on format flag."""
    if fmt == "json":
        output_json(data, file_path)
    else:
        # Pretty mode - just pretty-print the JSON with syntax highlighting
        from rich.syntax import Syntax
        json_str = json.dumps(data, indent=2, default=str)
        if file_path:
            with open(file_path, "w") as f:
                f.write(json_str)
        else:
            syntax = Syntax(json_str, "json", theme="monokai")
            console.print(syntax)
