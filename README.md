# LangSmith Client SDKs

[![Release Notes](https://img.shields.io/github/release/langchain-ai/langsmith-sdk?logo=python)](https://github.com/langchain-ai/langsmith-sdk/releases)
[![Python Downloads](https://static.pepy.tech/badge/langsmith/month)](https://pepy.tech/project/langsmith)

![NPM Version](https://img.shields.io/npm/v/langsmith?logo=npm)
[![JS Downloads](https://img.shields.io/npm/dm/langsmith)](https://www.npmjs.com/package/langsmith)

This repository contains the Python and Javascript SDK's for interacting with the [LangSmith platform](https://smith.langchain.com/). Please see [LangSmith Documentation](https://docs.smith.langchain.com/)
for documentation about using the LangSmith platform and the client SDK.

LangSmith helps your team debug, evaluate, and monitor your language models and intelligent agents. It works
with any LLM Application, including a native integration with the [LangChain Python](https://github.com/langchain-ai/langchain) and [LangChain JS](https://github.com/langchain-ai/langchainjs) open source libraries.

LangSmith is developed and maintained by [LangChain](https://langchain.com/), the company behind the LangChain framework.

## Quick Start

To get started with the Python SDK, [install the package](https://pypi.org/project/langsmith/), then follow the instructions in the [Python README](python/README.md).

```bash
pip install -U langsmith
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=ls_...
export LANGSMITH_WORKSPACE_ID=<your-workspace-id> # Required for org-scoped keys
```

Then start tracing your app:

```python
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
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=ls_...
export LANGSMITH_WORKSPACE_ID=<your-workspace-id> # Required for org-scoped keys
```

Then start tracing your app!

```javascript
import { OpenAI } from "openai";
import { traceable } from "langsmith/traceable";
import { wrapOpenAI } from "langsmith/wrappers";

const client = wrapOpenAI(new OpenAI());

await client.chat.completions.create({
  model: "gpt-3.5-turbo",
  messages: [{ content: "Hi there!", role: "user" }],
});
```

```
{
  id: 'chatcmpl-8sOWEOYVyehDlyPcBiaDtTxWvr9v6',
  object: 'chat.completion',
  created: 1707974654,
  model: 'gpt-3.5-turbo-0613',
  choices: [
    {
      index: 0,
      message: { role: 'assistant', content: 'Hello! How can I help you today?' },
      logprobs: null,
      finish_reason: 'stop'
    }
  ],
  usage: { prompt_tokens: 10, completion_tokens: 9, total_tokens: 19 },
  system_fingerprint: null
}
```

## Cookbook

For tutorials on how to get more value out of LangSmith, check out the [Langsmith Cookbook](https://github.com/langchain-ai/langsmith-cookbook/tree/main) repo.

## Documentation

To learn more about the LangSmith platform, check out the [docs](https://docs.smith.langchain.com/)
