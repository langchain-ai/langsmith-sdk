import os

os.environ["LANGCHAIN_PROJECT"] = "llm_messages_test_py"
os.environ["LANGSMITH_USE_PYO3_CLIENT"] = "true"

from langsmith import Client, traceable

client = Client(
    api_url="https://beta.api.smith.langchain.com",
    api_key=os.environ["LANGCHAIN_API_KEY"],
)


@traceable(client=client)
def format_prompt(subject):
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": f"What's a good name for a store that sells {subject}?",
        },
    ]


@traceable(run_type="llm", client=client)
def invoke_llm(messages):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Sure, how about 'Rainbow Socks'?",
                }
            }
        ]
    }


@traceable(client=client)
def parse_output(response):
    return response["choices"][0]["message"]["content"]


@traceable(client=client)
def run_pipeline():
    messages = format_prompt("colorful socks")
    response = invoke_llm(messages)
    result = parse_output(response)

    import time

    time.sleep(2)

    return result


if __name__ == "__main__":
    print("running pipeline")
    run_pipeline()
