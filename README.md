# LangSmith Client SDKs

 [![Release Notes](https://img.shields.io/github/release/langchain-ai/langsmith-sdk?logo=python)](https://github.com/langchain-ai/langsmith-sdk/releases)
 [![Python Downloads](https://static.pepy.tech/badge/langsmith/month)](https://pepy.tech/project/langsmith)

![NPM Version](https://img.shields.io/npm/v/langsmith?logo=npm)
[![JS Downloads](https://img.shields.io/npm/dm/langsmith)](https://www.npmjs.com/package/langsmith)

This repository contains the Python and Javascript SDK's for interacting with the [LangSmith platform](https://smith.langchain.com/).

LangSmith helps your team debug, evaluate, and monitor your language models and intelligent agents. It works
with any LLM Application, including a native integration with the [LangChain Python](https://github.com/langchain-ai/langchain) and [LangChain JS](https://github.com/langchain-ai/langchainjs) open source libraries.

LangSmith is developed and maintained by [LangChain](https://langchain.com/), the company behind the LangChain framework.

## Python Quick Start

To get started with the Python SDK, [install the package](https://pypi.org/project/langsmith/), then follow the instructions in the [Python README](python/README.md).

```bash
pip install -U langsmith
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_...
```

Then start tracing your app:

Then trace:

```python
import openai
from langsmith.wrappers import wrap_openai
from langsmith import traceable

# Auto-trace LLM calls in-context
client = wrap_openai(openai.Client())

@traceable # Auto-trace this function
def pipeline(user_input: str):
    result = client.chat.completions.create(
        messages=[{"role": "user", "content": user_input}],
        model="gpt-3.5-turbo"
    )
    return result.choices[0].message.content

pipeline("Hello, world!")
# Hello there! How can I assist you today?
```

See the resulting nested trace [🌐 here](https://smith.langchain.com/public/b37ca9b1-60cd-4a2a-817e-3c4e4443fdc0/r).

## JS Quick Start

To get started with the JavaScript / TypeScript SDK, [install the package](https://www.npmjs.com/package/langsmith), then follow the instructions in the [JS README](js/README.md).

```bash
yarn add langsmith
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_...
```

Then start tracing your app!

```javascript
import { OpenAI } from "openai";
import { traceable } from "langsmith/traceable";
import { wrapOpenAI } from "langsmith/wrappers";
// Auto-trace LLM calls in-context
const client = wrapOpenAI(new OpenAI());
// Auto-trace this function
const pipeline = traceable(async (user_input) => {
    const result = await client.chat.completions.create({
        messages: [{ role: "user", content: user_input }],
        model: "gpt-3.5-turbo",
    });
    return result.choices[0].message.content;
});

await pipeline("Hello, world!")
// Hello there! How can I assist you today?
```

## Cookbook

For tutorials on how to get more value out of LangSmith, check out the [Langsmith Cookbook](https://github.com/langchain-ai/langsmith-cookbook/tree/main) repo.

## Documentation

To learn more about the LangSmith platform, check out the [docs](https://docs.smith.langchain.com/docs/)
