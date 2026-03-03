"""Dataset commands: list, get, create, delete, export, upload, generate, view-file, structure."""

from __future__ import annotations

import csv
import json
import os

import click

from langsmith.cli.config import get_client
from langsmith.cli.output import output_json, output_table, console
from langsmith.cli.utils import resolve_dataset as _resolve_dataset


@click.group("dataset")
def dataset_group():
    """Create, manage, and inspect evaluation datasets.

    \b
    Datasets are collections of input/output examples used for evaluating
    LLM applications. They can be created manually, uploaded from files,
    or generated from production traces.

    \b
    Common workflows:
      1. List & inspect:  dataset list, dataset get, dataset export
      2. Create from file: dataset upload data.json --name my-dataset
      3. Generate from traces: trace export ./traces && dataset generate -i ./traces -o eval.json --type final_response
      4. Inspect local files: dataset view-file data.json, dataset structure data.json

    \b
    Examples:
      langsmith dataset list
      langsmith dataset list --name-contains eval
      langsmith dataset get my-dataset
      langsmith dataset create --name my-dataset --description "Eval set for v2"
      langsmith dataset export my-dataset ./export.json
      langsmith dataset upload data.json --name new-dataset
    """


@dataset_group.command("list")
@click.option(
    "--limit",
    "-n",
    type=int,
    default=100,
    help="Maximum number of datasets to return. Default: 100.",
)
@click.option(
    "--name-contains",
    default=None,
    help="Filter to datasets whose name contains this substring.",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def dataset_list(ctx, limit, name_contains, output_file):
    """List all datasets in the workspace.

    \b
    Returns an array of dataset summaries including name, ID, description,
    example count, and creation date.

    \b
    Examples:
      langsmith dataset list
      langsmith dataset list --name-contains eval --limit 10

    \b
    JSON output: [{id, name, description, data_type, example_count, created_at}, ...]
    """
    client = get_client(ctx)
    kwargs = {"limit": limit}
    if name_contains:
        kwargs["dataset_name_contains"] = name_contains

    datasets = list(client.list_datasets(**kwargs))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        columns = ["Name", "ID", "Description", "Examples", "Created"]
        rows = []
        for ds in datasets:
            rows.append(
                [
                    ds.name,
                    str(ds.id)[:16] + "...",
                    (ds.description or "")[:50],
                    str(ds.example_count or 0),
                    ds.created_at.strftime("%Y-%m-%d") if ds.created_at else "N/A",
                ]
            )
        output_table(columns, rows, title="Datasets")
    else:
        data = []
        for ds in datasets:
            data.append(
                {
                    "id": str(ds.id),
                    "name": ds.name,
                    "description": ds.description,
                    "data_type": ds.data_type.value if ds.data_type else None,
                    "example_count": ds.example_count,
                    "created_at": ds.created_at.isoformat() if ds.created_at else None,
                }
            )
        output_json(data, output_file)


@dataset_group.command("get")
@click.argument("name_or_id")
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def dataset_get(ctx, name_or_id, output_file):
    """Get dataset details by name or UUID.

    \b
    Accepts either a dataset name (string) or a dataset UUID.

    \b
    Examples:
      langsmith dataset get my-eval-dataset
      langsmith dataset get 550e8400-e29b-41d4-a716-446655440000

    \b
    JSON output: {id, name, description, data_type, example_count, created_at}
    """
    client = get_client(ctx)
    ds = _resolve_dataset(client, name_or_id)
    fmt = ctx.obj["output_format"]

    data = {
        "id": str(ds.id),
        "name": ds.name,
        "description": ds.description,
        "data_type": ds.data_type.value if ds.data_type else None,
        "example_count": ds.example_count,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }

    if fmt == "pretty":
        from langsmith.cli.output import print_output

        print_output(data, "pretty", output_file)
    else:
        output_json(data, output_file)


@dataset_group.command("create")
@click.option(
    "--name", required=True, help="Name for the new dataset (must be unique)."
)
@click.option(
    "--description", default=None, help="Optional description of the dataset."
)
@click.pass_context
def dataset_create(ctx, name, description):
    """Create a new empty dataset.

    \b
    Examples:
      langsmith dataset create --name my-eval-dataset
      langsmith dataset create --name my-eval-dataset --description "QA pairs for v2"

    \b
    JSON output: {status: "created", id, name, description, created_at}
    """
    client = get_client(ctx)
    ds = client.create_dataset(dataset_name=name, description=description)
    output_json(
        {
            "status": "created",
            "id": str(ds.id),
            "name": ds.name,
            "description": ds.description,
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
        }
    )


@dataset_group.command("delete")
@click.argument("name_or_id")
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt. Required for non-interactive use.",
)
@click.pass_context
def dataset_delete(ctx, name_or_id, yes):
    """Delete a dataset by name or UUID.

    \b
    WARNING: This permanently deletes the dataset and all its examples.
    Use --yes to skip the confirmation prompt (required for scripts/agents).

    \b
    Examples:
      langsmith dataset delete my-old-dataset --yes
      langsmith dataset delete 550e8400-e29b-41d4-a716-446655440000 --yes

    \b
    JSON output: {status: "deleted", id, name}
    """
    client = get_client(ctx)
    ds = _resolve_dataset(client, name_or_id)

    if not yes:
        click.confirm(f"Delete dataset '{ds.name}' ({ds.id})?", abort=True)

    client.delete_dataset(dataset_id=ds.id)
    output_json({"status": "deleted", "id": str(ds.id), "name": ds.name})


