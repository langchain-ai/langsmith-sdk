import pytest
from pydantic import ValidationError
from langsmith.evaluation.evaluator import EvaluationResult

# 1. Should accept a valid feedback_config dict
def test_feedback_config_valid_dict():
    result = EvaluationResult(
        key="sentiment",
        value="positive",
        feedback_config={
            "type": "continuous",
            "min": 0,
            "max": 1,
            "categories": [{"label": "good", "value": 1}],
        }
    )
    assert result.feedback_config.type == "continuous"
    assert result.feedback_config.min == 0
    assert result.feedback_config.max == 1
    assert result.feedback_config.categories == [{"label": "good", "value": 1}]

# 2. Should raise a ValidationError if unknown fields are passed
def test_feedback_config_rejects_unknown_fields():
    with pytest.raises(ValidationError) as excinfo:
        EvaluationResult(
            key="sentiment",
            value="positive",
            feedback_config={"type": "continuous", "threshold": 1.0}
        )
    assert "Unknown fields" in str(excinfo.value)
    assert "threshold" in str(excinfo.value)

# 3. Should reject non-string literal values for 'type'
def test_feedback_config_literal_enforced():
    with pytest.raises(ValidationError) as excinfo:
        EvaluationResult(
            key="sentiment",
            value="positive",
            feedback_config={"type": 1.0}  # 🚫 invalid
        )
    assert "unexpected value" in str(excinfo.value)
    assert "continuous" in str(excinfo.value)
    assert "categorical" in str(excinfo.value)
    assert "freeform" in str(excinfo.value)

# 4. Should work when only some valid fields are present
def test_feedback_config_partial_valid():
    result = EvaluationResult(
        key="toxicity",
        value="low",
        feedback_config={"type": "categorical"}  # ✅ type is required, rest optional
    )
    assert result.feedback_config.type == "categorical"
    assert result.feedback_config.min is None
    assert result.feedback_config.max is None
    assert result.feedback_config.categories is None

# 5. Should raise if feedback_config dict is missing 'type'
def test_feedback_config_missing_type_rejected():
    with pytest.raises(ValidationError) as excinfo:
        EvaluationResult(
            key="sentiment",
            value="positive",
            feedback_config={"min": 0, "max": 1}  # 🚫 missing type
        )
    assert "field required" in str(excinfo.value)
    assert "type" in str(excinfo.value)

# 6. Original Example: Violates literal condition for type
def test_example_violates_literal_condition():
    with pytest.raises(ValidationError):
        EvaluationResult(
            key="sentiment",
            value="positive",
            feedback_config={"type": 1.0, "threshold": 1.0}  # 🚫 both issues
        )

# 7. Original Example: Follows literal condition but extra data rejected
def test_example_follows_literal_condition_but_extra_removed():
    with pytest.raises(ValidationError) as excinfo:
        EvaluationResult(
            key="sentiment",
            value="positive",
            feedback_config={"type": "continuous", "threshold": 1.0}  # 🚫 unknown field
        )
    assert "Unknown fields" in str(excinfo.value)

# 8. Original Example: No feedback_config at all (✅ allowed)
def test_feedback_config_optional_completely():
    result = EvaluationResult(
        key="sentiment",
        value="positive"
    )
    assert result.feedback_config is None
