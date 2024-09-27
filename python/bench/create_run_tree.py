from unittest.mock import patch

from langsmith import RunTree


def create_run_trees(N: int):
    with patch("langsmith.client.requests.Session", autospec=True):
        for i in range(N):
            RunTree(name=str(i)).post()