@dataset_group.command("export")
@click.argument("name_or_id")
@click.argument("output_file")
@click.option(
    "--limit",
    "-n",
    type=int,
    default=100,
    help="Maximum number of examples to export. Default: 100.",
)
@click.pass_context
def dataset_export(ctx, name_or_id, output_file, limit):
    """Export dataset examples to a JSON file.

    \b
    Writes an array of {inputs, outputs} objects. The output file is
    compatible with `dataset upload` for re-importing.

    \b
    Examples:
      langsmith dataset export my-dataset ./data.json
      langsmith dataset export my-dataset ./data.json --limit 500

    \b
    JSON output to stdout: {status: "exported", dataset, count, path}
    """
    client = get_client(ctx)
    ds = _resolve_dataset(client, name_or_id)
    examples = list(client.list_examples(dataset_id=ds.id, limit=limit))

    data = []
    for ex in examples:
        data.append({"inputs": ex.inputs, "outputs": ex.outputs})

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2, default=str)

    output_json(
        {
            "status": "exported",
            "dataset": ds.name,
            "count": len(data),
            "path": output_file,
        }
    )


@dataset_group.command("upload")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--name", required=True, help="Name for the new dataset to create.")
@click.option(
    "--description", default=None, help="Optional description of the dataset."
)
@click.pass_context
def dataset_upload(ctx, file_path, name, description):
    """Upload a JSON file as a new dataset.

    \b
    The JSON file should be an array of objects. Each object can be either:
      - {inputs: {...}, outputs: {...}}  (LangSmith format)
      - Any dict (treated as the input, no outputs)

    \b
    Creates a new dataset and populates it with examples from the file.

    \b
    Examples:
      langsmith dataset upload data.json --name my-dataset
      langsmith dataset upload pairs.json --name eval-v2 --description "QA pairs"

    \b
    JSON output: {status: "uploaded", dataset_id, dataset_name, example_count}
    """
    client = get_client(ctx)

    with open(file_path) as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    ds = client.create_dataset(dataset_name=name, description=description)

    inputs_list = []
    outputs_list = []
    for item in data:
        if isinstance(item, dict) and "inputs" in item:
            inputs_list.append(item["inputs"])
            outputs_list.append(item.get("outputs"))
        else:
            inputs_list.append(item)
            outputs_list.append(None)

    client.create_examples(
        inputs=inputs_list,
        outputs=outputs_list,
        dataset_id=ds.id,
    )

    output_json(
        {
            "status": "uploaded",
            "dataset_id": str(ds.id),
            "dataset_name": name,
            "example_count": len(inputs_list),
        }
    )


