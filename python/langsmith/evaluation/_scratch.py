import logging

from langchain_anthropic import ChatAnthropic

import langsmith
from langsmith.evaluation import LangChainStringEvaluator, evaluate

logging.basicConfig(level=logging.INFO)

c = langsmith.Client()


def nli(run, example):
    pred = next(iter(run.outputs))
    expected = example.outputs["answer"]
    return {"score": expected.lower() == pred}


def equal_length(runs, examples):
    return {"score": len(runs) == len(examples)}


results = evaluate(
    lambda inputs: {"output": "foo"},
    data="scone-test2",
    evaluators=[
        nli,
        LangChainStringEvaluator("embedding_distance"),
        LangChainStringEvaluator(
            "criteria", config={
                "criteria": {
                    "usefulness": "The prediction is useful if it is correct"
                             " and/or asks a useful followup question."},
                "llm": ChatAnthropic(model="claude-3-opus-20240229")
                }
        ),
    ],
    batch_evaluators=[equal_length],
)
print(results)

# # Subset
# examples = list(itertools.islice(c.list_examples(dataset_name="scone-test2"), 5))
# results2 = evaluate(
#     lambda inputs: {"output": "foo"},
#     data=examples,
#     evaluators=[nli],
#     batch_evaluators=[equal_length],
# )
# print(results2)
# # Streaming to more easily debug


# @traceable
# def nested_func(inputs):
#     @traceable
#     def foo(inputs):
#         return {"output": "foo"}

#     return foo(inputs)


# results3 = evaluate(
#     nested_func,
#     data=c.list_examples(dataset_name="scone-test2"),
#     evaluators=[nli],
#     batch_evaluators=[equal_length],
#     blocking=False,
# )
# for i, result in enumerate(results3):
#     print(i)
