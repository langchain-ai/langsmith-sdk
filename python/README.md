# LangChainPlus Client SDK

This package contains the Python client for interacting with the [LangChainPlus platform](https://www.langchain.plus/).

To install:

```bash
pip install langchainplus-sdk
```

LangChainPlus helps you and your team develop and evaluate language models and intelligent agents. It is compatible with any LLM Application and provides seamless integration with [LangChain](https://github.com/hwchase17/langchain), a widely recognized open-source framework that simplifies the process for developers to create powerful language model applications.

> **Note**: You can enjoy the benefits of LangChainPlus without using the LangChain open-source packages! To get started with your own proprietary framework, set up your account and then skip to [Logging Traces Outside LangChain](#logging-traces-outside-langchain).

A typical workflow looks like:

1. Set up an account with LangChainPlus or host your [local server](https://docs.langchain.plus/docs/getting-started/local_installation).
2. Log traces.
3. Debug, Create Datasets, and Evaluate Runs.

We'll walk through these steps in more detail below.

## 1. Connect to LangChainPlus

Sign up for [LangChainPlus](https://www.langchain.plus/) using your GitHub, Discord accounts, or an email address and password. If you sign up with an email, make sure to verify your email address before logging in.

Then, create a unique API key on the [Settings Page](https://www.langchain.plus/settings), which is found in the menu at the top right corner of the page.

Note: Save the API Key in a secure location. It will not be shown again.

## 2. Log Traces

You can log traces natively in your LangChain application or using a LangChainPlus RunTree.

### Logging Traces with LangChain

LangChainPlus seamlessly integrates with the Python LangChain library to record traces from your LLM applications.

1. **Copy the environment variables from the Settings Page and add them to your application.**

Tracing can be activated by setting the following environment variables or by manually specifying the LangChainTracer.

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.langchain.plus" # or your own server
os.environ["LANGCHAIN_API_KEY"] = "<YOUR-LANGCHAINPLUS-API-KEY>"
# os.environ["LANGCHAIN_SESSION"] = "My Session Name" # Optional: "default" is used if not set
```

> **Tip:** Sessions are groups of traces. All runs are logged to a session. If not specified, the session is set to `default`.

2. **Run an Agent, Chain, or Language Model in LangChain**

If the environment variables are correctly set, your application will automatically connect to the LangChainPlus platform.

```python
from langchain.chat_models import ChatOpenAI

chat = ChatOpenAI()
response = chat.predict(
    "Translate this sentence from English to French. I love programming."
)
print(response)
```

### Logging Traces Outside LangChain

_Note: this API is experimental and may change in the future_

You can still use the LangChainPlus development platform without depending on any
LangChain code. You can connect either by setting the appropriate environment variables,
or by directly specifying the connection information in the RunTree.

1. **Copy the environment variables from the Settings Page and add them to your application.**

```python
import os
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.langchain.plus" # or your own server
os.environ["LANGCHAIN_API_KEY"] = "<YOUR-LANGCHAINPLUS-API-KEY>"
# os.environ["LANGCHAIN_SESSION"] = "My Session Name" # Optional: "default" is used if not set
```

2. **Log traces using a RunTree.**

A RunTree tracks your application. Each RunTree object is required to have a `name` and `run_type`. These and other important attributes are as follows:

- `name`: `str` - used to identify the component's purpose
- `run_type`: `str` - Currently one of "llm", "chain" or "tool"; more options will be added in the future
- `inputs`: `dict` - the inputs to the component
- `outputs`: `Optional[dict]` - the (optional) returned values from the component
- `error`: `Optional[str]` - Any error messages that may have arisen during the call

```python
from langchainplus_sdk.run_trees import RunTree

parent_run = RunTree(
    name="My Chat Bot",
    run_type="chain",
    inputs={"text": "Summarize this morning's meetings."},
    serialized={},  # Serialized representation of this chain
    # session_name= "Defaults to the LANGCHAIN_SESSION env var"
    # api_url= "Defaults to the LANGCHAIN_ENDPOINT env var"
    # api_key= "Defaults to the LANGCHAIN_API_KEY env var"
)
# .. My Chat Bot calls an LLM
child_llm_run = parent_run.create_child(
    name="My Proprietary LLM",
    run_type="llm",
    inputs={
        "prompts": [
            "You are an AI Assistant. The time is XYZ."
            " Summarize this morning's meetings."
        ]
    },
)
child_llm_run.end(
    outputs={
        "generations": [
            "I should use the transcript_loader tool"
            " to fetch meeting_transcripts from XYZ"
        ]
    }
)
# ..  My Chat Bot takes the LLM output and calls
# a tool / function for fetching transcripts ..
child_tool_run = parent_run.create_child(
    name="transcript_loader",
    run_type="tool",
    inputs={"date": "XYZ", "content_type": "meeting_transcripts"},
)
# The tool returns meeting notes to the chat bot
child_tool_run.end(outputs={"meetings": ["Meeting1 notes.."]})

child_chain_run = parent_run.create_child(
    name="Unreliable Component",
    run_type="tool",
    inputs={"input": "Summarize these notes..."},
)

try:
    # .... the component does work
    raise ValueError("Something went wrong")
except Exception as e:
    child_chain_run.end(error=f"I errored again {e}")
    pass
# .. The chat agent recovers

parent_run.end(outputs={"output": ["The meeting notes are as follows:..."]})

# This posts all nested runs as a batch
res = parent_run.post(exclude_child_runs=False)
res.result()
```

## Create a Dataset from Existing Runs

Once your runs are stored in LangChainPlus, you can convert them into a dataset.
For this example, we will do so using the Client, but you can also do this using
the web interface, as explained in the [LangChainPlus docs](https://docs.langchain.plus/docs/).

```python
from langchainplus_sdk import LangChainPlusClient

client = LangChainPlusClient()
dataset_name = "Example Dataset"
# We will only use examples from the top level AgentExecutor run here,
# and exclude runs that errored.
runs = client.list_runs(
    session_name="my_session",
    execution_order=1,
    error=False,
)

dataset = client.create_dataset(dataset_name, description="An example dataset")
for run in runs:
    client.create_example(
        inputs=run.inputs,
        outputs=run.outputs,
        dataset_id=dataset.id,
    )
```

## Evaluating Runs

You can run evaluations directly using the LangChainPlus client.

```python
from typing import Optional
from langchainplus_sdk.evaluation import StringEvaluator


def jaccard_chars(output: str, answer: str) -> float:
    """Naive Jaccard similarity between two strings."""
    prediction_chars = set(output.strip().lower())
    answer_chars = set(answer.strip().lower())
    intersection = prediction_chars.intersection(answer_chars)
    union = prediction_chars.union(answer_chars)
    return len(intersection) / len(union)


def grader(run_input: str, run_output: str, answer: Optional[str]) -> dict:
    """Compute the score and/or label for this run."""
    if answer is None:
        value = "AMBIGUOUS"
        score = 0.5
    else:
        score = jaccard_chars(run_output, answer)
        value = "CORRECT" if score > 0.9 else "INCORRECT"
    return dict(score=score, value=value)

evaluator = StringEvaluator(evaluation_name="Jaccard", grading_function=grader)

runs = client.list_runs(
    session_name="my_session",
    execution_order=1,
    error=False,
)
for run in runs:
    client.evaluate_run(run, evaluator)
```

## Additional Documentation

To learn more about the LangChainPlus platform, check out the [docs](https://docs.langchain.plus/docs/).
