from unittest.mock import Mock, patch

from langsmith.wrappers._gateway import (
    add_gateway_response_metadata,
    install_gateway_response_hook,
)


def test_add_gateway_response_metadata() -> None:
    run = Mock()

    add_gateway_response_metadata(
        {"X-LangSmith-Gateway-Metadata": '{"outcome":"blocked"}'},
        run_tree=run,
    )

    run.add_metadata.assert_called_once_with(
        {"ls_gateway_info": {"outcome": "blocked"}}
    )


def test_invalid_gateway_response_metadata_is_ignored() -> None:
    run = Mock()

    add_gateway_response_metadata(
        {"x-langsmith-gateway-metadata": "not-json"},
        run_tree=run,
    )

    run.add_metadata.assert_not_called()


def test_install_gateway_response_hook_once() -> None:
    class Client:
        def __init__(self) -> None:
            self.event_hooks: dict[str, list] = {"response": []}

    http_client = Client()
    client = Mock(_client=http_client)
    run = Mock(run_type="llm")

    install_gateway_response_hook(client)
    install_gateway_response_hook(client)
    assert len(http_client.event_hooks["response"]) == 1

    with patch(
        "langsmith.wrappers._gateway.run_helpers.get_current_run_tree",
        return_value=run,
    ):
        http_client.event_hooks["response"][0](
            Mock(headers={"x-langsmith-gateway-metadata": '{"outcome":"success"}'})
        )

    run.add_metadata.assert_called_once_with(
        {"ls_gateway_info": {"outcome": "success"}}
    )


async def test_install_async_gateway_response_hook() -> None:
    import httpx

    http_client = httpx.AsyncClient()
    client = Mock(_client=http_client)
    run = Mock(run_type="llm")

    install_gateway_response_hook(client)
    assert len(http_client.event_hooks["response"]) == 1

    with patch(
        "langsmith.wrappers._gateway.run_helpers.get_current_run_tree",
        return_value=run,
    ):
        await http_client.event_hooks["response"][0](
            Mock(headers={"x-langsmith-gateway-metadata": '{"outcome":"success"}'})
        )

    run.add_metadata.assert_called_once_with(
        {"ls_gateway_info": {"outcome": "success"}}
    )
    await http_client.aclose()
