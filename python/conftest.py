"""Pytest config for doctests."""

import hashlib
import json
import os
import re

import pytest
import vcr
import vcr.patch


def get_request_hash(request):
    """Generate a hash based on important parts of the request body."""
    if not request.body:
        return None

    try:
        # Try to decode and parse as JSON
        if isinstance(request.body, bytes):
            body_str = request.body.decode("utf-8")
        else:
            body_str = request.body

        body_json = json.loads(body_str)

        key_elements = {
            k: v for k, v in body_json.items() if k in ("model", "messages", "tools")
        }
        # Hash the key elements
        hash_input = json.dumps(key_elements, sort_keys=True)
        return hashlib.md5(hash_input.encode()).hexdigest()
    except BaseException:
        # If parsing fails, return None
        return None


def custom_request_matcher(r1, r2):
    """Match that uses request hashing for OpenAI API calls."""
    # First check standard matchers
    standard_match = all(
        [
            r1.method == r2.method,
            r1.scheme == r2.scheme,
            r1.host == r2.host,
            r1.port == r2.port,
            r1.path == r2.path,
            r1.query == r2.query,
        ]
    )

    if not standard_match:
        return False

    # For OpenAI API calls, use our custom hash-based matching
    if "openai.com" in r1.host:
        hash1 = get_request_hash(r1)
        hash2 = get_request_hash(r2)

        # If we couldn't hash either request, fall back to exact body matching
        if hash1 is None or hash2 is None:
            return r1.body == r2.body

        return hash1 == hash2

    # For other requests, use exact body matching
    return r1.body == r2.body


def pytest_addoption(parser):
    """Pytest options."""
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--vcr-mode",
        type=str,
        default="once",
        help="VCR record mode: once, new_episodes, none, or all (default: all)",
    )


def pytest_collection_modifyitems(config, items):
    """Configure tests to run."""
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
        # For doctests, don't match on body since it might change slightly
        match_on=["custom"],
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
    my_vcr.register_matcher("custom_body", custom_request_matcher)
    my_vcr.match_on = ["custom_body"]

    return my_vcr


@pytest.fixture(scope="function", autouse=True)
def vcr_fixture(request):
    """Global VCR fixture that's automatically used for all tests.

    This will record/replay only OpenAI and Anthropic API calls.
    """
    # Check if this is a doctest
    is_doctest = hasattr(request.node, "dtest")

    # Get the record mode from command line, but use a different default for doctests
    record_mode = request.config.getoption("--vcr-mode")
    if is_doctest and record_mode == "once":
        # For doctests, default to new_episodes which is more forgiving
        record_mode = "new_episodes"

    # Create the VCR instance
    my_vcr = create_vcr_instance(record_mode)

    # Create a cassette name based on the test function
    cassette_name = request.module.__name__.split(".")[-1]
    if request.function:
        test_name = request.function.__name__
        cassette_name += f"_{test_name}"

    # Use the cassette for this test
    with my_vcr.use_cassette(f"{cassette_name}.yaml"):
        yield


original_exit = vcr.patch.ConnectionRemover.__exit__


def safe_exit(self, *args):
    """Create safer ConnectionRemover.__exit__."""
    for pool, connections in self._connection_pool_to_connections.items():
        readd_connections = []
        # Get all connections from the pool first
        while pool.pool and not pool.pool.empty():
            connection = pool.pool.get()
            if isinstance(connection, self._connection_class):
                try:
                    # Use a safer way to remove - check first if it exists
                    if connection in connections:
                        connections.remove(connection)
                    connection.close()
                except (KeyError, RuntimeError):
                    # Just close the connection if we can't remove it properly
                    connection.close()
            else:
                readd_connections.append(connection)

        # Add connections back to the pool
        for connection in readd_connections:
            pool._put_conn(connection)

        # Use a copy of the set for iteration to avoid modification issues
        for connection in list(connections):
            try:
                connection.close()
            except Exception:
                pass  # Ignore any errors while closing connections


vcr.patch.ConnectionRemover.__exit__ = safe_exit
