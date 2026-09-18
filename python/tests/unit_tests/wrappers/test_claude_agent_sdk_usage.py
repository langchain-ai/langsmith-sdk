"""Unit tests for Claude Agent SDK usage normalization."""

import pytest

from langsmith.integrations.claude_agent_sdk._usage import extract_usage_metadata


def _authoritative_input(usage: dict) -> int:
    """Anthropic cache tokens are additive to the raw ``input_tokens``."""
    return (
        usage["input_tokens"]
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )


@pytest.mark.parametrize(
    "usage",
    [
        pytest.param(
            {
                "input_tokens": 25,
                "output_tokens": 7,
                "cache_read_input_tokens": 21375,
                "cache_creation_input_tokens": 0,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 0,
                    "ephemeral_1h_input_tokens": 0,
                },
            },
            id="cache_read",
        ),
        pytest.param(
            {
                "input_tokens": 25,
                "output_tokens": 7,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 1000,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 1000,
                    "ephemeral_1h_input_tokens": 0,
                },
            },
            id="cache_creation_5m",
        ),
        pytest.param(
            {
                "input_tokens": 25,
                "output_tokens": 7,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 1000,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 400,
                    "ephemeral_1h_input_tokens": 600,
                },
            },
            id="cache_creation_both_tiers",
        ),
        pytest.param(
            {
                "input_tokens": 25,
                "output_tokens": 7,
                "cache_creation_input_tokens": 1000,
            },
            id="flat_field_only",
        ),
    ],
)
def test_input_tokens_match_the_authoritative_total(usage):
    """input_tokens must equal raw input plus every cache field Anthropic reports."""
    meta = extract_usage_metadata(usage)

    expected_input = _authoritative_input(usage)
    assert meta["input_tokens"] == expected_input
    assert meta["total_tokens"] == expected_input + usage["output_tokens"]


def test_unrecognized_cache_tier_is_still_counted():
    """A TTL tier this code does not name must not vanish from the totals.

    ``cache_creation_input_tokens`` is the total; ``cache_creation`` is a
    per-tier breakdown of that same total. Deriving the arithmetic from the
    breakdown means a tier the SDK has not been taught about is dropped from
    ``input_tokens`` and ``total_tokens``, and nothing raises, so the run just
    reports fewer tokens than were billed.

    The tier set is not fixed. ``cache_creation`` was introduced alongside the
    1-hour cache, splitting what had been a single flat field, so the same
    thing happens again the next time a tier is added.
    """
    usage = {
        "input_tokens": 25,
        "output_tokens": 7,
        "cache_creation_input_tokens": 1000,
        "cache_creation": {"ephemeral_1d_input_tokens": 1000},
    }

    meta = extract_usage_metadata(usage)

    assert meta["input_tokens"] == 1025
    assert meta["total_tokens"] == 1032


def test_empty_cache_creation_breakdown_falls_back_to_the_total():
    """An empty breakdown must not zero out a non-zero cache-creation total."""
    usage = {
        "input_tokens": 25,
        "output_tokens": 7,
        "cache_creation_input_tokens": 1000,
        "cache_creation": {},
    }

    meta = extract_usage_metadata(usage)

    assert meta["input_tokens"] == 1025
    assert meta["total_tokens"] == 1032


def test_breakdown_without_a_flat_total_is_still_summed():
    """When only the per-tier breakdown is present, it supplies the total."""
    usage = {
        "input_tokens": 25,
        "output_tokens": 7,
        "cache_creation": {
            "ephemeral_5m_input_tokens": 400,
            "ephemeral_1h_input_tokens": 600,
        },
    }

    meta = extract_usage_metadata(usage)

    assert meta["input_tokens"] == 1025
    assert meta["total_tokens"] == 1032
    assert meta["input_token_details"] == {
        "ephemeral_5m_input_tokens": 400,
        "ephemeral_1hr_input_tokens": 600,
    }


def test_details_are_preserved():
    """The per-tier breakdown is still reported, under the canonical keys."""
    usage = {
        "input_tokens": 25,
        "output_tokens": 7,
        "cache_read_input_tokens": 500,
        "cache_creation_input_tokens": 1000,
        "cache_creation": {
            "ephemeral_5m_input_tokens": 400,
            "ephemeral_1h_input_tokens": 600,
        },
    }

    meta = extract_usage_metadata(usage)

    assert meta["input_token_details"] == {
        "cache_read": 500,
        "ephemeral_5m_input_tokens": 400,
        "ephemeral_1hr_input_tokens": 600,
    }


def test_empty_usage_returns_empty_dict():
    assert extract_usage_metadata(None) == {}
    assert extract_usage_metadata({}) == {}
