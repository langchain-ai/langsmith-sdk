"""Contains the LLMEvaluator class for building LLM-as-a-judge evaluators."""

from typing import Any, Callable, List, Optional, Tuple, Union

from pydantic import BaseModel

from langsmith.evaluation import EvaluationResult, EvaluationResults, RunEvaluator
from langsmith.schemas import Example, Run


class CategoricalScoreConfig(BaseModel):
    """Configuration for a categorical score."""

    key: str
    choices: List[str]
    description: str
    include_explanation: bool = False


class ContinuousScoreConfig(BaseModel):
    """Configuration for a continuous score."""

    key: str
    min: float = 0
    max: float = 1
    description: str
    include_explanation: bool = False


def _create_score_json_schema(
    score_config: Union[CategoricalScoreConfig, ContinuousScoreConfig],
) -> dict:
    properties: dict[str, Any] = {}
    if isinstance(score_config, CategoricalScoreConfig):
        properties["score"] = {
            "type": "string",
            "enum": score_config.choices,
            "description": f"The score for the evaluation, one of "
            f"{', '.join(score_config.choices)}.",
        }
    elif isinstance(score_config, ContinuousScoreConfig):
        properties["score"] = {
            "type": "number",
            "minimum": score_config.min,
            "maximum": score_config.max,
            "description": f"The score for the evaluation, between "
            f"{score_config.min} and {score_config.max}, inclusive.",
        }
    else:
        raise ValueError("Invalid score type. Must be 'categorical' or 'continuous'")

    if score_config.include_explanation:
        properties["explanation"] = {
            "type": "string",
            "description": "The explanation for the score.",
        }

    return {
        "title": score_config.key,
        "description": score_config.description,
        "type": "object",
        "properties": properties,
        "required": (
            ["score", "explanation"] if score_config.include_explanation else ["score"]
        ),
    }


class LLMEvaluator(RunEvaluator):
    """A class for building LLM-as-a-judge evaluators."""

    def __init__(
        self,
        *,
        prompt_template: Union[str, List[Tuple[str, str]]],
        score_config: Union[CategoricalScoreConfig, ContinuousScoreConfig],
        map_variables: Optional[Callable[[Run, Example], dict]] = None,
        model: Optional[str] = "gpt-3.5-turbo",
        model_provider: Optional[str] = "openai",
        **kwargs,
    ):
        """Initialize the LLMEvaluator.

        Args:
            prompt_template (Union[str, List[Tuple[str, str]]): The prompt
                template to use for the evaluation. If a string is provided, it is
                assumed to be a system message.
            score_config (Union[CategoricalScoreConfig, ContinuousScoreConfig]):
                The configuration for the score, either categorical or continuous.
            map_variables (Optional[Callable[[Run, Example], dict]], optional):
                A function that maps the run and example to the variables in the
            prompt. Defaults to None. If None, it is assumed that the prompt
                only requires 'input', 'output', and 'expected'.
            model (Optional[str], optional): The model to use for the evaluation.
                Defaults to "gpt-3.5-turbo".
            model_provider (Optional[str], optional): The model provider to use
                for the evaluation. Defaults to "openai".
        """
        try:
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as e:
            raise ImportError(
                "LLMEvaluator requires langchain-core to be installed. "
                "Please install langchain-core by running `pip install langchain-core`."
            ) from e
        try:
            from langchain.chat_models import init_chat_model
        except ImportError as e:
            raise ImportError(
                "LLMEvaluator requires langchain to be installed. "
                "Please install langchain by running `pip install langchain`."
            ) from e
        if isinstance(prompt_template, str):
            self.prompt = ChatPromptTemplate.from_messages(
                [("system", prompt_template)]
            )
        else:
            self.prompt = ChatPromptTemplate.from_messages(prompt_template)

        if set(self.prompt.input_variables) - {"input", "output", "expected"}:
            if not map_variables:
                raise ValueError(
                    "map_inputs must be provided if the prompt template contains "
                    "variables other than 'input', 'output', and 'expected'"
                )
        self.map_variables = map_variables

        self.score_config = score_config
        self.score_schema = _create_score_json_schema(self.score_config)

        try:
            model = init_chat_model(
                model=model, model_provider=model_provider, **kwargs
            ).with_structured_output(self.score_schema)
        except ImportError as e:
            raise ImportError(
                "LLMEvaluator is missing a required langchain integration."
            ) from e
        except ValueError as e:
            raise ValueError(
                "Error loading the model. Please check the model, model_provider, "
                "and that the appropriate secrets are set."
            ) from e

        self.runnable = self.prompt | model

    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> Union[EvaluationResult, EvaluationResults]:
        """Evaluate a run."""
        if self.map_variables:
            variables = self.map_variables(run, example)
            if set(self.prompt.input_variables) - set(variables.keys()):
                raise ValueError(
                    "map_variables must return a dictionary with keys for all of the "
                    "variables in the prompt. Expected variables: "
                    f"{self.prompt.input_variables}. Returned variables: "
                    f"{variables.keys()}"
                )
            output = self.runnable.invoke(variables)
        else:
            variables = {}
            if "input" in self.prompt.input_variables:
                if len(run.inputs) == 0:
                    raise ValueError(
                        "No input keys are present in run.inputs but the prompt "
                        "requires 'input'."
                    )
                if len(run.inputs) != 1:
                    raise ValueError(
                        "Multiple input keys are present in run.inputs. Please provide "
                        "a map_variables function."
                    )
                variables["input"] = list(run.inputs.values())[0]
            if "output" in self.prompt.input_variables:
                if len(run.outputs) == 0:
                    raise ValueError(
                        "No output keys are present in run.outputs but the prompt "
                        "requires 'output'."
                    )
                if len(run.outputs) != 1:
                    raise ValueError(
                        "Multiple output keys are present in run.outputs. Please "
                        "provide a map_variables function."
                    )
                variables["output"] = list(run.outputs.values())[0]
            if "expected" in self.prompt.input_variables:
                if not example:
                    raise ValueError(
                        "No example is provided but the prompt requires 'expected'."
                    )
                if len(example.outputs) == 0:
                    raise ValueError(
                        "No output keys are present in example.outputs but the prompt "
                        "requires 'expected'."
                    )
                if len(example.outputs) != 1:
                    raise ValueError(
                        "Multiple output keys are present in example.outputs. Please "
                        "provide a map_variables function."
                    )
                variables["expected"] = list(example.outputs.values())[0]
            output = self.runnable.invoke(variables)

        if isinstance(self.score_config, CategoricalScoreConfig):
            value = output["score"]
            explanation = output.get("explanation", None)
            return EvaluationResult(
                key=self.score_config.key, value=value, comment=explanation
            )
        elif isinstance(self.score_config, ContinuousScoreConfig):
            score = output["score"]
            explanation = output.get("explanation", None)
            return EvaluationResult(
                key=self.score_config.key, score=score, comment=explanation
            )
