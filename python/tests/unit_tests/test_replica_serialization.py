"""`RunTree.replicas` is routing config, not run data: it must not be serialized.

`serialize_run_dict` dumps whatever is left in the payload with no allow-list,
so the guard has to live on the model field.
"""

import queue
import uuid
from unittest.mock import MagicMock

import orjson

from langsmith import Client
from langsmith.run_trees import AuthHeaders, RunTree, WriteReplica

SECRET = "replica-secret"
OTHER_URL = "https://other.example.com"


def _client(api_url="https://main.example.com", api_key="main-key"):
    client = Client(
        api_url=api_url,
        api_key=api_key,
        session=MagicMock(),
        auto_batch_tracing=False,
    )
    client.tracing_queue = queue.PriorityQueue(maxsize=100)
    client.compressed_traces = None
    return client


def test_replica_config_is_not_serialized():
    """The fan-out sends one body per replica, so anything left in the body
    reaches every destination -- including the other replicas' credentials."""
    client = _client()
    rt = RunTree(
        name="r",
        run_type="chain",
        id=uuid.uuid4(),
        inputs={"a": 1},
        ls_client=client,
        project_name="p",
        replicas=[
            WriteReplica(project_name="p", primary=True),
            WriteReplica(
                project_name="q",
                api_url=OTHER_URL,
                auth=AuthHeaders(api_key=SECRET),
                client=_client(OTHER_URL, "other-key"),
            ),
        ],
    )
    rt.post()
    rt.end(outputs={"b": 2})
    rt.patch()

    ops = [item.item for item in list(client.tracing_queue.queue)]
    assert ops, "nothing was queued"
    for op in ops:
        assert "replicas" not in orjson.loads(op._none)
        assert SECRET.encode() not in op._none
        assert OTHER_URL.encode() not in op._none
