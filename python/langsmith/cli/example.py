"""Example commands: list, create, delete."""

from __future__ import annotations

import json

import click

from langsmith.cli.config import get_client
from langsmith.cli.output import output_json, output_table
from langsmith.cli.utils import resolve_dataset as _resolve_dataset


@click.group("example")
def example_group():
    """Manage individual examples within datasets.

    \b
    Examples are the individual input/output pairs stored in a dataset.
    Use these commands to list, add, or remove examples.

    \b
    Examples:
      langsmith example list --dataset my-dataset
      langsmith example create --dataset my-dataset --inputs '{"question": "What is LangSmith?"}'
      langsmith example delete <example-id> --yes
    """


@example_group.command("list")
@click.option(
    "--dataset",
    "dataset_name",
    required=True,
    help="Dataset name or UUID to list examples from.",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=20,
    help="Maximum number of examples to return. Default: 20.",
)
@click.option(
    "--offset", type=int, default=0, help="Number of examples to skip (for pagination)."
)
@click.option(
    "--split",
    default=None,
    help="Filter to examples in a specific split (e.g. 'train', 'test').",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.pass_context
def example_list(ctx, dataset_name, limit, offset, split, output_file):
    """List examples in a dataset.

    \b
    Returns an array of examples with their inputs, outputs, metadata,
    and split information.

    \b
    Examples:
      langsmith example list --dataset my-dataset
      langsmith example list --dataset my-dataset --split test --limit 50
      langsmith example list --dataset my-dataset -o examples.json

    \b
    JSON output: [{id, inputs, outputs, metadata, split, created_at}, ...]
    """
    client = get_client(ctx)
    ds = _resolve_dataset(client, dataset_name)

    kwargs = {"dataset_id": ds.id, "limit": limit, "offset": offset}
    if split:
        kwargs["splits"] = [split]

    examples = list(client.list_examples(**kwargs))
    fmt = ctx.obj["output_format"]

    if fmt == "pretty":
        columns = ["ID", "Split", "Created", "Inputs Preview"]
        rows = []
        for ex in examples:
            inputs_preview = (
                json.dumps(ex.inputs, default=str)[:60] + "..." if ex.inputs else "N/A"
            )
            rows.append(
                [
                    str(ex.id)[:16] + "...",
                    getattr(ex, "split", None) or "N/A",
                    ex.created_at.strftime("%Y-%m-%d") if ex.created_at else "N/A",
                    inputs_preview,
                ]
            )
        output_table(columns, rows, title=f"Examples in {ds.name}")
    else:
        data = []
        for ex in examples:
            entry = {
                "id": str(ex.id),
                "inputs": ex.inputs,
                "outputs": ex.outputs,
                "metadata": ex.metadata,
                "created_at": ex.created_at.isoformat() if ex.created_at else None,
            }
            if hasattr(ex, "split"):
                entry["split"] = ex.split
            data.append(entry)
        output_json(data, output_file)


@example_group.command("create")
@click.option(
    "--dataset",
    "dataset_name",
    required=True,
    help="Dataset name to add the example to.",
)
@click.option(
    "--inputs",
    required=True,
    help='JSON string of input fields. Example: \'{"question": "What is LangSmith?"}\'',
)
@click.option(
    "--outputs",
    default=None,
    help='JSON string of expected output fields. Example: \'{"answer": "A platform for..."}\'',
)
@click.option(
    "--metadata",
    default=None,
    help='JSON string of metadata. Example: \'{"source": "manual"}\'',
)
@click.option(
    "--split",
    default=None,
    help="Assign to a split (e.g. 'train', 'test', 'validation').",
)
@click.pass_context
def example_create(ctx, dataset_name, inputs, outputs, metadata, split):
    """Create a new example in a dataset.

    \b
    Inputs and outputs are JSON strings. The example is added to the
    specified dataset.

    \b
    Examples:
      langsmith example create --dataset my-dataset \\
        --inputs '{"question": "What is LangSmith?"}' \\
        --outputs '{"answer": "A platform for LLM observability"}'

    \b
      langsmith example create --dataset my-dataset \\
        --inputs '{"query": "hello"}' --split test

    \b
    JSON output: {status: "created", id, dataset_id, inputs, outputs}
    """
    client = get_client(ctx)

    try:
        parsed_inputs = json.loads(inputs)
    except json.JSONDecodeError as e:
        output_json({"error": f"Invalid JSON for --inputs: {e}"})
        return

    try:
        parsed_outputs = json.loads(outputs) if outputs else None
    except json.JSONDecodeError as e:
        output_json({"error": f"Invalid JSON for --outputs: {e}"})
        return

    try:
        parsed_metadata = json.loads(metadata) if metadata else None
    except json.JSONDecodeError as e:
        output_json({"error": f"Invalid JSON for --metadata: {e}"})
        return

    ex = client.create_example(
        inputs=parsed_inputs,
        outputs=parsed_outputs,
        dataset_name=dataset_name,
        metadata=parsed_metadata,
        split=split,
    )

    output_json(
        {
            "status": "created",
            "id": str(ex.id),
            "dataset_id": str(ex.dataset_id),
            "inputs": ex.inputs,
            "outputs": ex.outputs,
        }
    )


@example_group.command("delete")
@click.argument("example_id")
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt. Required for non-interactive use.",
)
@click.pass_context
def example_delete(ctx, example_id, yes):
    """Delete an example by its UUID.

    \b
    Use --yes to skip the confirmation prompt (required for scripts/agents).

    \b
    Examples:
      langsmith example delete 550e8400-e29b-41d4-a716-446655440000 --yes

    \b
    JSON output: {status: "deleted", id}
    """
    if not yes:
        click.confirm(f"Delete example {example_id}?", abort=True)

    client = get_client(ctx)
    client.delete_example(example_id)
    output_json({"status": "deleted", "id": example_id})
