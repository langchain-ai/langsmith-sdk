import os
import re

import pytest
import vcr


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


def is_ai_api_request(request):
    """Check if the request is to OpenAI or Anthropic APIs."""
    ai_domains = [
        "api.openai.com",
        "api.anthropic.com",
    ]

    return any(domain in request.host for domain in ai_domains)


def filter_request_data(request):
    """Filter sensitive data from requests and only record AI API calls."""

    # Only record OpenAI and Anthropic API calls
    if not is_ai_api_request(request):
        return None  # Skip recording this request

    if request.body:
        try:
            # Try to decode as string if it's bytes
            if isinstance(request.body, bytes):
                body_str = request.body.decode("utf-8")
            else:
                body_str = request.body

            # Replace API keys and other sensitive data
            body_str = re.sub(
                r'(api[-_]?key"?\s*:\s*")\w+(")', r"\1FILTERED\2", body_str
            )
            body_str = re.sub(r"(Bearer\s+)[A-Za-z0-9-_]+", r"\1FILTERED", body_str)

            # Update the request body
            if isinstance(request.body, bytes):
                request.body = body_str.encode("utf-8")
            else:
                request.body = body_str
        except (UnicodeDecodeError, AttributeError):
            pass
    return request


def filter_response_data(response):
    """Filter sensitive data from responses."""
    # Only process responses from AI APIs
    if not hasattr(response, "request"):
        return response

    if not is_ai_api_request(response.request):
        return None

    return response


# Create a custom VCR instance with our configuration
def create_vcr_instance(record_mode):
    """Create a configured VCR instance."""
    cassette_dir = os.path.join(os.path.dirname(__file__), "cassettes")

    # Configure VCR
    my_vcr = vcr.VCR(
        cassette_library_dir=cassette_dir,
        record_mode=record_mode,
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
        filter_headers=[
            "Authorization",
            "X-Api-Key",
            "OpenAI-Organization",
            "Anthropic-Version",
            "User-Agent",
        ],
        # Filter out API keys from request bodies
        before_record_request=filter_request_data,
        before_record_response=filter_response_data,
        decode_compressed_response=True,
    )
    return my_vcr


@pytest.fixture(scope="function", autouse=True)
def vcr_fixture(request):
    """Global VCR fixture that's automatically used for all tests.

    This will record/replay only OpenAI and Anthropic API calls.
    """

    # Get the record mode from command line
    record_mode = request.config.getoption("--vcr-mode")

    # Create the VCR instance
    my_vcr = create_vcr_instance(record_mode)

    # Create a cassette name based on the test function
    module_name = request.module.__name__.split(".")[-1]
    test_name = request.function.__name__
    cassette_name = f"{module_name}_{test_name}"

    # Use the cassette for this test
    with my_vcr.use_cassette(f"{cassette_name}.yaml"):
        yield
