"""Top-level Click group and global options."""

try:
    import click
except ImportError:
    import sys

    def cli():
        print(
            "LangSmith CLI dependencies are not installed.\n"
            "Install them with: pip install 'langsmith[cli]'",
            file=sys.stderr,
        )
        sys.exit(1)
else:
    from langsmith.cli.trace import trace_group
    from langsmith.cli.run import run_group
    from langsmith.cli.thread import thread_group
    from langsmith.cli.dataset import dataset_group
    from langsmith.cli.example import example_group
    from langsmith.cli.evaluator import evaluator_group
    from langsmith.cli.experiment import experiment_group
    from langsmith.cli.tracing_project import project_group

    MAIN_HELP = """
    LangSmith CLI — query and manage LangSmith resources from the command line.

    \b
    Designed for AI coding agents and developers who need fast, scriptable
    access to traces, runs, datasets, evaluators, experiments, and threads.
    All commands output JSON by default for easy parsing.

    \b
    Authentication:
      Set LANGSMITH_API_KEY as an environment variable, or pass --api-key.
      Optionally set LANGSMITH_ENDPOINT for self-hosted instances.
      Set LANGSMITH_PROJECT as a default project name for trace/run queries.

    \b
    Quick start:
      langsmith project list
      langsmith trace list --project my-project --limit 5
      langsmith run list --project my-project --run-type llm --limit 10
      langsmith dataset list
      langsmith evaluator list
      langsmith experiment list --dataset my-eval-dataset

    \b
    Output:
      --format json    Machine-readable JSON (default). Best for agents and scripts.
      --format pretty  Human-readable tables, trees, and syntax-highlighted JSON.
    """

    @click.group(help=MAIN_HELP)
    @click.option(
        "--api-key",
        envvar="LANGSMITH_API_KEY",
        default=None,
        help="LangSmith API key. [env: LANGSMITH_API_KEY]",
    )
    @click.option(
        "--api-url",
        envvar="LANGSMITH_ENDPOINT",
        default="https://api.smith.langchain.com",
        help="LangSmith API URL. [env: LANGSMITH_ENDPOINT]",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(["json", "pretty"]),
        default="json",
        help="Output format. 'json' for machine-readable, 'pretty' for human-readable.",
    )
    @click.version_option(package_name="langsmith")
    @click.pass_context
    def cli(ctx: click.Context, api_key: str, api_url: str, output_format: str) -> None:
        """LangSmith CLI - Query and manage LangSmith resources."""
        ctx.ensure_object(dict)
        ctx.obj["api_key"] = api_key
        ctx.obj["api_url"] = api_url
        ctx.obj["output_format"] = output_format

    cli.add_command(project_group, name="project")
    cli.add_command(trace_group, name="trace")
    cli.add_command(run_group, name="run")
    cli.add_command(thread_group, name="thread")
    cli.add_command(dataset_group, name="dataset")
    cli.add_command(example_group, name="example")
    cli.add_command(evaluator_group, name="evaluator")
    cli.add_command(experiment_group, name="experiment")
