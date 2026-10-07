"""Query an agent's traces: resolve its address to a project id, then query runs.

Needs LANGSMITH_API_KEY. The agent environment must already have traces. Run it
with `python query_agent_traces.py`.
"""

import asyncio

import langsmith as ls

client = ls.Client()
agent = ls.Agent("checkout", "production")


async def main() -> None:
    project = await client.projects.resolve(**agent.to_api_address())

    async for run in client.runs.query_v2(
        project_ids=[str(project.session_id)],
        is_root=True,
        selects=["ID", "NAME", "STATUS"],
        page_size=10,
    ):
        print(run.id, run.name, run.status)


asyncio.run(main())