@dataset_group.command("generate")
@click.option(
    "--input",
    "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a directory of JSONL trace files, or a single JSONL/JSON file.",
)
@click.option(
    "--type",
    "dataset_type",
    required=True,
    type=click.Choice(["final_response", "single_step", "trajectory", "rag"]),
    help="Dataset type: final_response (input->output), single_step (node I/O), trajectory (tool sequence), rag (question->answer with chunks).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    required=True,
    help="Output file path (.json or .csv).",
)
@click.option(
    "--upload",
    "upload_name",
    default=None,
    help="Also upload the generated dataset to LangSmith with this name.",
)
@click.option(
    "--run-name",
    default=None,
    help="For single_step type: only extract I/O from runs matching this name.",
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="For trajectory type: maximum hierarchy depth for tool sequence extraction.",
)
@click.option(
    "--input-fields",
    default=None,
    help="Comma-separated field names to extract as inputs (e.g. 'query,question').",
)
@click.option(
    "--output-fields",
    default=None,
    help="Comma-separated field names to extract as outputs (e.g. 'answer,response').",
)
@click.option(
    "--messages-only",
    is_flag=True,
    default=False,
    help="For final_response: only extract from messages arrays, skip common fields.",
)
@click.option(
    "--sample-per-trace",
    type=int,
    default=None,
    help="For single_step: max number of examples to sample per trace.",
)
@click.option(
    "--sort",
    type=click.Choice(["newest", "oldest", "alphabetical", "reverse-alphabetical"]),
    default="newest",
    help="Sort order for input traces. Default: newest.",
)
@click.option(
    "--replace",
    is_flag=True,
    default=False,
    help="Overwrite existing output file and/or LangSmith dataset.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts for destructive operations.",
)
@click.pass_context
def dataset_generate(
    ctx,
    input_path,
    dataset_type,
    output_path,
    upload_name,
    run_name,
    depth,
    input_fields,
    output_fields,
    messages_only,
    sample_per_trace,
    sort,
    replace,
    yes,
):
    """Generate evaluation datasets from exported trace files.

    \b
    Reads JSONL trace files (produced by `trace export`) and extracts
    structured input/output pairs suitable for evaluation.

    \b
    Dataset types:
      final_response  Extract root input -> root output pairs
      single_step     Extract individual node I/O (use --run-name to target)
      trajectory      Extract input -> tool call sequence
      rag             Extract question -> retrieved chunks -> answer

    \b
    Typical workflow:
      langsmith trace export ./traces --project my-app --full --limit 50
      langsmith dataset generate -i ./traces -o eval.json --type final_response
      langsmith dataset generate -i ./traces -o eval.json --type rag --upload my-rag-eval

    \b
    JSON output: {status: "generated", type, count, output, [uploaded_to]}
    """
    from langsmith.cli.generation import (
        load_traces_from_dir,
        load_traces_from_file,
        generate_dataset,
        export_to_file,
        export_to_langsmith,
    )

    # Parse field lists
    in_fields = [f.strip() for f in input_fields.split(",")] if input_fields else None
    out_fields = (
        [f.strip() for f in output_fields.split(",")] if output_fields else None
    )

    # Load traces
    if os.path.isdir(input_path):
        traces = load_traces_from_dir(input_path, sort)
    else:
        traces = load_traces_from_file(input_path, sort)

    if not traces:
        output_json({"error": "No traces found"})
        return

    # Generate dataset
    dataset = generate_dataset(
        traces=traces,
        dataset_type=dataset_type,
        run_name=run_name,
        depth=depth,
        input_fields=in_fields,
        output_fields=out_fields,
        messages_only=messages_only,
        sample_per_trace=sample_per_trace,
    )

    if not dataset:
        output_json({"error": "No examples generated"})
        return

    # Handle replace for output file
    if os.path.exists(output_path) and not replace:
        output_json(
            {"error": f"Output file exists: {output_path}. Use --replace to overwrite."}
        )
        return

    # Export to file
    export_to_file(dataset, output_path)

    result = {
        "status": "generated",
        "type": dataset_type,
        "count": len(dataset),
        "output": output_path,
    }

    # Upload to LangSmith if requested
    if upload_name:
        client = get_client(ctx)

        # Handle replace for LangSmith dataset
        if replace:
            try:
                existing = client.read_dataset(dataset_name=upload_name)
            except Exception:
                existing = None  # Dataset doesn't exist yet, nothing to replace
            if existing is not None:
                if not yes:
                    click.confirm(
                        f"Delete existing dataset '{upload_name}'?", abort=True
                    )
                client.delete_dataset(dataset_id=existing.id)

        export_to_langsmith(client, dataset, upload_name, dataset_type)
        result["uploaded_to"] = upload_name

    output_json(result)


