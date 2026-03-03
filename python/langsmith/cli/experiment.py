"""Experiment commands: list, get."""

from __future__ import annotations


import click

from langsmith.cli.config import get_client
from langsmith.cli.output import output_json, output_table


@click.group("experiment")
def experiment_group():
    """Query evaluation experiments and their results.

    \b
    Experiments are evaluation runs that test your application against a
    dataset. Each experiment produces feedback scores (accuracy, relevance,
    etc.) and run statistics (latency, token usage, error rate).

    \b
    Experiments are listed as LangSmith projects that have a reference
    dataset (i.e. they are not free-form projects).

    \b
    Examples:
      langsmith experiment list
      langsmith experiment list --dataset my-eval-dataset
      langsmith experiment get my-experiment-name
    """


@experiment_group.command("list")
@click.option("--dataset", "dataset_name", default=None,
              help="Filter to experiments that evaluated this dataset (by name).")
@click.option("--limit", "-n", type=int, default=20,
              help="Maximum number of experiments to return. Default: 20.")
@click.option("-o", "--output", "output_file", default=None,
              help="Write JSON output to a file instead of stdout.")
@click.pass_context
def experiment_list(ctx, dataset_name, limit, output_file):
    """List experiments, optionally filtered by dataset.

    \b
    Returns an array of experiment summaries. Use --dataset to narrow
    results to experiments for a specific evaluation dataset.

    \b
    Examples:
      langsmith experiment list
      langsmith experiment list --dataset my-eval-dataset --limit 10
      langsmith experiment list -o experiments.json

    \b
    JSON output: [{id, name, reference_dataset_id, run_count, feedback_stats}, ...]
    """
    client = get_client(ctx)

    kwargs = {"limit": limit, "reference_free": False}
    if dataset_name:
        ds = client.read_dataset(dataset_name=dataset_name)
        kwargs["reference_dataset_id"] = ds.id

    projects = list(client.list_projects(**kwargs))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        columns = ["Name", "ID", "Dataset ID", "Runs"]
        rows = []
        for p in projects:
            rows.append([
                p.name,
                str(p.id)[:16] + "...",
                str(p.reference_dataset_id)[:16] + "..." if p.reference_dataset_id else "N/A",
                str(getattr(p, "run_count", "N/A")),
            ])
        output_table(columns, rows, title="Experiments")
    else:
        data = []
        for p in projects:
            entry = {
                "id": str(p.id),
                "name": p.name,
                "reference_dataset_id": str(p.reference_dataset_id) if p.reference_dataset_id else None,
            }
            if hasattr(p, "run_count"):
                entry["run_count"] = p.run_count
            if hasattr(p, "feedback_stats"):
                entry["feedback_stats"] = p.feedback_stats
            data.append(entry)
        output_json(data, output_file)


@experiment_group.command("get")
@click.argument("name_or_id")
@click.option("-o", "--output", "output_file", default=None,
              help="Write JSON output to a file instead of stdout.")
@click.pass_context
def experiment_get(ctx, name_or_id, output_file):
    """Get detailed results for a specific experiment.

    \b
    Returns feedback statistics (e.g. accuracy scores), run statistics
    (latency, token counts, error rates), and the number of examples
    evaluated.

    \b
    Falls back to get_test_results (Pandas DataFrame) if the structured
    API is unavailable.

    \b
    Examples:
      langsmith experiment get my-experiment-2024-01-15
      langsmith experiment get my-experiment -o results.json

    \b
    JSON output: {name, feedback_stats, run_stats, example_count}
    """
    client = get_client(ctx)
    fmt = ctx.obj["output_format"]

    try:
        results = client.get_experiment_results(name=name_or_id)

        data = {
            "name": name_or_id,
            "feedback_stats": results.get("feedback_stats", {}),
            "run_stats": _serialize_run_stats(results.get("run_stats", {})),
        }

        # Include examples with runs summary
        examples_with_runs = list(results.get("examples_with_runs", []))
        data["example_count"] = len(examples_with_runs)

        if fmt == "pretty":
            from langsmith.cli.output import print_output
            print_output(data, "pretty", output_file)
        else:
            output_json(data, output_file)

    except Exception:
        # Structured API unavailable or failed — fallback to get_test_results (returns DataFrame)
        try:
            df = client.get_test_results(project_name=name_or_id)
            records = df.to_dict(orient="records") if hasattr(df, "to_dict") else []
            data = {
                "name": name_or_id,
                "result_count": len(records),
                "results": records,
            }
            if fmt == "pretty":
                from langsmith.cli.output import print_output
                print_output(data, "pretty", output_file)
            else:
                output_json(data, output_file)
        except Exception as e2:
            output_json({"error": f"Failed to fetch experiment results: {e2}"})


def _serialize_run_stats(stats: dict) -> dict:
    """Make run stats JSON serializable."""
    result = {}
    for k, v in stats.items():
        if hasattr(v, "total_seconds"):
            result[k] = v.total_seconds()
        elif hasattr(v, "__float__"):
            result[k] = float(v)
        else:
            result[k] = v
    return result
