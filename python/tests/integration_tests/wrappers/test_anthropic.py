from anthropic import Anthropic, AsyncAnthropic

from langsmith.wrappers._generic import wrap_sdk


def test_invoke():
    client = Anthropic()
    client = wrap_sdk(client)

    message = client.messages.create(
        max_tokens=23,
        messages=[
            {
                "role": "user",
                "content": "Hello, Claude",
            }
        ],
        model="claude-3-opus-20240229",
    )
    assert len(message.content) > 0
    assert "H" in message.content[0].text


async def test_invoke_async():
    client = AsyncAnthropic()
    client = wrap_sdk(client)

    message = await client.messages.create(
        max_tokens=23,
        messages=[
            {
                "role": "user",
                "content": "Hello, Claude",
            }
        ],
        model="claude-3-opus-20240229",
    )
    assert len(message.content) > 0
    assert "H" in message.content[0].text