@dataset_group.command("view-file")
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--limit",
    "-n",
    type=int,
    default=5,
    help="Number of examples to display. Default: 5.",
)
@click.pass_context
def dataset_view_file(ctx, file_path, limit):
    """Preview examples from a local dataset file (JSON or CSV).

    \b
    Quick way to inspect dataset files without uploading them. Supports
    .json and .csv files.

    \b
    Examples:
      langsmith dataset view-file data.json
      langsmith dataset view-file data.csv --limit 10
      langsmith --format pretty dataset view-file data.json

    \b
    JSON output: [{...}, ...] (first N examples)
    """
    fmt = ctx.obj["output_format"]
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        with open(file_path) as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = [data]

        click.echo(f"File: {os.path.basename(file_path)}", err=True)
        click.echo(f"Total: {len(data)} examples", err=True)

        examples = data[:limit]
        if fmt == "pretty":
            _display_examples_pretty(examples)
        else:
            output_json(examples)

    elif ext == ".csv":
        with open(file_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        click.echo(f"File: {os.path.basename(file_path)}", err=True)
        click.echo(f"Total: {len(rows)} rows", err=True)

        examples = rows[:limit]
        if fmt == "pretty":
            if examples:
                columns = list(examples[0].keys())
                table_rows = []
                for row in examples:
                    table_rows.append([str(row.get(c, ""))[:100] for c in columns])
                output_table(columns, table_rows, title=os.path.basename(file_path))
        else:
            output_json(examples)

    else:
        output_json({"error": f"Unsupported file type: {ext}"})


@dataset_group.command("structure")
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def dataset_structure(ctx, file_path):
    """Analyze the structure and field coverage of a local dataset file.

    \b
    Shows the format, example/row count, a preview of the first example,
    and a field coverage report showing how many examples contain each field.

    \b
    Useful for understanding the shape of a dataset before uploading or
    using it for evaluation.

    \b
    Examples:
      langsmith dataset structure data.json
      langsmith dataset structure data.csv

    \b
    JSON output: {format, example_count, first_example_preview, field_coverage: {field: "N/M (P%)"}}
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        with open(file_path) as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = [data]

        # First example preview
        first_preview = json.dumps(data[0], default=str)[:500] if data else "N/A"

        # Field coverage
        all_fields: dict[str, int] = {}
        for item in data:
            if isinstance(item, dict):
                for key in item:
                    all_fields[key] = all_fields.get(key, 0) + 1

        total = len(data)
        coverage = {
            field: f"{count}/{total} ({count * 100 // total}%)"
            for field, count in sorted(all_fields.items())
        }

        output_json(
            {
                "format": "json",
                "example_count": total,
                "first_example_preview": first_preview,
                "field_coverage": coverage,
            }
        )

    elif ext == ".csv":
        with open(file_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        col_counts: dict[str, int] = {}
        for row in rows:
            for key, val in row.items():
                if val:
                    col_counts[key] = col_counts.get(key, 0) + 1

        total = len(rows)
        coverage = {
            col: f"{count}/{total} ({count * 100 // total}%)"
            for col, count in sorted(col_counts.items())
        }

        output_json(
            {
                "format": "csv",
                "row_count": total,
                "column_coverage": coverage,
            }
        )

    else:
        output_json({"error": f"Unsupported file type: {ext}"})


def _display_examples_pretty(examples: list) -> None:
    """Display examples in pretty format using Rich panels."""
    from rich.panel import Panel
    from rich.syntax import Syntax

    for i, ex in enumerate(examples):
        if isinstance(ex, dict) and "inputs" in ex:
            inputs_str = json.dumps(ex["inputs"], indent=2, default=str)
            console.print(
                Panel(
                    Syntax(inputs_str, "json", theme="monokai"),
                    title=f"Example {i + 1} - Inputs",
                    border_style="blue",
                )
            )
            if "outputs" in ex and ex["outputs"]:
                outputs_str = json.dumps(ex["outputs"], indent=2, default=str)
                console.print(
                    Panel(
                        Syntax(outputs_str, "json", theme="monokai"),
                        title=f"Example {i + 1} - Outputs",
                        border_style="green",
                    )
                )
        else:
            raw_str = json.dumps(ex, indent=2, default=str)
            console.print(
                Panel(
                    Syntax(raw_str, "json", theme="monokai"),
                    title=f"Example {i + 1}",
                )
            )
