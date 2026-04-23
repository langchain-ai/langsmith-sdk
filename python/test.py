#!/usr/bin/env python3

# import openai
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable

# openai_client = wrap_openai(openai.Client())

# @traceable(name="trace-with-dynamic-client")
# def joke():
#     print(f"Joking... {openai_client}")
#     response = openai_client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": "Tell me a short joke."}],
#     )
#     return response.choices[0].message.content

# joke()
# joke(langsmith_extra={"tracing_destinations": "otel"})
# joke(langsmith_extra={"tracing_destinations": "hybrid"})


import openai

from langsmith import Client, traceable, tracing_context
from langsmith.run_trees import WriteReplica
from langsmith.wrappers import wrap_openai

# Client A: LangSmith only (default)
ls_client = Client()
# Client B: OTEL only
otel_client = Client(tracing_mode="otel")
# Client C: hybrid (both LangSmith + OTEL)
hybrid_client = Client(tracing_mode="hybrid")

# OpenAI client wrapper
openai_client = wrap_openai(openai.Client())


@traceable()
def joke():
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Tell me a short joke."}],
    )
    response = response.choices[0].message.content
    return response


replica_ls = WriteReplica(client=ls_client)
replica_otel = WriteReplica(client=otel_client)
replica_hybrid = WriteReplica(client=hybrid_client)

with tracing_context(replicas=[replica_ls]):
    print(joke())

with tracing_context(replicas=[replica_otel]):
    print(joke())

with tracing_context(replicas=[replica_hybrid]):
    print(joke())
