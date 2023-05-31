import pytest

from langchainplus_sdk.client import LangChainPlusClient
from langchainplus_sdk.run_helpers import run_tree
from langchainplus_sdk.schemas import flush_all_runs


@pytest.fixture
def langchain_client(monkeypatch: pytest.MonkeyPatch) -> LangChainPlusClient:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    return LangChainPlusClient()


def test_nested_runs(langchain_client: LangChainPlusClient):
    session_name = "__My Tracer Session"
    if session_name in [session.name for session in langchain_client.list_sessions()]:
        langchain_client.delete_session(session_name=session_name)

    @run_tree(run_type="chain")
    def my_run(text: str):
        my_llm_run(text)
        return text

    @run_tree(run_type="llm")
    def my_llm_run(text: str):
        return f"Completed: text"

    @run_tree(run_type="chain")
    def my_chain_run(text: str, run):
        return my_run(text, run=run)

    my_chain_run("foo", session_name=session_name)
    flush_all_runs()
    runs = list(langchain_client.list_runs(session_name=session_name))
    assert len(runs) == 3
    langchain_client.delete_session(session_name=session_name)
