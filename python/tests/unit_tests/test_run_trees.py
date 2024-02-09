from langsmith import run_trees


def test_run_tree_accepts_tpe() -> None:
    run_trees.RunTree(
        name="My Chat Bot",
        inputs={"text": "Summarize this morning's meetings."},
        api_url="http://localhost:8000",
        api_key="test",
    )
