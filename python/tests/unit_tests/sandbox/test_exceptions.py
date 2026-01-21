"""Tests for sandbox exceptions."""

from langsmith.sandbox import (
    PoolValidationError,
    ResourceNameConflictError,
    SandboxClientError,
    SandboxCreationError,
    SandboxOperationError,
    SandboxQuotaExceededError,
    SandboxTimeoutError,
    SandboxValidationError,
)
from langsmith.utils import LangSmithError


class TestExceptionHierarchy:
    """Test that sandbox exceptions extend LangSmithError."""

    def test_sandbox_client_error_extends_langsmith_error(self):
        """Test that SandboxClientError extends LangSmithError."""
        assert issubclass(SandboxClientError, LangSmithError)

    def test_sandbox_client_error_can_be_raised(self):
        """Test that SandboxClientError can be raised and caught."""
        try:
            raise SandboxClientError("test error")
        except LangSmithError as e:
            assert str(e) == "test error"


class TestSandboxTimeoutError:
    """Tests for SandboxTimeoutError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxTimeoutError("Timeout waiting for sandbox")
        assert str(error) == "Timeout waiting for sandbox"
        assert error.last_status is None

    def test_with_last_status(self):
        """Test error with last_status."""
        error = SandboxTimeoutError(
            "Timeout waiting for sandbox", last_status="Pending"
        )
        assert "Timeout waiting for sandbox" in str(error)
        assert "last_status: Pending" in str(error)
        assert error.last_status == "Pending"


class TestSandboxValidationError:
    """Tests for SandboxValidationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxValidationError("Invalid CPU value")
        assert str(error) == "Invalid CPU value"
        assert error.field is None
        assert error.details == []

    def test_with_field_and_details(self):
        """Test error with field and details."""
        details = [{"loc": ["body", "cpu"], "msg": "value too high"}]
        error = SandboxValidationError(
            "Invalid CPU value",
            field="cpu",
            details=details,
        )
        assert error.field == "cpu"
        assert error.details == details


class TestSandboxQuotaExceededError:
    """Tests for SandboxQuotaExceededError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxQuotaExceededError("Quota exceeded")
        assert str(error) == "Quota exceeded"
        assert error.quota_type is None

    def test_with_quota_type(self):
        """Test error with quota_type."""
        error = SandboxQuotaExceededError("Quota exceeded", quota_type="sandbox_count")
        assert error.quota_type == "sandbox_count"


class TestSandboxCreationError:
    """Tests for SandboxCreationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxCreationError("Failed to create sandbox")
        assert str(error) == "Failed to create sandbox"
        assert error.error_type is None

    def test_with_error_type(self):
        """Test error with error_type."""
        error = SandboxCreationError("Image pull failed", error_type="ImagePull")
        assert "[ImagePull]" in str(error)
        assert error.error_type == "ImagePull"


class TestSandboxOperationError:
    """Tests for SandboxOperationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = SandboxOperationError("Command failed")
        assert str(error) == "Command failed"
        assert error.error_type is None

    def test_with_error_type(self):
        """Test error with error_type."""
        error = SandboxOperationError("Write failed", error_type="WriteError")
        assert "[WriteError]" in str(error)
        assert error.error_type == "WriteError"


class TestResourceNameConflictError:
    """Tests for ResourceNameConflictError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = ResourceNameConflictError("Name already exists")
        assert str(error) == "Name already exists"
        assert error.resource_type is None

    def test_with_resource_type(self):
        """Test error with resource_type."""
        error = ResourceNameConflictError("Name already exists", resource_type="volume")
        assert error.resource_type == "volume"


class TestPoolValidationError:
    """Tests for PoolValidationError."""

    def test_basic_message(self):
        """Test basic error message."""
        error = PoolValidationError("Template has volumes")
        assert str(error) == "Template has volumes"
        assert error.error_type is None

    def test_with_error_type(self):
        """Test error with error_type."""
        error = PoolValidationError(
            "Template has volumes", error_type="ValidationError"
        )
        assert error.error_type == "ValidationError"
