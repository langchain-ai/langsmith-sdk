from langsmith import Client, aevaluate, evaluate
from langsmith.evaluation.llm_evaluator import (
    CategoricalScoreConfig,
    ContinuousScoreConfig,
    LLMEvaluator,
)
from langchain_openai import ChatOpenAI


def test_from_model() -> None:
    evaluator = LLMEvaluator.from_model(
        ChatOpenAI(), # can't use FakeChatModel because of bind_tools call in LLMEvaluator
        prompt_template="Rate the response from 0 to 1.\n{input}",
        score_config=ContinuousScoreConfig(
            key="rating", description="The rating of the response, from 0 to 1."
        ),
    )
    assert evaluator is not None
    assert evaluator.prompt.input_variables == ["input"]
    assert evaluator.score_schema == {
        "title": "rating",
        "description": "The rating of the response, from 0 to 1.",
        "type": "object",
        "properties": {
            'score': {
                'description': 'The score for the evaluation, between 0.0 and 1.0, inclusive.',
                'maximum': 1.0, 
                'minimum': 0.0, 
                'type': 'number'
            }
        },
        "required": ["score"],
    }

async def test_evaluate() -> None:
    client = Client()
    client.clone_public_dataset(
        "https://smith.langchain.com/public/1f800a04-56b0-4c3a-b01e-0b43095feea0/d"
    )
    dataset_name = "Evaluate Examples"

    def predict(inputs: dict) -> dict:
        return {"answer": "Yes"}

    async def apredict(inputs: dict) -> dict:
        return {"answer": "Yes"}

    reference_accuracy = LLMEvaluator(
        prompt_template="Is the output accurate with respect to the expected output? "
        "Y/N\nOutput: {output}\nExpected: {expected}",
        score_config=CategoricalScoreConfig(
            key="reference_accuracy",
            choices=["Y", "N"],
            description="Whether the output is accurate with respect to "
            "the expected output.",
        ),
    )

    accuracy = LLMEvaluator(
        prompt_template=[
            (
                "system",
                "Is the output accurate with respect to the context and "
                "question? Y/N",
            ),
            ("human", "Context: {context}\nQuestion: {question}\nOutput: {output}"),
        ],
        score_config=CategoricalScoreConfig(
            key="accuracy",
            choices=["Y", "N"],
            description="Whether the output is accurate with respect to "
            "the context and question.",
            reasoning_key="explanation",
        ),
        map_variables=lambda run, example: {
            "context": example.inputs.get("context", "") if example else "",
            "question": example.inputs.get("question", "") if example else "",
            "output": run.outputs.get("output", "") if run.outputs else "",
        },
        model_provider="openai",
        model_name="gpt-4o-mini",
    )
    results = evaluate(
        predict,
        data=dataset_name,
        evaluators=[reference_accuracy, accuracy],
        experiment_prefix=__name__ + "::test_evaluate.evaluate",
        client=client
    )
    results.wait()

    await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[reference_accuracy, accuracy],
        experiment_prefix=__name__ + "::test_evaluate.aevaluate",
        client=client
    )
