from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from langsmith import run_trees
from langsmith.client import Client


def test_run_tree_accepts_tpe() -> None:
    mock_client = MagicMock(spec=Client)
    run_trees.RunTree(
        name="My Chat Bot",
        inputs={"text": "Summarize this morning's meetings."},
        client=mock_client,
        executor=ThreadPoolExecutor(),
    )
