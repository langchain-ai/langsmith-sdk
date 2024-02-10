# LangSmith Client SDKs

This repository contains the Python and Javascript SDK's for interacting with the [LangSmith platform](https://smith.langchain.com/).

LangSmith helps your team debug, evaluate, and monitor your language models and intelligent agents. It works
with any LLM Application, including a native integration with the [LangChain Python](https://github.com/hwchase17/langchain) and [LangChain JS](https://github.com/hwchase17/langchainjs) open source libraries.

LangSmith is developed and maintained by [LangChain](https://langchain.com/), the company behind the LangChain framework.

## Quick Start

To get started with the Python SDK, [install the package](https://pypi.org/project/langsmith/), then follow the instructions in the [Python README](python/README.md).

```bash
pip install -U langsmith
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_...
```

Then start tracing your app:

```
import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai

client = wrap_openai(openai.Client())

client.chat.completions.create(
    messages=[{"role": "user", "content": "Hello, world"}],
    model="gpt-3.5-turbo"
)
```

To get started with the JavaScript / TypeScript SDK, [install the package](https://www.npmjs.com/package/langsmith), then follow the instructions in the [JS README](js/README.md).

```bash
yarn add langsmith
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_...
```

Then start tracing your app!

## Cookbook

For tutorials on how to get more value out of LangSmith, check out the [Langsmith Cookbook](https://github.com/langchain-ai/langsmith-cookbook/tree/main) repo.

## Documentation

To learn more about the LangSmith platform, check out the [docs](https://docs.smith.langchain.com/docs/)
