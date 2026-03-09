"""Unit tests for Anthropic wrapper processing functions."""

from langsmith.wrappers._anthropic import _create_usage_metadata


class TestCreateUsageMetadata:
    """Test _create_usage_metadata function."""

    def test_no_cache(self):
        result = _create_usage_metadata({"input_tokens": 100, "output_tokens": 50})
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150
        assert "input_token_details" not in result

    def test_legacy_cache_tokens(self):
        # Anthropic reports cache tokens additively (not as subsets of input_tokens).
        # input_tokens=19 is the NON-cached portion; cache tokens are on top.
        result = _create_usage_metadata(
            {
                "input_tokens": 19,
                "output_tokens": 100,
                "cache_read_input_tokens": 32000,
                "cache_creation_input_tokens": 7000,
            }
        )
        assert result["input_tokens"] == 39019  # 19 + 32000 + 7000
        assert result["output_tokens"] == 100
        assert result["total_tokens"] == 39119  # 39019 + 100
        assert result["input_token_details"]["cache_read"] == 32000
        assert result["input_token_details"]["cache_creation"] == 7000

    def test_new_format_cache_object(self):
        result = _create_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 500,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 800,
                    "ephemeral_1h_input_tokens": 200,
                },
            }
        )
        assert result["input_tokens"] == 1600  # 100 + 500 + 800 + 200
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 1650  # 1600 + 50
        assert result["input_token_details"]["cache_read"] == 500
        assert result["input_token_details"]["ephemeral_5m_input_tokens"] == 800
        assert result["input_token_details"]["ephemeral_1h_input_tokens"] == 200

    def test_only_cache_read(self):
        result = _create_usage_metadata(
            {
                "input_tokens": 50,
                "output_tokens": 30,
                "cache_read_input_tokens": 1000,
            }
        )
        assert result["input_tokens"] == 1050  # 50 + 1000
        assert result["output_tokens"] == 30
        assert result["total_tokens"] == 1080  # 1050 + 30
        assert result["input_token_details"]["cache_read"] == 1000

    def test_zero_cache_tokens_not_in_details(self):
        # Zero-valued cache fields should not appear in input_token_details
        result = _create_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        )
        assert result["input_tokens"] == 100
        assert result["total_tokens"] == 150
        assert "input_token_details" not in result

    def test_empty_usage(self):
        result = _create_usage_metadata({})
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["total_tokens"] == 0
