"""Auth, env vars, and client configuration."""

import os
import sys

import click
from langsmith.client import Client


def get_client(ctx: click.Context) -> Client:
    """Build a langsmith.Client from Click context."""
    api_key = ctx.obj.get("api_key")
    api_url = ctx.obj.get("api_url")
    if not api_key:
        click.echo('{"error": "LANGSMITH_API_KEY not set"}', err=True)
        sys.exit(1)
    return Client(api_key=api_key, api_url=api_url)


def get_api_headers(ctx: click.Context) -> dict:
    """Build headers for direct REST calls (evaluators)."""
    api_key = ctx.obj.get("api_key")
    if not api_key:
        click.echo('{"error": "LANGSMITH_API_KEY not set"}', err=True)
        sys.exit(1)
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    workspace_id = os.getenv("LANGSMITH_WORKSPACE_ID")
    if workspace_id:
        headers["x-tenant-id"] = workspace_id
    return headers


def get_api_url(ctx: click.Context) -> str:
    """Get the API base URL from Click context."""
    return ctx.obj.get("api_url", "https://api.smith.langchain.com")
