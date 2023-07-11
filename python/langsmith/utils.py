"""Generic utility functions."""
import platform
from functools import lru_cache
from typing import Any, Callable, Dict, List, Mapping, Tuple

import requests
from requests import ConnectionError, HTTPError, Response
from tenacity import Retrying


class LangChainPlusAPIError(Exception):
    """An error occurred while communicating with the LangChain API."""


class LangChainPlusUserError(Exception):
    """An error occurred while communicating with the LangChain API."""


class LangChainPlusError(Exception):
    """An error occurred while communicating with the LangChain API."""


class LangChainPlusConnectionError(Exception):
    """Couldn't connect to the LC+ API."""


def request_with_retries(
    request_method: str, url: str, request_kwargs: Mapping, retry_config: Mapping
) -> Response:
    for attempt in Retrying(**retry_config):
        with attempt:
            try:
                response = requests.request(request_method, url, **request_kwargs)
                raise_for_status_with_text(response)
                return response
            except HTTPError as e:
                if response is not None and response.status_code == 500:
                    raise LangChainPlusAPIError(
                        f"Server error caused failure to {request_method} {url} in"
                        f" LangSmith API. {e}"
                    )
                else:
                    raise LangChainPlusUserError(
                        f"Failed to {request_method} {url} in LangSmith API. {e}"
                    )
            except ConnectionError as e:
                raise LangChainPlusConnectionError(
                    f"Connection error caused failure to {request_method} {url}"
                    "  in LangSmith API. Please confirm your LANGCHAIN_ENDPOINT."
                ) from e
            except Exception as e:
                raise LangChainPlusError(
                    f"Failed to {request_method} {url} in LangSmith API. {e}"
                ) from e
    raise LangChainPlusError(f"Failed to {request_method}  {url} in LangSmith API. ")


def xor_args(*arg_groups: Tuple[str, ...]) -> Callable:
    """Validate specified keyword args are mutually exclusive."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            """Validate exactly one arg in each group is not None."""
            counts = [
                sum(1 for arg in arg_group if kwargs.get(arg) is not None)
                for arg_group in arg_groups
            ]
            invalid_groups = [i for i, count in enumerate(counts) if count != 1]
            if invalid_groups:
                invalid_group_names = [", ".join(arg_groups[i]) for i in invalid_groups]
                raise ValueError(
                    "Exactly one argument in each of the following"
                    " groups must be defined:"
                    f" {', '.join(invalid_group_names)}"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def raise_for_status_with_text(response: Response) -> None:
    """Raise an error with the response text."""
    try:
        response.raise_for_status()
    except HTTPError as e:
        raise ValueError(response.text) from e


@lru_cache(maxsize=1)
def get_runtime_environment() -> dict:
    """Get information about the environment."""
    # Lazy import to avoid circular imports
    from langsmith import __version__

    return {
        "sdk_version": __version__,
        "library": "langsmith",
        "platform": platform.platform(),
        "runtime": "python",
        "runtime_version": platform.python_version(),
    }


def _get_message_type(message: Mapping[str, Any]) -> str:
    if not message:
        raise ValueError("Message is empty.")
    if "lc" in message:
        if "id" not in message:
            raise ValueError(
                f"Unexpected format for serialized message: {message}"
                " Message does not have an id."
            )
        return message["id"][-1].replace("Message", "").lower()
    else:
        if "type" not in message:
            raise ValueError(
                f"Unexpected format for stored message: {message}"
                " Message does not have a type."
            )
        return message["type"]


def _get_message_fields(message: Mapping[str, Any]) -> Mapping[str, Any]:
    if not message:
        raise ValueError("Message is empty.")
    if "lc" in message:
        if "kwargs" not in message:
            raise ValueError(
                f"Unexpected format for serialized message: {message}"
                " Message does not have kwargs."
            )
        return message["kwargs"]
    else:
        if "data" not in message:
            raise ValueError(
                f"Unexpected format for stored message: {message}"
                " Message does not have data."
            )
        return message["data"]


def _convert_message(message: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract message from a message object."""
    message_type = _get_message_type(message)
    message_data = _get_message_fields(message)
    return {"type": message_type, "data": message_data}


def get_messages_from_inputs(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if "messages" in inputs:
        return [_convert_message(message) for message in inputs["messages"]]
    if "message" in inputs:
        return [_convert_message(inputs["message"])]
    raise ValueError(f"Could not find message(s) in run with inputs {inputs}.")


def get_message_generation_from_outputs(outputs: Mapping[str, Any]) -> Dict[str, Any]:
    if "generations" not in outputs:
        raise ValueError(f"No generations found in in run with output: {outputs}.")
    generations = outputs["generations"]
    if len(generations) != 1:
        raise ValueError(
            "Chat examples expect exactly one generation."
            f" Found {len(generations)} generations: {generations}."
        )
    first_generation = generations[0]
    if "message" not in first_generation:
        raise ValueError(
            f"Unexpected format for generation: {first_generation}."
            " Generation does not have a message."
        )
    return _convert_message(first_generation["message"])


def get_prompt_from_inputs(inputs: Mapping[str, Any]) -> str:
    if "prompt" in inputs:
        return inputs["prompt"]
    if "prompts" in inputs:
        prompts = inputs["prompts"]
        if len(prompts) == 1:
            return prompts[0]
        raise ValueError(
            f"Multiple prompts in run with inputs {inputs}."
            " Please create example manually."
        )
    raise ValueError(f"Could not find prompt in run with inputs {inputs}.")


def get_llm_generation_from_outputs(outputs: Mapping[str, Any]) -> str:
    if "generations" not in outputs:
        raise ValueError(f"No generations found in in run with output: {outputs}.")
    generations = outputs["generations"]
    if len(generations) != 1:
        raise ValueError(f"Multiple generations in run: {generations}")
    first_generation = generations[0]
    if "text" not in first_generation:
        raise ValueError(f"No text in generation: {first_generation}")
    return first_generation["text"]
