import threading
from unittest.mock import MagicMock

from langsmith import RunTree
from langsmith._internal import _background_thread as bt
from langsmith._internal._compressed_traces import CompressedTraces
from langsmith.client import Client


def create_compressed_run_trees(count: int) -> None:
    session = MagicMock()
    response = session.request.return_value
    response.status_code = 202
    response.text = "Accepted"
    client = Client(session=session, api_key="fake", auto_batch_tracing=False)
    client.compressed_traces = CompressedTraces()
    client._data_available_event = threading.Event()

    for i in range(count):
        RunTree(name=str(i), ls_client=client).post()

    stream, info, destinations = bt._tracing_thread_drain_compressed_buffer(
        client, size_limit=1, size_limit_bytes=1
    )
    if stream is not None:
        client._send_compressed_multipart_req(stream, info, destinations=destinations)
