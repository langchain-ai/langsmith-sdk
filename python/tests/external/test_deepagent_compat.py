def test_deepagent_import():
    from deepagents import FilesystemMiddleware, create_deep_agent

    assert create_deep_agent is not None
    assert FilesystemMiddleware is not None


def test_deepagent_compile():
    from deepagents import create_deep_agent

    # Compiles the LangGraph graph — no API key needed
    agent = create_deep_agent()
    assert agent is not None
