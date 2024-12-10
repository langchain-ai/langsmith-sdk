import os
os.environ["LANGCHAIN_PROJECT"] = "llm_messages_test_py"
os.environ["LANGSMITH_USE_PYO3_CLIENT"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "http://localhost:1984"

import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai

client = wrap_openai(openai.Client())

@traceable(run_type="tool", name="Retrieve Context")
def my_tool(question: str) -> str:
    return "During this morning's meeting, we solved all world conflict."

@traceable(name="Chat Pipeline")
def chat_pipeline(question: str):
    context = my_tool(question)
    messages = [
        { "role": "system", "content": "You are a helpful assistant. Please respond to the user's request only based on the given context." },
        { "role": "user", "content": f"Question: {question}\nContext: {context}"}
    ]
    chat_completion = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages
    )
    return chat_completion.choices[0].message.content

if __name__ == "__main__":
    chat_pipeline("Can you summarize this morning's meetings?")