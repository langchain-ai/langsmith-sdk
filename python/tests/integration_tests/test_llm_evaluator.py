import pytest

from langsmith import Client, aevaluate, evaluate
from langsmith.evaluation.llm_evaluator import (
    CategoricalScoreConfig,
    ContinuousScoreConfig,
    LLMEvaluator,
)


def test_llm_evaluator_init() -> None:
    evaluator = LLMEvaluator(
        prompt_template="Is the response vague? Y/N\n{input}",
        score_config=CategoricalScoreConfig(
            key="vagueness",
            choices=["Y", "N"],
            description="Whether the response is vague. Y for yes, N for no.",
            reasoning_key="explanation",
        ),
    )
    assert evaluator is not None
    assert evaluator.prompt.input_variables == ["input"]
    assert evaluator.score_schema == {
        "title": "vagueness",
        "description": "Whether the response is vague. Y for yes, N for no.",
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["Y", "N"],
                "description": "The selected catgory for the evaluation, one of Y, N.",
            },
            "explanation": {
                "type": "string",
                "description": "Think step-by-step about what the correct score should be.",  # noqa: E501
            },
        },
        "required": ["category", "explanation"],
    }

    # Try a continuous score
    evaluator = LLMEvaluator(
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
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "The score for the evaluation, "
                "between 0 and 1, inclusive.",
            },
        },
        "required": ["score"],
    }

    # Test invalid model
    with pytest.raises(ValueError):
        LLMEvaluator(
            prompt_template="Rate the response from 0 to 1.\n{input}",
            score_config=ContinuousScoreConfig(
                key="rating", description="The rating of the response, from 0 to 1."
            ),
            model_provider="invalid",
        )

    evaluator = LLMEvaluator(
        prompt_template="Rate the response from 0 to 1.\n{input} {output} {expected}",
        score_config=ContinuousScoreConfig(
            key="rating", description="The rating of the response, from 0 to 1."
        ),
    )
    assert evaluator is not None
    assert set(evaluator.prompt.input_variables) == {"input", "output", "expected"}

    with pytest.raises(ValueError):
        # Test invalid input variable without map_variables
        LLMEvaluator(
            prompt_template="Rate the response from 0 to 1.\n{input} {output} {hello}",
            score_config=ContinuousScoreConfig(
                key="rating",
                description="The rating of the response, from 0 to 1.",
                include_explanation=False,
            ),
        )

    evaluator = LLMEvaluator(
        prompt_template="Rate the response from 0 to 1.\n{input} {output} {hello}",
        score_config=ContinuousScoreConfig(
            key="rating", description="The rating of the response, from 0 to 1."
        ),
        map_variables=lambda run, example: {"hello": "world"},
    )
    assert evaluator is not None
    assert set(evaluator.prompt.input_variables) == {"input", "output", "hello"}


def test_from_model() -> None:
    from langchain_openai import ChatOpenAI

    evaluator = LLMEvaluator.from_model(
        ChatOpenAI(),
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
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "The score for the evaluation, "
                "between 0 and 1, inclusive.",
            },
        },
        "required": ["score"],
    }


async def test_evaluate() -> None:
    client = Client()
    client.clone_public_dataset(
        "https://beta.smith.langchain.com/public/06785303-0f70-4466-b637-f23d38c0f28e/d"
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
        model_provider="anthropic",
        model_name="claude-3-haiku-20240307",
    )
    results = evaluate(
        predict,
        data=dataset_name,
        evaluators=[reference_accuracy, accuracy],
        experiment_prefix=__name__ + "::test_evaluate.evaluate",
    )
    results.wait()

    await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[reference_accuracy, accuracy],
        experiment_prefix=__name__ + "::test_evaluate.aevaluate",
    )


@pytest.mark.parametrize(
    "config_class", [CategoricalScoreConfig, ContinuousScoreConfig]
)
def test_backwards_compatibility(config_class) -> None:
    # Test include_explanation deprecation
    with pytest.warns(DeprecationWarning, match="include_explanation.*reasoning_key"):
        config = config_class(
            key="test",
            description="test description",
            include_explanation=True,
            **(
                {"choices": ["Y", "N"]}
                if config_class == CategoricalScoreConfig
                else {}
            ),
        )
        assert config.reasoning_key == "explanation"

    # Test explanation_description deprecation
    with pytest.warns(
        DeprecationWarning, match="explanation_description.*reasoning_description"
    ):
        config = config_class(
            key="test",
            description="test description",
            explanation_description="test explanation",
            **(
                {"choices": ["Y", "N"]}
                if config_class == CategoricalScoreConfig
                else {}
            ),
        )
        assert config.reasoning_description == "test explanation"

    # Test both deprecated fields together
    with pytest.warns(DeprecationWarning) as warnings:
        config = config_class(
            key="test",
            description="test description",
            include_explanation=True,
            explanation_description="test explanation",
            **(
                {"choices": ["Y", "N"]}
                if config_class == CategoricalScoreConfig
                else {}
            ),
        )
        assert len(warnings) == 2  # Should show both deprecation warnings
        assert config.reasoning_key == "explanation"
        assert config.reasoning_description == "test explanation"

    with pytest.raises(ValueError):
        config = config_class(
            key="test",
            description="test description",
            reasoning_key="custom_key",
            reasoning_description="custom description",
            explanation_description="old description",
            **(
                {"choices": ["Y", "N"]}
                if config_class == CategoricalScoreConfig
                else {}
            ),
        )

    with pytest.raises(ValueError):
        config = config_class(
            key="test",
            description="test description",
            reasoning_key="custom_key",
            include_explanation=True,
            reasoning_description="custom description",
            **(
                {"choices": ["Y", "N"]}
                if config_class == CategoricalScoreConfig
                else {}
            ),
        )
