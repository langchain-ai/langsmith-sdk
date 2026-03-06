"""Evaluator commands: list, upload, delete."""

from __future__ import annotations

import importlib.util
import inspect
import re

import click
import requests

from langsmith.cli.config import get_api_headers, get_api_url, get_client
from langsmith.cli.output import output_json, output_table


@click.group("evaluator")
def evaluator_group():
    """Manage online and offline evaluator rules.

    \b
    Evaluators are Python functions uploaded to LangSmith that automatically
    score runs. They can target a specific dataset (offline/experiment
    evaluators) or a project (online evaluators that score production runs).

    \b
    Offline evaluators receive (run, example) and are used in experiments.
    Online evaluators receive (run) and score runs as they arrive.

    \b
    Note: Global evaluators (no --dataset or --project) are not supported.

    \b
    Examples:
      langsmith evaluator list
      langsmith evaluator upload eval.py --name accuracy --function check_accuracy --dataset my-eval-set
      langsmith evaluator upload eval.py --name latency-check --function check_latency --project my-app
      langsmith evaluator delete accuracy --yes
    """


@evaluator_group.command("list")
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def evaluator_list(ctx, output_file):
    """List all evaluator rules in the workspace.

    \b
    Shows each evaluator's name, sampling rate, target (dataset or project),
    and whether it is enabled.

    \b
    Examples:
      langsmith evaluator list
      langsmith evaluator list -o evaluators.json

    \b
    JSON output: [{id, name, sampling_rate, is_enabled, dataset_id, session_id}, ...]
    """
    headers = get_api_headers(ctx)
    api_url = get_api_url(ctx)

    try:
        response = requests.get(f"{api_url}/runs/rules", headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        output_json({"error": f"Failed to list evaluators: {e}"})
        return
    rules = response.json()

    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        columns = ["Name", "Sampling Rate", "Target", "Enabled"]
        rows = []
        for rule in rules:
            name = rule.get("display_name", "N/A")
            rate = f"{rule.get('sampling_rate', 0) * 100:.0f}%"
            # Determine target
            dataset_ids = rule.get("dataset_id") or rule.get("target_dataset_ids", [])
            session_ids = rule.get("session_id") or rule.get("target_project_ids", [])
            if dataset_ids:
                target = "dataset"
            elif session_ids:
                target = "project"
            else:
                target = "All runs"
            enabled = "Yes" if rule.get("is_enabled", False) else "No"
            rows.append([name, rate, target, enabled])
        output_table(columns, rows, title="Evaluator Rules")
    else:
        data = []
        for rule in rules:
            data.append(
                {
                    "id": rule.get("id"),
                    "name": rule.get("display_name"),
                    "sampling_rate": rule.get("sampling_rate"),
                    "is_enabled": rule.get("is_enabled"),
                    "dataset_id": rule.get("dataset_id"),
                    "session_id": rule.get("session_id"),
                }
            )
        output_json(data, output_file)


@evaluator_group.command("upload")
@click.argument("evaluator_file", type=click.Path(exists=True))
@click.option(
    "--name", required=True, help="Display name for the evaluator in LangSmith."
)
@click.option(
    "--function",
    "func_name",
    required=True,
    help="Name of the Python function to upload from the file.",
)
@click.option(
    "--dataset",
    "target_dataset",
    default=None,
    help="Target dataset name (creates an offline/experiment evaluator).",
)
@click.option(
    "--project",
    "target_project",
    default=None,
    help="Target project name (creates an online evaluator).",
)
@click.option(
    "--sampling-rate",
    type=float,
    default=1.0,
    help="Fraction of runs to evaluate (0.0-1.0). Default: 1.0 (all runs).",
)
@click.option(
    "--replace",
    is_flag=True,
    default=False,
    help="Replace an existing evaluator with the same name and target.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt when replacing.",
)
@click.pass_context
def evaluator_upload(
    ctx,
    evaluator_file,
    name,
    func_name,
    target_dataset,
    target_project,
    sampling_rate,
    replace,
    yes,
):
    """Upload a Python evaluator function to LangSmith.

    \b
    The function is extracted from the given Python file by name, its source
    code is uploaded, and it is registered as an evaluator rule. The function
    is automatically renamed to `perform_eval` (a LangSmith API requirement).

    \b
    You must specify either --dataset (offline) or --project (online).
    Global evaluators are not supported.

    \b
    Function signatures:
      Offline (--dataset): def my_eval(run, example) -> dict
      Online  (--project): def my_eval(run) -> dict

    \b
    Examples:
      # Offline evaluator for experiments
      langsmith evaluator upload evals.py \\
        --name accuracy --function check_accuracy --dataset my-eval-set

    \b
      # Online evaluator for production monitoring
      langsmith evaluator upload evals.py \\
        --name latency-check --function check_latency --project my-app

    \b
      # Replace an existing evaluator
      langsmith evaluator upload evals.py \\
        --name accuracy --function check_accuracy_v2 --dataset my-eval-set --replace --yes

    \b
    JSON output: {status: "uploaded", id, name, target}
    """
    if not target_dataset and not target_project:
        output_json(
            {
                "error": "Must specify --dataset or --project (global evaluators not supported)"
            }
        )
        return

    headers = get_api_headers(ctx)
    api_url = get_api_url(ctx)
    client = get_client(ctx)

    # Resolve targets
    dataset_id = None
    project_id = None

    if target_dataset:
        ds = client.read_dataset(dataset_name=target_dataset)
        dataset_id = str(ds.id)

    if target_project:
        for proj in client.list_projects():
            if proj.name == target_project:
                project_id = str(proj.id)
                break
        if not project_id:
            output_json({"error": f"Project not found: {target_project}"})
            return

    # Check for existing evaluator
    try:
        existing = _find_evaluator(api_url, headers, name, dataset_id, project_id)
    except requests.RequestException as e:
        output_json({"error": f"Failed to check for existing evaluator: {e}"})
        return
    if existing:
        if not replace:
            output_json(
                {
                    "error": f"Evaluator '{name}' already exists (use --replace to overwrite)",
                    "id": existing.get("id"),
                }
            )
            return
        if not yes:
            click.confirm(f"Replace existing evaluator '{name}'?", abort=True)
        try:
            _delete_evaluator_by_id(api_url, headers, existing["id"])
        except requests.RequestException as e:
            output_json({"error": f"Failed to delete existing evaluator: {e}"})
            return

    # Load and prepare function source
    spec = importlib.util.spec_from_file_location("evaluator_module", evaluator_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    func = getattr(module, func_name, None)
    if func is None:
        output_json({"error": f"Function '{func_name}' not found in {evaluator_file}"})
        return

    source = inspect.getsource(func)
    # Rename function to perform_eval (LangSmith requirement)
    source = re.sub(
        rf"\bdef\s+{re.escape(func_name)}\s*\(",
        "def perform_eval(",
        source,
    )

    # Build payload
    payload = {
        "display_name": name,
        "sampling_rate": sampling_rate,
        "is_enabled": True,
        "include_extended_stats": False,
        "code_evaluators": [{"code": source, "language": "python"}],
    }

    if dataset_id:
        payload["dataset_id"] = dataset_id
    if project_id:
        payload["session_id"] = project_id

    # Upload
    try:
        response = requests.post(f"{api_url}/runs/rules", headers=headers, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        output_json({"error": f"Failed to upload evaluator: {e}"})
        return

    result = response.json()
    output_json(
        {
            "status": "uploaded",
            "id": result.get("id"),
            "name": name,
            "target": "dataset" if dataset_id else "project",
        }
    )


@evaluator_group.command("delete")
@click.argument("name")
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt. Required for non-interactive use.",
)
@click.pass_context
def evaluator_delete(ctx, name, yes):
    """Delete an evaluator rule by its display name.

    \b
    Finds all evaluator rules matching the given name and deletes them.
    Use --yes to skip confirmation (required for scripts/agents).

    \b
    Examples:
      langsmith evaluator delete accuracy --yes
      langsmith evaluator delete my-evaluator --yes

    \b
    JSON output: {status: "deleted", name, count}
    """
    headers = get_api_headers(ctx)
    api_url = get_api_url(ctx)

    try:
        response = requests.get(f"{api_url}/runs/rules", headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        output_json({"error": f"Failed to list evaluators: {e}"})
        return
    rules = response.json()

    matching = [r for r in rules if r.get("display_name") == name]
    if not matching:
        output_json({"error": f"Evaluator '{name}' not found"})
        return

    if not yes:
        click.confirm(f"Delete evaluator '{name}'?", abort=True)

    deleted = 0
    for rule in matching:
        try:
            _delete_evaluator_by_id(api_url, headers, rule["id"])
            deleted += 1
        except requests.RequestException as e:
            output_json({"error": f"Failed to delete evaluator {rule['id']}: {e}"})
            return

    output_json({"status": "deleted", "name": name, "count": deleted})


def _find_evaluator(
    api_url: str,
    headers: dict,
    name: str,
    dataset_id: str | None,
    project_id: str | None,
) -> dict | None:
    """Find an existing evaluator by name and target."""
    response = requests.get(f"{api_url}/runs/rules", headers=headers)
    response.raise_for_status()  # Let caller handle RequestException
    rules = response.json()

    for rule in rules:
        if rule.get("display_name") != name:
            continue
        # Match by target
        if dataset_id and str(rule.get("dataset_id", "")) == dataset_id:
            return rule
        if project_id and str(rule.get("session_id", "")) == project_id:
            return rule
    return None


def _delete_evaluator_by_id(api_url: str, headers: dict, rule_id: str) -> None:
    """Delete an evaluator rule by ID."""
    response = requests.delete(f"{api_url}/runs/rules/{rule_id}", headers=headers)
    response.raise_for_status()  # Let caller handle RequestException
